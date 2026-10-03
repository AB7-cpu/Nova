# 🎙️ MyCroft (aka Nova) — Voice-First Multi-Agent Conversational AI Assistant

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/Framework-FastAPI%20%7C%20LangChain%20%7C%20LangGraph-brightgreen.svg)](https://www.langchain.com/)
[![LLM Backend](https://img.shields.io/badge/LLM-Groq%20Cloud%20%7C%20Local%20Ollama-orange.svg)](https://ollama.com/)
[![Audio Pipeline](https://img.shields.io/badge/Audio-VAD%20%7C%20Faster--Whisper%20%7C%20VibeVoice-purple.svg)](https://github.com/SYSTRAN/faster-whisper)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Nova** is an end-to-end, voice-first intelligent co-pilot engineered for real-time natural language interaction, asynchronous multi-agent orchestration, and native system automation. Designed as a project at the intersection of **Applied Machine Learning**, **Distributed Multi-Agent Systems**, and **Real-Time Human-Computer Interaction (HCI)**, Nova bridges local neural inference on edge devices with high-throughput cloud LLM acceleration.

Unlike conventional chatbots that operate through rigid text turn-taking, Nova features a continuous audio streaming loop with zero-latency voice activity detection, background parallel agent execution with proactive speech delivery, a dynamic hybrid edge-cloud router, and a 3-tier security sandbox for natural language operating system control.

---

## 🏛️ System Architecture

<p align="center">
  <img src="docs/System%20Architecture.png" alt="System Architecture" width="100%">
</p>

---

## 🌟 Key Technical Capabilities

### 1. Zero-Cloud Audio Pipeline (VAD + Local Whisper + VibeVoice)
- **Neural Wake-Word Detection**: Runs on-device ONNX runtime (`openWakeWord`) targeting `"Hey Mycroft"` with sub-100ms inference and thread-safe stream cancellation.
- **Voice Activity Detection (VAD)**: Utilizes `webrtcvad` frame analysis to dynamically detect speech boundaries, avoiding arbitrary recording cut-offs or button pushes.
- **Local Transcription**: Powered by `faster-whisper` (CTranslate2 FP16 on CUDA with INT8 CPU fallback) for instantaneous in-memory voice-to-text.
- **Streaming Local TTS**: Locally hosted kokoro tts via Voicebox or a persistent WebSocket client connecting to `VibeVoice`, enabling instant sentence-buffered playback before full thought completion.

### 2. Asynchronous Multi-Agent Dispatch & Proactive Bundling
- **Fire-and-Forget Parallelism**: When handling complex requests (e.g. *"Play jazz music, search for tomorrow's weather, and check free disk space"*), the orchestrator decomposes tasks and spawns multiple asynchronous sub-agents in parallel.
- **Time-Windowed Results Bundler**: Rather than overwhelming the user with fragmented spoken interruptions, a background collector aggregates agent completions across a configurable 5-second bundling window, synthesizing a coherent proactive voice update.
- **Non-Blocking Conversation Flow**: Users can continue conversing while long-running background research or file processing tasks execute in independent threads.

### 3. Dynamic Edge-Cloud Hybrid Router
- **Hybrid Mode**: Leverages ultra-fast cloud inference (**Groq** with `openai/gpt-oss-20b` or `llama-3.3-70b-versatile`). If network conditions degrade or response time exceeds **15 seconds**, the system automatically falls back to local **Ollama** (`lfm2.5`) with zero session interruption.
- **100% Offline Mode**: Bypasses cloud endpoints entirely, executing all orchestration, agent reasoning, and synthesis on private local weights.
- **Live Mode Switching**: Switchable on-the-fly via the Web UI dashboard without restarting server or speech workers.

### 4. Natural Language Shell Agent with 3-Tier Security
Translates plain-English operating system directives into Windows PowerShell cmdlets with robust guardrails:
- **`BLOCKED`**: High-risk system actions (volume formatting, `System32` tampering, SAM registry access) are rejected at code generation.
- **`DESTRUCTIVE`**: Potentially irreversible actions (`Remove-Item`, process kills, system restart/shutdown) trigger a `needs_confirmation` state, prompting the user for vocal or UI consent before execution.
- **`SAFE`**: Non-destructive operations (application launching, querying system telemetry, reading directory trees) execute with an enforced 15-second process timeout and output truncation.

### 5. ReAct Deep Search Agent
- Autonomous multi-step research agent using `langchain.agents` and the Tavily Search API.
- Generates targeted queries, inspects retrieved snippets, determines if secondary searches are warranted, and synthesizes key findings into clear prose optimized for speech output.

### 6. Media Streaming Engine
- YouTube audio stream URL extraction via `yt-dlp` metadata fetching.
- Direct playback through a headless, detached `mpv` player instance with cross-process PID lifecycle tracking, volume control, and graceful track replacement.

---

## 📂 Repository Structure

```
├── agents/                       # Specialized Autonomous Sub-Agents
│   ├── base.py                   # Pydantic AgentResult schema
│   ├── search_agent.py           # ReAct research agent (Tavily + synthesis)
│   ├── shell_agent.py            # PowerShell automation with 3-tier security
│   ├── media_agent.py            # YouTube audio stream extraction & mpv engine
│   └── system_agent.py           # System telemetry & hardware control agent
│
├── core/                         # Orchestrator & Concurrency Runtime
│   ├── orchestrator.py           # Central reasoning engine & tool binding
│   ├── dispatcher.py             # Asynchronous task dispatch & queue routing
│   ├── results_bundler.py        # Time-windowed multi-agent result aggregation
│   ├── speak_queue.py            # Non-blocking thread-safe speech FIFO queue
│   ├── session.py                # Context history & token compression manager
│   └── context_builder.py        # System telemetry, date/time, & state injection
│
├── llm/                          # Edge-Cloud Inference & Routing
│   ├── router.py                 # Dynamic Hybrid/Offline RouterLLM with fallback
│   ├── online_llm.py             # Groq & Google Gemini client bindings
│   └── ollama_llm.py             # Local Ollama client (lfm2.5 / Qwen)
│
├── stt/                          # Speech Recognition & Voice Activity Detection
│   └── whisper_stt.py            # WebRTC VAD + faster-whisper in-memory transcriber
│
├── tts/                          # Text-to-Speech Streaming Engines
│   ├── kokoro_tts.py             # Kokoro TTS client via local Voicebox HTTP stream
│   └── vibes_tts.py              # WebSocket streaming client for VibeVoice engine
│
├── wakeword/                     # Neural Wake-Word Detection
│   └── wakeword_open.py          # ONNX openWakeWord with thread-safe cancellation
│
├── frontend/                     # Web Dashboard & Monitoring
│   ├── server.py                 # FastAPI server (REST + WebSockets)
│   ├── bridge.py                 # Async state bridge to browser clients
│   └── static/                   # HTML5, Vanilla CSS Design System, Web Audio JS
│       ├── index.html            # Glassmorphic UI with animated waveform & controls
│       ├── style.css             # Dark theme design system with micro-animations
│       └── app.js                # WebSocket client & real-time audio animation
│
├── prompts/                      # Curated System & Agent Prompts
│   ├── orchestrator_prompt.py    # Voice persona, dispatch rules, & tool protocols
│   └── agents_prompt.py          # Prompts for search synthesis and PowerShell mapping
│
├── tools/                        # Tool definitions & schemas
│   ├── orchestrator_tools.py     # Pydantic schemas for speak() and spawnAgent()
│   ├── search_tools.py           # Tavily web search tool wrappers
│   └── media_tools.py            # yt-dlp audio stream extraction helpers
│
├── docs/                         # Architecture Documentation & Visual Assets
│   ├── Architecture Diagram.png      # Architecture Diagram
│   ├── Router Pipeline.png       # Router pipeline diagram image
│   └── System Architecture.png   # Architecture schematic diagram
│
├── config.py                     # Central configuration & environment source of truth
├── main.py                       # CLI headless entry point & audio event loop
├── requirements.txt              # Production dependency specifications
└── .env.example                  # Environment configuration template
```

---

## 🛠️ Tech Stack & Engineering Highlights

| Component | Technology | Rationale |
| :--- | :--- | :--- |
| **Language** | Python 3.10+ | Native `asyncio` ecosystem, rich AI/ML runtime support |
| **Agent Framework** | LangChain Core / LangGraph | Structured tool-calling, ReAct graphs, declarative schemas |
| **Cloud LLMs** | Groq (Llama-3.3-70B, GPT-OSS-20B) | Sub-300ms Time-to-First-Token (TTFT) via LPU hardware |
| **Local LLMs** | Ollama (`lfm2.5`, `qwen`) | High-privacy light-weight local reasoning without external network reliance |
| **STT Engine** | Faster-Whisper (CTranslate2) | 4x speedup over vanilla Whisper with minimal VRAM footprint |
| **Wake Word** | openWakeWord (ONNX Runtime) | Low-overhead background CPU inference with zero false wakes |
| **Web Server** | FastAPI, Uvicorn, WebSockets | Non-blocking async I/O, bidirectional real-time state push |
| **Frontend** | Vanilla HTML5 / Modern CSS / JS | Zero-dependency glassmorphism dashboard with 60 FPS waveform |

### Key Engineering Challenges Solved:
1. **Audio Device Contention & Deadlock Prevention**: Solved OS-level audio device locking between background PyAudio wake-word threads and foreground SoundDevice STT recording by implementing cooperative threading events (`stop_event`) and deterministic audio stream tear-down.
2. **Deterministic Fallback Under Latency Constraints**: Designed a custom `RouterLLM` wrapper supporting LangChain's `bind_tools` protocol that enforces a 15-second hard deadline on cloud requests before seamlessly falling back to local Ollama without dropping tool call structures.
3. **Detached Background Process Management**: Overcame Windows Job Object process group tree termination constraints by launching the `mpv` media playback engine with detached process flags, ensuring audio streams persist across interactive turns.

---

## 🚀 Getting Started

### 1. Prerequisites
- **OS**: Windows 10/11 (for native PowerShell integration and mpv audio player)
- **Python**: Version 3.10 or higher
- **Ollama**: Installed and running locally with the target model:
  ```bash
  ollama pull lfm2.5
  ```
- **External Media Player**: [mpv](https://mpv.io/) installed (or placed in project directory).

### 2. Installation
Clone the repository and initialize the Python virtual environment:
```powershell
git clone https://github.com/AB7-cpu/MyCroft.git
cd MyCroft

python -m venv venv
.\venv\Scripts\activate

pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy the template and populate your API credentials:
```powershell
cp .env.example .env
```
Edit `.env`:
```ini
GROQ_API_KEY=gsk_your_groq_api_key_here
TAVILY_API_KEY=tvly-your_tavily_api_key_here
GOOGLE_API_KEY=your_optional_gemini_key_here
OLLAMA_BASE_URL=http://localhost:11434
VIBESVOICE_URI=ws://localhost:3000
```

### 4. Running Nova

#### Option A: Web Dashboard (Recommended)
Start the FastAPI server and open the browser interface:
```powershell
python frontend/server.py
```
Open **`http://localhost:8000`** in your browser to view the interactive control panel, monitor live states (Sleeping, Listening, Thinking, Speaking), and switch between **Hybrid** and **Offline** model routing.

#### Option B: Headless Terminal CLI
Run Nova directly in the console:
```powershell
python main.py
```

Say **"Hey Mycroft"** to activate Nova, followed by your command!

---

## 💡 Example Queries & Interactions

| Category | Example Voice Prompt | Underlying Execution |
| :--- | :--- | :--- |
| **System Automation** | *"Open Task Manager and check my available RAM"* | `shell_agent` synthesizes safe PowerShell commands; returns parsed telemetry. |
| **Destructive Guardrail** | *"Delete all temporary files in my downloads folder"* | `shell_agent` classifies command as `DESTRUCTIVE`; Nova halts and prompts: *"This command will delete files. Are you sure you want to proceed?"* |
| **Web Research** | *"Who won the most recent F1 Grand Prix and what was the gap?"* | `search_agent` performs multi-step Tavily queries and returns synthesised prose. |
| **Media Playback** | *"Play lo-fi hip hop beats on YouTube"* | `media_agent` extracts CDN audio stream and streams via detached `mpv`. |
| **Complex Multi-Agent** | *"Play classical piano, and check the latest news on quantum computing"* | Dispatches `media_agent` and `search_agent` in parallel; starts music and delivers synthesized news. |

---

## 📑 Additional Documentation
- **[PROJECT_DOCS.md](PROJECT_DOCS.md)**: Deep-dive setup guide, API endpoints, audio configuration, and troubleshooting.
- **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)**: Technical architecture specification, threading model, and agent design patterns.
- **[NOVA_ARCHITECTURE.md](docs/NOVA_ARCHITECTURE.md)**: Comprehensive architectural whitepaper with component breakdown.

---

## 📜 License
This project is open-source under the [MIT License](LICENSE).
