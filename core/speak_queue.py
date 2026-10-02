"""
core/speak_queue.py
====================
Serialised TTS delivery via an asyncio Queue.

The tts_worker is a persistent background task that drains the queue
sequentially.

speak() puts text on the queue and returns immediately.
"""

import asyncio

_speak_queue: asyncio.Queue = asyncio.Queue()

is_speaking: bool = False


async def wait_until_done_speaking() -> None:
    await _speak_queue.join()


async def enqueue_speech(text: str) -> None:
    await _speak_queue.put(text.strip())


async def tts_worker() -> None:
    global is_speaking

    from tts.kokoro_tts import fetch_audio, play_audio

    try:
        from frontend.bridge import set_state as _set_state
    except ImportError:
        async def _set_state(_: str): pass

    loop = asyncio.get_event_loop()

    while True:
        text = await _speak_queue.get()

        if text is None:
            _speak_queue.task_done()
            break

        try:
            is_speaking = True
            await _set_state("speaking")

            audio_bytes = await loop.run_in_executor(None, fetch_audio, text)

            if audio_bytes:
                await loop.run_in_executor(None, play_audio, audio_bytes)

        except Exception as e:
            print(f"⚠️  TTS error: {e}")
        finally:
            is_speaking = False
            _speak_queue.task_done()


async def stop_tts_worker() -> None:
    """Send the shutdown sentinel to the tts_worker."""
    await _speak_queue.put(None)
