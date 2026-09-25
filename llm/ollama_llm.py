"""
llm/ollama_llm.py — Offline LLM Client (Ollama)
================================================

Provides a ready-to-use LangChain ChatOllama instance for fully local
inference. Falls back to this when online LLMs are unavailable.
"""

from langchain_ollama import ChatOllama

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import OLLAMA


def get_ollama(model: str | None = None, temperature: float = 0.7, **kwargs) -> ChatOllama:
    """
    Return a ChatOllama instance.
    """
    return ChatOllama(
        model=model or OLLAMA.DEFAULT_MODEL,
        base_url=OLLAMA.BASE_URL,
        temperature=temperature,
        **kwargs,
    )


ollama_llm: ChatOllama = get_ollama()
