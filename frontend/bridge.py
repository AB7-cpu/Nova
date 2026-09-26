"""
frontend/bridge.py — State broadcaster.

States:
    "sleeping"  — waiting for wake word (no animation)
    "wakeword"  — wake word just detected (brief flash)
    "listening" — recording voice command (blue wave)
    "thinking"  — LLM processing (purple wave)
    "speaking"  — TTS playing (green wave)
"""

from typing import Set
from fastapi import WebSocket

_clients: Set[WebSocket] = set()
_current_state: str = "sleeping"


def register(ws: WebSocket) -> None:
    _clients.add(ws)


def unregister(ws: WebSocket) -> None:
    _clients.discard(ws)


def get_state() -> str:
    return _current_state


async def set_state(state: str) -> None:
    global _current_state, _clients
    _current_state = state

    dead: Set[WebSocket] = set()
    for client in _clients:
        try:
            await client.send_text(state)
        except Exception:
            dead.add(client)

    _clients -= dead
