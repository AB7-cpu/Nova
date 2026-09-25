import io
import asyncio
import requests
from pydub import AudioSegment
from pydub.playback import play

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import TTS

# ---------------------------------------------------------------------------
# Voicebox / Kokoro config
# ---------------------------------------------------------------------------
VOICEBOX_URL = getattr(TTS, "VOICEBOX_URL", "http://127.0.0.1:17493/generate/stream")
PROFILE_ID   = getattr(TTS, "VOICEBOX_PROFILE_ID", "a441e093-3f50-491d-b764-532040510eb3")
# ---------------------------------------------------------------------------


def fetch_audio(text: str) -> bytes | None:
    """
    HTTP only: sends text to Voicebox and returns the raw WAV bytes.
    """
    if not text.strip():
        return None

    payload = {
        "profile_id":       PROFILE_ID,
        "text":             text,
        "language":         "en",
        "seed":             0,
        "engine":           "kokoro",
        "personality":      False,
        "max_chunk_chars":  800,
        "crossfade_ms":     50,
        "normalize":        True,
        "effects_chain":    [],
    }

    try:
        response = requests.post(VOICEBOX_URL, json=payload, timeout=60)
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"[kokoro_tts] HTTP error: {e}")
        return None
    except Exception as e:
        print(f"[kokoro_tts] fetch error: {e}")
        return None


def play_audio(audio_bytes: bytes) -> None:
    """
    Playback only: plays raw WAV bytes via pydub.
    """
    if not audio_bytes:
        return
    try:
        audio = AudioSegment.from_file(
            io.BytesIO(audio_bytes),
            format="wav",
        )
        play(audio)
    except Exception as e:
        print(f"[kokoro_tts] Playback error: {e}")


def _speak_blocking(text: str) -> None:
    audio_bytes = fetch_audio(text)
    if audio_bytes:
        play_audio(audio_bytes)


async def speak_async(text: str, voice: str = "kokoro") -> None:
    if not text.strip():
        return

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _speak_blocking, text)


def speak(text: str, voice: str = "kokoro") -> None:
    asyncio.run(speak_async(text, voice))



if __name__ == "__main__":
    speak("Hello! Kokoro TTS is working through Voicebox.")
