"""
config.py
=======================================
Single config file for all settings, model names, API endpoints,
and feature toggles across the project.

All sensitive values (API keys) are loaded from .env.
Non-sensitive defaults are defined here directly.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# LLM — Online Providers
# ---------------------------------------------------------------------------

class GroqConfig:
    API_KEY: str = os.getenv("GROQ_API_KEY", "")
    DEFAULT_MODEL: str = "openai/gpt-oss-20b"
    FALLBACK_MODEL: str = "llama-3.3-70b-versatile"
    TIMEOUT_SECONDS: int = 10  # Hard deadline before switching to offline


class GeminiConfig:
    API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    DEFAULT_MODEL: str = "gemini-2.0-flash"
    PRO_MODEL: str = "gemini-2.5-pro"
    TIMEOUT_SECONDS: int = 12

class OpenRouterConfig:
    API_KEY: str = os.getenv("OPENROUTER_API_KEY")
    DEFAULT_MODEL: str = 'liquid/lfm-2.5-2.6b:free'
    FALLBACK_MODEL: str = 'nvidia/nemotron-3-super-120b-a12b:free'
    TIMEOUT_SECONDS: int = 8


# Which online provider to use as primary: "groq" | "gemini" | "openrouter"
ONLINE_LLM_PROVIDER: str = "groq"

# ---------------------------------------------------------------------------
# LLM — Offline (Ollama)
# ---------------------------------------------------------------------------

class OllamaConfig:
    BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    DEFAULT_MODEL: str = "lfm2.5"
    EMBED_MODEL: str = "nomic-embed-text"
    TIMEOUT_SECONDS: int = 30


# ---------------------------------------------------------------------------
# LLM Router
# ---------------------------------------------------------------------------

class RouterConfig:
    # Mode: "hybrid" | "offline"
    MODE: str = os.getenv("NOVA_MODE", "hybrid")
    # How long (seconds) to wait for online LLM before falling back to Ollama
    ONLINE_TIMEOUT: int = 10
    # Whether to always try online first, or use offline when online fails
    PREFER_ONLINE: bool = (os.getenv("NOVA_MODE", "hybrid").lower() == "hybrid")
    # If True, router logs which provider was used on each call
    LOG_PROVIDER_CHOICE: bool = True


# ---------------------------------------------------------------------------
# STT (Speech-to-Text)
# ---------------------------------------------------------------------------

class STTConfig:
    WHISPER_MODEL: str = "medium.en"   # tiny.en / base.en / small.en / medium.en
    DEVICE: str = "cuda"
    COMPUTE_TYPE: str = "float16"
    SAMPLE_RATE: int = 16000
    CHANNELS: int = 1
    # VAD sensitivity (webrtcvad): 0=least aggressive, 3=most aggressive
    VAD_AGGRESSIVENESS: int = 3
    # Seconds of silence before STT considers utterance complete
    SILENCE_THRESHOLD_SEC: float = 1
    # Max seconds to wait for speech after wake word before returning to idle
    COMMAND_TIMEOUT_SEC: float = 8.0
    # Max seconds to wait for follow-up command before returning to idle
    FOLLOWUP_TIMEOUT_SEC: float = 5.0


# ---------------------------------------------------------------------------
# TTS (Text-to-Speech — Kokoro via Voicebox & VibeVoice)
# ---------------------------------------------------------------------------

class TTSConfig:
    # Primary engine: "kokoro" | "vibevoice"
    ENGINE: str = os.getenv("TTS_ENGINE", "kokoro")

    # Kokoro TTS (via local Voicebox HTTP endpoint)
    VOICEBOX_URL: str = os.getenv("VOICEBOX_URL", "http://127.0.0.1:17493/generate/stream")
    VOICEBOX_PROFILE_ID: str = os.getenv("VOICEBOX_PROFILE_ID", "a441e093-3f50-491d-b764-532040510eb3")

    # VibeVoice (via local WebSocket server)
    WS_URI: str = os.getenv("VIBESVOICE_URI", "ws://localhost:3000")
    # Reconnect delay if WebSocket drops
    RECONNECT_DELAY_SEC: float = 2.0
    INTERRUPT_ENERGY_THRESHOLD: float = 0.02


# ---------------------------------------------------------------------------
# Wake Word
# ---------------------------------------------------------------------------

class WakeWordConfig:
    MODEL_NAME: str = "hey_mycroft"
    # Confidence threshold (0–1); higher = fewer false positives
    DETECTION_THRESHOLD: float = 0.5
    CHUNK_SIZE: int = 1280


# ---------------------------------------------------------------------------
# Tools / Integrations
# ---------------------------------------------------------------------------

class ToolsConfig:
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    TAVILY_MAX_RESULTS: int = 5
    WLED_IP: str = os.getenv("WLED_IP", "192.168.1.20")
    VIBESVOICE_WS_URI: str = TTSConfig.WS_URI


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

class LogConfig:
    LEVEL: str = "INFO"             # DEBUG / INFO / WARNING / ERROR
    LOG_TO_FILE: bool = False
    LOG_FILE: str = "./logs/nova.log"
    # SQLite conversation history
    CONVERSATIONS_DB: str = "./logs/conversations.db"


# ---------------------------------------------------------------------------
# Quick-access aliases
# ---------------------------------------------------------------------------

GROQ = GroqConfig()
OPENROUTER = OpenRouterConfig()
GEMINI = GeminiConfig()
OLLAMA = OllamaConfig()
ROUTER = RouterConfig()
STT = STTConfig()
TTS = TTSConfig()
WAKE_WORD = WakeWordConfig()
TOOLS = ToolsConfig()
LOG = LogConfig()
