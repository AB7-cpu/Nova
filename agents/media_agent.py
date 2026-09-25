"""
agents/media_agent.py
======================
Media Playback Agent:

No internal LLM. The orchestrator writes specific task descriptions, so a
simple keyword classifier is reliable enough for all common media operations.

Pipeline:
  task string → _classify_intent() → action handler → AgentResult

Playback:
  yt-dlp (in thread) → CDN stream URL → mpv subprocess → audio plays

State:
  Class-level — _mpv_proc and _current_title persist across calls.
  This is intentional: pause/skip need access to the running process.

"""

import re
import os
import asyncio
import subprocess
import shutil
import tempfile
import psutil
import sys
from pathlib import Path
from agents.base import AgentResult
from tools.media_tools import get_audio_stream


if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass



# ─── mpv executable location ──────────────────────────────────────────────────

_MPV = shutil.which("mpv") or shutil.which("mpv.exe") or "mpv"

_PID_FILE = Path(tempfile.gettempdir()) / "nova_mpv.pid"



# ─── Intent classification ────────────────────────────────────────────────────

def _classify(task: str) -> str:
    t = task.lower()
    if any(k in t for k in ["pause", "stop music", "stop the music", "stop playing", "stop playback"]):
        return "pause"
    if any(k in t for k in ["resume", "continue playing", "unpause", "play again"]):
        return "resume"
    if any(k in t for k in ["skip", "next track", "next song", "next one"]):
        return "skip"
    if any(k in t for k in ["volume", "louder", "quieter", "softer", "lower volume", "raise volume"]):
        return "volume"
    if any(k in t for k in ["what", "now playing", "current song", "current track", "what's playing"]):
        return "status"
    if any(k in t for k in ["play", "put on", "start", "queue", "find me", "listen to"]):
        return "play"
    return "unknown"


def _extract_query(task: str) -> str:
    """Strip command verbs from the task to get the bare search query."""
    t = task.strip()
    t = re.sub(
        r"^(?:play|put on|start playing|queue up|find and play|search for|"
        r"find me|please play|i want to listen to|play me|listen to)\s+",
        "", t, flags=re.IGNORECASE,
    ).strip()
    t = re.sub(
        r"\s+(?:for me|please|now|right now|immediately)\s*$",
        "", t, flags=re.IGNORECASE,
    ).strip()
    return t or task


def _extract_volume(task: str) -> int:
    """
    Parse target volume (0-100) from the task string.
    Returns -1 for "louder", -2 for "quieter" (relative signals).
    """
    m = re.search(r"(\d+)\s*(?:%|percent)?", task)
    if m:
        return max(0, min(100, int(m.group(1))))
    t = task.lower()
    if any(k in t for k in ["louder", "raise", "increase", "higher"]):
        return -1
    if any(k in t for k in ["quieter", "softer", "lower", "decrease"]):
        return -2
    return 50  # safe fallback


# ─── Agent class ──────────────────────────────────────────────────────────────

class MediaAgent:

    _mpv_proc: subprocess.Popen | None = None
    _current_title: str = ""

    # ─── Public entry point ───────────────────────────────────────────────────

    @classmethod
    async def run(cls, task: str) -> AgentResult:
        intent = _classify(task)
        print(f"[MediaAgent] Intent={intent} | {task[:70]}")

        if intent == "play":
            return await cls._play(_extract_query(task))
        elif intent == "pause":
            return cls._pause(task)
        elif intent == "resume":
            return cls._resume(task)
        elif intent == "skip":
            return cls._skip(task)
        elif intent == "volume":
            return await cls._set_volume(_extract_volume(task), task)
        elif intent == "status":
            return cls._status(task)
        else:
            return AgentResult(
                agent="media_agent",
                task=task,
                status="failed",
                error=f"Could not understand media command: '{task[:60]}'",
            )

    # ─── Action handlers ──────────────────────────────────────────────────────

    @classmethod
    async def _play(cls, query: str) -> AgentResult:
        # 1. Extract direct CDN audio stream URL via yt-dlp (blocking -> thread)
        try:
            print(f"[MediaAgent] Searching: '{query}'")
            cdn_url, title = await asyncio.to_thread(get_audio_stream, query)
            print(f"[MediaAgent] Found: {title}")
        except Exception as e:
            return AgentResult(
                agent="media_agent", task=query, status="failed",
                error=f"Could not find '{query}' on YouTube: {e}",
            )

        # 2. Stop any existing playback (in-process AND cross-process via PID file)
        cls._stop_any_existing_mpv()

        # 3. Launch mpv with the CDN URL.
        popen_kwargs: dict = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if sys.platform == "win32":
            popen_kwargs["creationflags"] = 0x00000008 | 0x00000200

        try:
            cls._mpv_proc = subprocess.Popen(
                [_MPV, "--no-video", "--really-quiet", "--no-terminal", cdn_url],
                **popen_kwargs,
            )
            cls._current_title = title
            cls._save_pid()

            await asyncio.sleep(0.4)
            if cls._mpv_proc.poll() is not None:
                return AgentResult(
                    agent="media_agent", task=query, status="failed",
                    error=f"mpv exited immediately. Check that mpv.EXE is valid. (path: {_MPV})",
                )

            print(f"[MediaAgent] Now playing: {title}")
            return AgentResult(
                agent="media_agent", task=query, status="completed",
                result=f"Playing '{title}'",
            )
        except FileNotFoundError:
            return AgentResult(
                agent="media_agent", task=query, status="failed",
                error=(
                    "mpv not found. Please install mpv from https://mpv.io and "
                    "add mpv.exe to your system PATH (or place it in the project folder)."
                ),
            )


    @classmethod
    def _pause(cls, task: str) -> AgentResult:
        title = cls._current_title
        stopped = cls._stop_any_existing_mpv()
        cls._current_title = ""
        if stopped:
            return AgentResult(
                agent="media_agent", task=task, status="completed",
                result=f"Stopped '{title}'." if title else "Playback stopped.",
            )
        return AgentResult(
            agent="media_agent", task=task, status="completed",
            result="Nothing is currently playing.",
        )

    @classmethod
    def _resume(cls, task: str) -> AgentResult:
        return AgentResult(
            agent="media_agent", task=task, status="failed",
            error="Resume is not yet supported. Ask me to play a specific track.",
        )

    @classmethod
    def _skip(cls, task: str) -> AgentResult:
        cls._stop_any_existing_mpv()
        cls._current_title = ""
        return AgentResult(
            agent="media_agent", task=task, status="completed",
            result="Skipped. Ask me to play something new.",
        )


    @classmethod
    async def _set_volume(cls, level: int, task: str) -> AgentResult:
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL

            devices   = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            vol_ctrl  = cast(interface, POINTER(IAudioEndpointVolume))

            # Resolve relative levels
            if level < 0:
                current = int(vol_ctrl.GetMasterVolumeLevelScalar() * 100)
                level   = min(100, current + 15) if level == -1 else max(0, current - 15)

            vol_ctrl.SetMasterVolumeLevelScalar(level / 100.0, None)
            return AgentResult(
                agent="media_agent", task=task, status="completed",
                result=f"Volume set to {level}%.",
            )
        except Exception as e:
            return AgentResult(
                agent="media_agent", task=task, status="failed",
                error=f"Could not set volume: {e}",
            )

    @classmethod
    def _status(cls, task: str) -> AgentResult:
        in_proc = cls._mpv_proc and cls._mpv_proc.poll() is None
        in_pid  = _PID_FILE.exists() and cls._pid_file_alive()
        if in_proc or in_pid:
            msg = f"Currently playing '{cls._current_title}'." if cls._current_title else "Something is playing."
        else:
            msg = "Nothing is currently playing."
        return AgentResult(
            agent="media_agent", task=task, status="completed",
            result=msg,
        )


    # ─── Internal helpers ─────────────────────────────────────────────────────

    @classmethod
    def _save_pid(cls) -> None:
        """Write running mpv PID to file so it survives process restarts."""
        if cls._mpv_proc:
            try:
                _PID_FILE.write_text(str(cls._mpv_proc.pid))
            except Exception:
                pass

    @classmethod
    def _pid_file_alive(cls) -> bool:
        """Return True if the PID in the PID file refers to a living mpv process."""
        try:
            pid = int(_PID_FILE.read_text().strip())
            proc = psutil.Process(pid)
            return "mpv" in proc.name().lower() and proc.is_running()
        except Exception:
            return False

    @classmethod
    def _stop_any_existing_mpv(cls) -> bool:
        killed = False

        # 1. Kill the in-process tracked process
        if cls._mpv_proc:
            try:
                if cls._mpv_proc.poll() is None:  # still running
                    cls._mpv_proc.terminate()
                    cls._mpv_proc.wait(timeout=3)
                    killed = True
            except Exception:
                try:
                    cls._mpv_proc.kill()
                    killed = True
                except Exception:
                    pass
            cls._mpv_proc = None

        # 2. Kill any mpv from a previous process (PID file)
        if _PID_FILE.exists():
            try:
                pid  = int(_PID_FILE.read_text().strip())
                proc = psutil.Process(pid)
                if "mpv" in proc.name().lower():
                    proc.terminate()
                    try:
                        proc.wait(timeout=2)
                    except psutil.TimeoutExpired:
                        proc.kill()
                    killed = True
            except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError, OSError):
                pass
            try:
                _PID_FILE.unlink()
            except Exception:
                pass

        return killed
