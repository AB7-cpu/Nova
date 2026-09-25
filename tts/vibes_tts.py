
import asyncio
import websockets
import numpy as np
import sounddevice as sd
from urllib.parse import urlencode
from collections import deque

# Constants
SAMPLE_RATE = 24000
CHANNELS = 1
DTYPE = "float32"

audio_buffer = deque()
_stream = None

def audio_callback(outdata, frames, time, status):
    if status:
        print("Audio status:", status)

    samples_needed = frames
    outdata.fill(0)

    while samples_needed > 0 and audio_buffer:
        chunk = audio_buffer[0]

        take = min(len(chunk), samples_needed)
        outdata[frames - samples_needed : frames - samples_needed + take, 0] = chunk[:take]

        if take < len(chunk):
            audio_buffer[0] = chunk[take:]
        else:
            audio_buffer.popleft()

        samples_needed -= take

def start_stream():
    """Starts a persistent audio stream."""
    global _stream
    if _stream is None:
        _stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            callback=audio_callback,
            blocksize=512,
        )
        _stream.start()
        print("🔈 Audio stream started")

def stop_stream():
    """Stops the persistent audio stream."""
    global _stream
    if _stream is not None:
        _stream.stop()
        _stream.close()
        _stream = None
        audio_buffer.clear()
        print("🔇 Audio stream stopped")

async def wait_until_done():
    while audio_buffer:
        await asyncio.sleep(0.05)
    await asyncio.sleep(0.2)

async def ws_receiver(text, voice):
    params = {
        "text": text,
        "voice": voice,
        "cfg": 1.5,
        "steps": 5,
    }
    WS_URL = f"ws://localhost:3000/stream?{urlencode(params)}"

    try:
        async with websockets.connect(WS_URL, max_size=None) as ws:
            async for msg in ws:
                if isinstance(msg, bytes):
                    # PCM16 → float32
                    samples = (
                        np.frombuffer(msg, dtype=np.int16)
                        .astype(np.float32) / 32768.0
                    )
                    audio_buffer.append(samples)
    except Exception as e:
        print(f"WebSocket Error: {e}")


async def speak_async(text: str, voice: str = 'en-Mike_man'):
    if not text.strip():
        return
    
    if _stream is None:
        start_stream()
        
    await ws_receiver(text, voice)


def speak(text: str, voice: str = 'en-Mike_man'):
    if not text.strip():
        return
        
    try:
        start_stream()
        asyncio.run(speak_async(text, voice))
        asyncio.run(wait_until_done())
        stop_stream()
    except Exception as e:
        print(f"TTS Error: {e}")


if __name__ == "__main__":
    TEXT = "Hello! VibeVoice TTS is working through WebSocket."
    print(f"Speaking: {TEXT}")
    speak(TEXT)
