# 🛠️ Nova Developer Guide & System Architecture Deep Dive

This document provides a comprehensive technical exploration of the internal architecture, engineering tradeoffs, concurrency models, and design patterns powering the **Nova Voice Assistant**. It is intended for software engineers, machine learning researchers, and academic evaluation committees assessing the codebase.

---

## 📐 Table of Contents
1. [Concurrency Architecture & Event Loops](#1-concurrency-architecture--event-loops)
2. [Audio Subsystem & Thread Synchronization](#2-audio-subsystem--thread-synchronization)
3. [The Orchestrator & Tool Calling Pattern](#3-the-orchestrator--tool-calling-pattern)
4. [Multi-Agent Dispatch & Results Bundler](#4-multi-agent-dispatch--results-bundler)
5. [RouterLLM & Dynamic Edge-Cloud Fallback](#5-routerllm--dynamic-edge-cloud-fallback)
6. [Security & Human-in-the-Loop Guardrails](#6-security--human-in-the-loop-guardrails)
7. [Context Management & Token Budgeting](#7-context-management--token-budgeting)
8. [Failure Modes & Architectural Hardening](#8-failure-modes--architectural-hardening)

---

## 1. Concurrency Architecture & Event Loops

Nova is structured around a single-threaded asynchronous event loop (`asyncio`) coordinating multiple long-running background tasks alongside non-blocking worker threads.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Asyncio Main Event Loop                         │
│                                                                        │
│   ┌────────────────────────┐              ┌────────────────────────┐   │
│   │   results_bundler()    │              │      tts_worker()      │   │
│   │  (Background Task)     │              │  (Background Task)     │   │
│   └───────────▲────────────┘              └───────────▲────────────┘   │
│               │                                       │                │
│         results_queue                            speak_queue           │
│               │                                       │                │
│   ┌───────────┴────────────┐              ┌───────────┴────────────┐   │
│   │      main_loop()       │              │  invoke_orchestrator() │   │
│   │  (Turn State Machine)  │              │  (Reasoning Runtime)   │   │
│   └───────────┬────────────┘              └────────────────────────┘   │
│               │                                                        │
└───────────────┼────────────────────────────────────────────────────────┘
                │ asyncio.to_thread()
  ┌─────────────┴─────────────┐
  │   Blocking OS Threads     │
  │  - openWakeWord Listener  │
  │  - WebRTC VAD Recorder    │
  │  - PowerShell Executions  │
  └───────────────────────────┘
```

### Key Concurrency Principles:
1. **Never Block the Event Loop**: Heavy CPU workloads (e.g. ONNX neural wake word inference, CTranslate2 speech recognition, local LLM generation, PowerShell command execution) are delegated to `asyncio.to_thread()`.
2. **Decoupled Thought and Speech**: The speech output pipeline (`tts_worker`) operates independently from the LLM reasoning loop. The model can queue speech tokens and return to thinking or spawning background agents without waiting for the audio device to complete playback.
3. **Graceful Cancellation**: All long-lived tasks register cancellation handlers to release native audio hardware buffers and sockets on application shutdown.

---

## 2. Audio Subsystem & Thread Synchronization

One of the most complex challenges in real-time voice systems is avoiding device contention between disparate audio capture libraries.

### The Wake-Word Race Condition Problem:
When Nova enters idle state, it waits for either:
- A vocal wake word (`"Hey Mycroft"` via `openwakeword`), or
- A proactive result notification delivered by a background agent (`_proactive_ready.wait()`).

In standard Python `asyncio`:
```python
# PROBLEM: Cancelling an asyncio.to_thread Task does NOT terminate the OS thread!
ww_task = asyncio.create_task(asyncio.to_thread(wakeword.listen_for_wake_word))
proactive_task = asyncio.create_task(_proactive_ready.wait())

done, pending = await asyncio.wait([ww_task, proactive_task], return_when=FIRST_COMPLETED)
for t in pending:
    t.cancel()  # OS thread continues running indefinitely!
```

If `proactive_task` finishes first, calling `ww_task.cancel()` cancels the asyncio future, but leaves the underlying PyAudio stream running in the background thread. When the assistant returns to sleep later, a second thread is launched—causing **two threads to concurrently read from the same microphone**. The audio stream is sliced into alternating frames, causing ONNX acoustic confidence to collapse.

### The Solution: Cooperative Event Signaling
In `wakeword/wakeword_open.py`, the listener accepts a `threading.Event`:
```python
def listen_for_wake_word(stop_event: threading.Event | None = None) -> bool:
    audio = pyaudio.PyAudio()
    stream = audio.open(...)
    try:
        while True:
            if stop_event and stop_event.is_set():
                return False
            data = stream.read(CHUNK, exception_on_overflow=False)
            ...
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()
        model.reset()
```
In `main.py`, when a proactive result arrives, Nova signals the event and explicitly awaits thread termination before opening the microphone for follow-up speech:
```python
ww_stop_event.set()
await ww_task  # Guarantees the OS thread exits and releases PyAudio within 80ms!
```

---

## 3. The Orchestrator & Tool Calling Pattern

The central orchestrator in `core/orchestrator.py` does not use an overly complex monolithic graph for its main conversational turn; instead, it uses a high-performance **LangChain tool-binding execution model**.

### Declarative Tool Schemas:
The LLM is bound with two structured Pydantic schemas:
- `speak(text: str)`: Emits spoken text to the user.
- `spawnAgent(agents: list[AgentTask])`: Enqueues parallel agent jobs.

```python
_llm = RouterLLM().bind_tools([_speak_tool, _spawn_agent_tool])
```

### Deterministic Conversational Rules:
1. **Zero Raw Markdown in Audio**: System prompts instruct the LLM to format output exclusively in human phonetics.
2. **Auto-Ack Protection**: If the LLM generates `spawnAgent` tool calls but forgets to invoke `speak`, the orchestrator automatically detects this state and queues an immediate vocal confirmation (`"On it."`) before running the agents, preventing acoustic dead air.
3. **Fallback Plaintext Handler**: If an offline model produces plain conversational text without structured tool calls, Nova seamlessly routes the raw text content to the speech queue.

---

## 4. Multi-Agent Dispatch & Results Bundler

Nova implements an asynchronous, fire-and-forget agent pattern via `core/dispatcher.py` and `core/results_bundler.py`.

```
Orchestrator Turn
       │
       ▼ spawnAgent(tasks)
┌──────────────────────────────────────┐
│       Parallel Task Dispatcher       │
│  ├── Task 1: SearchAgent.run()       │
│  ├── Task 2: MediaAgent.run()        │
│  └── Task 3: ShellAgent.run()        │
└──────────────────┬───────────────────┘
                   │ Enqueue AgentResult
                   ▼
┌──────────────────────────────────────┐
│           results_queue              │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│       results_bundler() Worker       │
│  - Opens 5-second bundling window    │
│  - Closes early if all tasks finish  │
└──────────────────┬───────────────────┘
                   │
                   ▼ Bundled Results
┌──────────────────────────────────────┐
│  Orchestrator Proactive Turn         │
│  "Here is what I found for you..."   │
└──────────────────────────────────────┘
```

### Advantages of Time-Windowed Bundling:
- Prevents conversational thrashing: if three agents finish at seconds 1.2, 1.8, and 2.5, Nova delivers **one unified proactive update** rather than interrupting the user three separate times.
- If all active tasks finish before the 5.0-second deadline, the bundler closes immediately to minimize response latency.

---

## 5. RouterLLM & Dynamic Edge-Cloud Fallback

The LLM abstraction in `llm/router.py` implements a custom subclass of LangChain's `BaseChatModel`.

```python
class RouterLLM(BaseChatModel):
    tools: list[Any] = Field(default_factory=list)
    bound_kwargs: dict[str, Any] = Field(default_factory=dict)
    temperature: float = 0.7
```

### Architecture Highlights:
- **Native Tool Binding**: Overrides `bind_tools()` to preserve tool definitions across both online (`ChatGroq`) and offline (`ChatOllama`) models.
- **Latency Deadline Guard**:
  ```python
  resp = await asyncio.wait_for(
      online.ainvoke(messages, stop=stop, **kwargs),
      timeout=15.0,  # Strict 15s latency budget
  )
  ```
  If cloud APIs experience packet loss, outages, or rate-limiting, the router logs a warning and routes the exact message payload to local Ollama (`lfm2.5`), ensuring continuous uptime.
- **Zero-Restart Mode Toggling**: Reads `ROUTER.MODE` dynamically on every generation, enabling the Web UI to switch system modes on the fly.

---

## 6. Security & Human-in-the-Loop Guardrails

The `ShellAgent` (`agents/shell_agent.py`) translates natural language instructions into Windows PowerShell scripts using a strict 3-tier security filter.

```
       Plain-English User Directive
                    │
                    ▼
       Ollama / Groq PS Generation
                    │
                    ▼
      Regex Security Classifier
                    │
       ┌────────────┼────────────┐
       ▼            ▼            ▼
   [BLOCKED]  [DESTRUCTIVE]    [SAFE]
       │            │            │
       │            │            ▼
       │            │     Execute with
       │            │     15s Timeout
       │            │            │
       │            ▼            ▼
       │      Return Status:   Output
       │      needs_confirm    Truncated
       │            │
       ▼            ▼
   Hard Fail   Orchestrator
  "Forbidden"  Asks User
```

### Safety Categories:
1. **BLOCKED**: Disk formatting (`Format-Volume`, `format C:`), `System32` directory modification, SAM registry access. Rejected automatically without execution.
2. **DESTRUCTIVE**: `Remove-Item`, recursive `rd /s`, `Stop-Process`, `Stop-Computer`, `Stop-Service`. Returns `AgentResult(status="needs_confirmation")`. The orchestrator verbally asks the user for confirmation. If confirmed, the command is re-dispatched with `"CONFIRMED: <cmd>"`.
3. **SAFE**: Information retrieval (`Get-ChildItem`, `Get-Process`, `Get-PSDrive`), launching executables. Runs with a 15-second subprocess timeout and an 800-character stdout truncation buffer to prevent memory bloat.

---

## 7. Context Management & Token Budgeting

Continuous voice interaction generates substantial context over long sessions. Nova's `Session` manager (`core/session.py`) maintains state while preventing context window overflow.

- **Sliding History Buffer**: Preserves immediate conversational turns.
- **Token Estimation**: Monitors total tokens consumed.
- **Post-Turn Maintenance**: Executes non-blocking context compression in the background, pruning stale intermediate agent results while preserving core conversational threads.

---

## 8. Failure Modes & Architectural Hardening

| Failure Mode | Root Cause | Engineering Mitigation |
| :--- | :--- | :--- |
| **Microphone Lockup** | Background PyAudio thread left open after asyncio task cancellation | Implemented cooperative `stop_event` flag with clean stream teardown and explicit `await ww_task` before STT acquisition. |
| **Cloud LLM Stalls** | High network latency or Groq API rate limits | Enforced 15-second timeout in `RouterLLM` with automatic fallback to local Ollama weights. |
| **Audio Clipping in TTS** | Frequent opening/closing of sound card output | Persistent sounddevice output stream with double-buffered `deque` chunk consumer. |
| **Command Buffer Bloat** | CLI tool generating thousands of output lines | Automatic stdout truncation at 800 characters with ellipsis indicators. |
| **Process Tree Killing** | Windows Job Object killing child mpv processes on Python exit | Spawned `mpv` player with detached process flags (`CREATE_NEW_PROCESS_GROUP`). |
