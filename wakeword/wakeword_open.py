import openwakeword
from openwakeword.model import Model
import pyaudio
import numpy as np
import logging
import threading

logging.getLogger('openwakeword').setLevel(logging.ERROR)

# Configuration
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1280
THRESHOLD = 0.5

print("⏳ Loading Wake Word Model...")
model = Model(wakeword_models=["hey_mycroft"], inference_framework="onnx")
print("✅ Wake Word Model Loaded")

def listen_for_wake_word(stop_event: threading.Event | None = None) -> bool:
    """
    Listens continuously for the wake word 'Hey Mycroft'.
    """
    audio = pyaudio.PyAudio()
    stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    
    try:
        while True:
            if stop_event is not None and stop_event.is_set():
                return False

            # Read audio chunk
            data = stream.read(CHUNK, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16)
            
            # Feed to model
            prediction = model.predict(audio_data)
            
            # Check for wake word
            if prediction["hey_mycroft"] > THRESHOLD:
                return True
                
    except KeyboardInterrupt:
        return False
    except Exception:
        return False
    finally:
        try:
            stream.stop_stream()
            stream.close()
        except Exception:
            pass
        try:
            audio.terminate()
        except Exception:
            pass
        try:
            model.reset()
        except Exception:
            pass

if __name__ == "__main__":
    while True:
        if listen_for_wake_word():
            print("Wake word detected!")
