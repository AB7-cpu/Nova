"""
llm/online_llm.py — Online LLM Clients
=======================================

Provides ready-to-use LangChain chat model instances for:
  - Groq  (default: openai/gpt-oss-20b)
  - Google Gemini  (gemini-2.0-flash / gemini-2.5-pro)
"""

from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import GROQ, GEMINI


# ---------------------------------------------------------------------------
# Groq
# ---------------------------------------------------------------------------

def get_groq(model: str | None = None, temperature: float = 0.7, **kwargs) -> ChatGroq:
    """
    Return a ChatGroq instance.
    """
    return ChatGroq(
        model=model or GROQ.DEFAULT_MODEL,
        api_key=GROQ.API_KEY,
        temperature=temperature,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Google Gemini
# ---------------------------------------------------------------------------

def get_gemini(
    model: str | None = None,
    temperature: float = 0.7,
    **kwargs,
) -> ChatGoogleGenerativeAI:
    """
    Return a ChatGoogleGenerativeAI instance.
    """
    _model_shortcuts = {
        "flash": GEMINI.DEFAULT_MODEL,
        "pro": GEMINI.PRO_MODEL,
    }
    resolved_model = _model_shortcuts.get(model or "flash", model or GEMINI.DEFAULT_MODEL)

    return ChatGoogleGenerativeAI(
        model=resolved_model,
        google_api_key=GEMINI.API_KEY,
        temperature=temperature,
        **kwargs,
    )



groq_llm: ChatGroq | None = get_groq() if GROQ.API_KEY else None
gemini_llm: ChatGoogleGenerativeAI | None = get_gemini() if GEMINI.API_KEY else None
