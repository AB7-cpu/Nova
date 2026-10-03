# 📘 Nova Project Documentation & User Guide

Welcome to the comprehensive reference and user manual for **Nova**, a voice-first, multi-agent artificial intelligence assistant built for high-speed local and hybrid interaction.

---

## 📋 Table of Contents
1. [Architecture & Workflow](#1-architecture--workflow)
2. [Configuration & Environment Setup](#2-configuration--environment-setup)
3. [Component Deep Dive](#3-component-deep-dive)
   - [Voice & Audio Pipeline](#voice--audio-pipeline)
   - [Core Orchestrator](#core-orchestrator)
   - [Dynamic LLM Router](#dynamic-llm-router)
   - [Specialized Sub-Agents](#specialized-sub-agents)
   - [Results Bundler & Proactive Flow](#results-bundler--proactive-flow)
4. [Frontend & WebSocket API](#4-frontend--websocket-api)
5. [Step-by-Step Installation & Deployment](#5-step-by-step-installation--deployment)
6. [Troubleshooting & Diagnostics](#6-troubleshooting--diagnostics)

---

## 1. Architecture & Workflow

Nova operates on a decoupled, asynchronous, voice-first pipeline designed to minimize human perceived latency (Time-to-First-Word) while supporting concurrent long-running background tasks.

### Turn-Taking Lifecycle:
1. **Idle State**: The system listens for the neural wake-word (`"Hey Mycroft"`) using an ONNX-optimized model running continuously in background memory with minimal CPU footprint (<2%).
2. **Wake Detection**: Upon detection, the wake-word thread safely yields the audio hardware and alerts the user (visual feedback and audio chime).
3. **Voice Activity Detection & Transcription**:
   - WebRTC VAD continuously tracks voice energy chunks.
   - When speech ceases for >0.8s, the audio frame buffer is passed to `faster-whisper` (CTranslate2 FP16 on GPU, with INT8 CPU fallback) for in-memory transcription.
4. **Orchestrator Execution**:
   - The transcribed text is sent to the central Orchestrator.
   - The Orchestrator evaluates the query against conversational history and active system context (date, time, battery level).
   - If direct speech is required, it immediately invokes `speak(text)`.
   - If complex tasks are requested, it invokes `spawnAgent(agents=[...])` to dispatch sub-agents in parallel.
5. **Parallel Background Execution**:
   - Sub-agents (`search_agent`, `shell_agent`, `media_agent`) run concurrently in non-blocking worker threads.
   - When each agent completes, its structured `AgentResult` is enqueued into the `results_queue`.
6. **Proactive Results Bundling**:
   - The `results_bundler` gathers completions across a 5-second window.
   - Once all active tasks finish or the window elapses, the bundled results are reinjected into the Orchestrator.
   - The Orchestrator generates a concise, spoken summary, queues it for speech synthesis, and transitions into a follow-up listening window.

---

## 2. Configuration & Environment Setup

All system settings are consolidated in [`config.py`](config.py) and dynamically read from the `.env` file.

### Environment Variables (`.env`)

| Variable | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| `GROQ_API_KEY` | `string` | API key for high-speed cloud LLM inference via Groq | Yes (Hybrid) | None |
| `TAVILY_API_KEY` | `string` | API key for live web search and deep research | Yes (Search) | None |
| `GOOGLE_API_KEY` | `string` | Fallback cloud API key for Google Gemini | No | None |
| `VOICEBOX_URL`   | `string` | Local HTTP endpoint for Voicebox / Kokoro TTS stream | Optional | `http://127.0.0.1:17493/generate/stream` |
| `VOICEBOX_PROFILE_ID` | `string` | Voice profile ID for Voicebox synthesis | Optional | Default profile |
| `VIBESVOICE_URI` | `string` | WebSocket URI for local VibeVoice TTS engine | Optional | `ws://localhost:3000` |
| `WLED_IP` | `string` | Network IP address of WLED addressable RGB strip | Optional | `192.168.1.20` |

---

## 3. Component Deep Dive

### Voice & Audio Pipeline

#### Wake-Word Detection (`wakeword/wakeword_open.py`)
- **Engine**: `openwakeword` using ONNX Runtime.
- **Model**: Pre-trained `"hey_mycroft"` acoustic model.
- **Thread Safety**: Operates in a blocking OS thread managed via `asyncio.to_thread`. Accepts a `stop_event: threading.Event` to ensure clean termination within 80ms when proactive speech interrupts sleep, releasing PyAudio hardware handles without resource leaks.

#### Speech-to-Text & VAD (`stt/whisper_stt.py`)
- **VAD**: `webrtcvad` configured with aggressiveness level 3 (maximum sensitivity).
- **Pre-Roll Ring Buffer**: Preserves the first 0.5s of audio prior to VAD speech confirmation so leading consonants are never clipped.
- **Transcriber**: `faster-whisper` (`base.en` or `small.en`) processing in-memory PCM buffers directly to avoid disk I/O bottlenecks.

#### Real-Time Text-to-Speech (`tts/kokoro_tts.py` & `tts/vibes_tts.py`)
- **Primary Engine (`tts/kokoro_tts.py`)**: Connects to locally hosted **Kokoro TTS via Voicebox HTTP API** (`/generate/stream`). Uses a two-stage fetch-and-play architecture (`fetch_audio` -> `play_audio` via `pydub`), eliminating event-loop blockages while rendering natural, human-like voice synthesis.
- **Alternative Engine (`tts/vibes_tts.py`)**: Persistent WebSocket client streaming raw PCM audio chunks from local **VibeVoice** directly into a thread-safe `collections.deque` and played via `sounddevice`.

---

### Core Orchestrator (`core/orchestrator.py`)

The brain of Nova. Implemented as an asynchronous LangChain reasoning unit bound with two declarative tools:
1. `speak(text: str)`: Sends natural language responses directly to the TTS speak queue.
2. `spawnAgent(agents: list[AgentTask])`: Asynchronously triggers one or more specialized sub-agents.

#### Prompt Engineering & Conversational Guidelines:
- Strips all markdown formatting, bullet points, headers, and code fences from spoken outputs.
- Uses natural acoustic pauses (`...`) and conversational cadence.
- Implements an auto-acknowledgment guard: if agents are dispatched but no speech was generated, it automatically injects a verbal confirmation (*"On it."*) so the user is never met with silence.

---

### Dynamic LLM Router (`llm/router.py`)

Provides seamless switching between cloud acceleration and local edge privacy.

<p align="center">
  <img src="docs/Router%20Pipeline.png" alt="System Architecture" width="100%">
</p>

- **`RouterLLM`**: A custom `BaseChatModel` implementation supporting LangChain's `bind_tools` protocol.
- **Timeout Protection**: Enforces an asynchronous 15-second hard deadline on cloud calls. If network packets stall or the provider errors, it automatically falls back to local Ollama (`lfm2.5`) without dropping the turn.
- **Runtime Mode Swapping**: Can be dynamically switched between `"hybrid"` and `"offline"` via REST API without server restart.

---

### Specialized Sub-Agents

#### 1. Search Agent (`agents/search_agent.py`)
- Autonomous ReAct pattern compiled with `langchain.agents.create_agent`.
- Equipped with `search_tool` (Tavily Search API).
- Capable of multi-step iterative exploration: executes up to 3 searches to verify facts, cross-reference sources, and synthesize an articulate, concise voice response.

#### 2. Shell Agent (`agents/shell_agent.py`)
- Translates natural language directives into native Windows PowerShell cmdlets.
- **Safety Classification Engine**:
  - `BLOCKED`: Immediately halts disk formatting, registry deletion, and OS-critical file manipulation (`C:\Windows`, `System32`).
  - `DESTRUCTIVE`: Inspects commands for file deletion (`Remove-Item`, `rd /s`), process termination (`Stop-Process`), or system shutdowns (`Stop-Computer`). Halts and requests user confirmation via `status="needs_confirmation"`.
  - `SAFE`: Runs directly with a 15-second process timeout and stdout truncation.

#### 3. Media Agent (`agents/media_agent.py`)
- Extracts direct YouTube audio CDN streams via `yt-dlp`.
- Spawns and tracks a detached `mpv` player instance using Windows process group isolation.
- Manages cross-turn volume adjustment, playback pausing, track switching, and graceful process termination.

---

### Results Bundler & Proactive Flow (`core/results_bundler.py`)

When agents finish their tasks:
1. Each result is published to `dispatcher.results_queue`.
2. The `results_bundler` background task opens a 5.0-second aggregation window upon arrival of the first result.
3. If all dispatched tasks in the current batch complete early, the bundler closes immediately.
4. Results are formatted with status glyphs (`✓` Completed, `⚠` Needs Confirmation, `✗` Failed) and fed back into the Orchestrator.
5. The Orchestrator delivers a unified proactive voice report, keeping conversational interruptions structured and professional.

---

## 4. Frontend & WebSocket API

The frontend provides real-time state visualization and telemetry through a FastAPI server (`frontend/server.py`).

### REST Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Serves the single-page web UI dashboard (`index.html`) |
| `GET` | `/status` | Returns system running state, current voice state, and active LLM mode |
| `POST` | `/start` | Starts the assistant main event loop in an asynchronous task |
| `POST` | `/stop` | Gracefully cancels the main loop and returns Nova to sleep |
| `GET` | `/mode` | Retrieves active routing mode (`{"mode": "hybrid" \| "offline"}`) |
| `POST` | `/mode` | Updates active routing mode on-the-fly (`{"mode": "hybrid" \| "offline"}`) |

### WebSocket Endpoint (`/ws`)
Pushes real-time state string frames to connected browser clients:
- `sleeping`: Microphone inactive; wake-word listener standing by.
- `wakeword`: "Hey Mycroft" detected; activating speech pipeline.
- `listening`: Recording active microphone audio through WebRTC VAD.
- `thinking`: Orchestrator or agents executing reasoning/inference.
- `speaking`: TTS audio rendering and actively streaming to speakers.

---

## 5. Step-by-Step Installation & Deployment

### 1. Environment Preparation
```powershell
# Create virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Install Local Dependencies
- **Ollama**: Download from [ollama.com](https://ollama.com/) and pull the local model:
  ```bash
  ollama pull lfm2.5
  ```
- **mpv Player**: Download `mpv.exe` from [mpv.io](https://mpv.io/) and add to your system `PATH` or place in the project root.

### 3. Launching Nova
Launch the unified server and web client:
```powershell
python frontend/server.py
```
Open **`http://localhost:8000`** in your browser. Click **Start** to activate the assistant.

---

## 6. Troubleshooting & Diagnostics

### Issue: Wake word does not respond after proactive update
- **Cause**: PyAudio device contention from lingering listener threads.
- **Solution**: The latest update uses cooperative `threading.Event` signaling to terminate the wake-word thread prior to opening the STT microphone. Verify that you are running the updated `wakeword/wakeword_open.py`.

### Issue: Cloud LLM latency is high or timing out
- **Cause**: Flaky network connection or API rate limit.
- **Solution**: The system will automatically fall back to Ollama after 15 seconds. You can also toggle the UI dropdown to **Offline** to force local-only processing.

### Issue: `mpv` player does not produce audio
- **Cause**: Missing `mpv.exe` binary in PATH.
- **Solution**: Run `where mpv` in PowerShell to confirm the binary is discoverable.
