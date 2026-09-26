"""
frontend/server.py — Nova Frontend Server
==========================================

Opens the UI at:  http://localhost:8000

Endpoints:
    GET  /       → Serves the web UI (index.html)
    WS   /ws     → WebSocket stream (pushes state strings to browser)
    POST /start  → Starts the assistant main loop as an asyncio task
    POST /stop   → Cancels the assistant main loop
"""

import asyncio
import sys
from pathlib import Path
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from frontend import bridge


_main_task: asyncio.Task | None = None

# ─── App lifecycle ────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(title="Nova Assistant", lifespan=lifespan)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    """WebSocket endpoint — browser connects here to receive state updates."""
    await websocket.accept()
    bridge.register(websocket)

    await websocket.send_text(bridge.get_state())

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        bridge.unregister(websocket)


@app.post("/start")
async def start_assistant():
    """Load models and start the assistant."""
    global _main_task

    if _main_task and not _main_task.done():
        return JSONResponse({"status": "already_running"})

    from main import main_loop
    _main_task = asyncio.create_task(main_loop())
    return JSONResponse({"status": "started"})


@app.post("/stop")
async def stop_assistant():
    """Stop the assistant."""
    global _main_task

    if _main_task and not _main_task.done():
        _main_task.cancel()
        try:
            await _main_task
        except asyncio.CancelledError:
            pass
        _main_task = None

    await bridge.set_state("sleeping")
    return JSONResponse({"status": "stopped"})


from pydantic import BaseModel
from llm.router import get_mode, set_mode


class ModePayload(BaseModel):
    mode: str


@app.get("/mode")
async def get_model_mode():
    """Return active model mode ('hybrid' or 'offline')."""
    return JSONResponse({"mode": get_mode()})


@app.post("/mode")
async def set_model_mode(payload: ModePayload):
    """Set active model mode ('hybrid' or 'offline')."""
    try:
        updated = set_mode(payload.mode)
        return JSONResponse({"status": "ok", "mode": updated})
    except ValueError as err:
        return JSONResponse({"status": "error", "message": str(err)}, status_code=400)


@app.get("/status")
async def get_status():
    """Return current running state and model mode."""
    running = _main_task is not None and not _main_task.done()
    return JSONResponse({
        "running": running,
        "state": bridge.get_state(),
        "mode": get_mode(),
    })


if __name__ == "__main__":
    print("🌐 Nova UI → http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
