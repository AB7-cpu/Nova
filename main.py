"""
main.py
==========================================
Wires together the full pipeline:
  wakeword → STT → orchestrator → speak_queue → TTS

Background workers (persistent, started once at boot):
  tts_worker()       — drains speak_queue sequentially
  results_bundler()  — collects agent results → calls orchestrator
"""

import asyncio
import threading
from dotenv import load_dotenv

load_dotenv()

import wakeword.wakeword_open as wakeword
from stt.whisper_stt import take_command

from core.orchestrator import invoke_orchestrator
from core.speak_queue import tts_worker, stop_tts_worker, wait_until_done_speaking
from core.results_bundler import results_bundler
from core.session import Session


try:
    from frontend.bridge import set_state
except ImportError:
    async def set_state(_: str): pass


# ─── Constants ────────────────────────────────────────────────────────────────

TIMEOUT_INITIAL  = 5   # seconds to wait for first user input after wake word
TIMEOUT_FOLLOWUP = 6   # seconds to wait for follow-up input


# ─── Agent result handler ─────────────────────────────────────────────────────

def _format_results(bundle: list[dict]) -> str:
    """Format a bundle of agent results into a readable string for the orchestrator."""
    lines = []
    for r in bundle:
        if r["status"] == "completed":
            icon = "✓"
            body = r.get("result", "")
        elif r["status"] == "needs_confirmation":
            icon = "⚠"
            body = r.get("result", "")
        else:  # failed
            icon = "✗"
            body = r.get("error", "unknown error")
        lines.append(f"[{r['agent']}] {icon} {body}")
    return "\n".join(lines)


# ─── Main loop ────────────────────────────────────────────────────────────────

async def main_loop() -> None:
    session = Session()

    _proactive_ready = asyncio.Event()
    current_ww_stop_event: threading.Event | None = None

    #agent-results callback
    async def on_agent_results(bundle: list[dict]) -> None:
        formatted = _format_results(bundle)
        print(f"\n📦 Agent results received:\n{formatted}")
        await set_state("thinking")
        await invoke_orchestrator(session, agent_results=formatted)
        await wait_until_done_speaking()
        _proactive_ready.set()

    # Start persistent background workers
    tts_task     = asyncio.create_task(tts_worker())
    bundler_task = asyncio.create_task(results_bundler(on_agent_results))

    # ─── Main wakeword → conversation loop ───────────────────────────────────
    while True:
        try:
            print("\n💤 Waiting for Wake Word ('Hey Mycroft')...")
            await set_state("sleeping")
            _proactive_ready.clear()

            ww_stop_event  = threading.Event()
            current_ww_stop_event = ww_stop_event
            ww_task        = asyncio.create_task(
                asyncio.to_thread(wakeword.listen_for_wake_word, stop_event=ww_stop_event)
            )
            proactive_task = asyncio.create_task(_proactive_ready.wait())

            done, pending = await asyncio.wait(
                [ww_task, proactive_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            if proactive_task in done:
                ww_stop_event.set()
                try:
                    await ww_task
                except Exception:
                    pass

                print("\n🔔 Proactive update delivered — listening for follow-up...")
                _proactive_ready.clear()
                current_timeout = TIMEOUT_FOLLOWUP

            else:
                proactive_task.cancel()
                try:
                    await proactive_task
                except asyncio.CancelledError:
                    pass

                try:
                    detected = ww_task.result()
                except Exception:
                    continue

                if not detected:
                    continue

                print("⚡ Wake Word Detected!")
                await set_state("wakeword")
                current_timeout = TIMEOUT_INITIAL

            # ─── Inner conversation loop ──────────────────────────────────────
            while True:
                # Wait for any ongoing speech before opening mic
                await wait_until_done_speaking()

                await set_state("listening")
                user_input = await asyncio.to_thread(
                    take_command, timeout=current_timeout
                )

                if user_input is None:
                    print(f"⏳ Timeout ({current_timeout}s) — returning to sleep.")
                    await set_state("sleeping")
                    break

                print(f"\n🎙️ User: {user_input}")
                await set_state("thinking")

                await invoke_orchestrator(session, user_input=user_input)

                current_timeout = TIMEOUT_FOLLOWUP

        except asyncio.CancelledError:
            print("\n🛑 Mycroft shutting down...")
            if current_ww_stop_event:
                current_ww_stop_event.set()
            await set_state("sleeping")
            await stop_tts_worker()
            tts_task.cancel()
            bundler_task.cancel()
            break

        except KeyboardInterrupt:
            break

        except Exception as e:
            print(f"❌ Error in main loop: {e}")
            import traceback; traceback.print_exc()


# ─── Standalone entry point ───────────────────────────────────────────────────

if __name__ == "__main__":
    asyncio.run(main_loop())
