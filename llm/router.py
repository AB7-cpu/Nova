"""
llm/router.py — LLM Router with Online → Offline Fallback
==========================================================

Provides dynamic routing between Online (Groq, OpenRouter) and Offline (Ollama):
  - "offline": Forces orchestrator and subagents to use local Ollama model directly.
  - "hybrid":  Tries online Groq or OpenRouter first with a timeout,
               falling back to local Ollama if (Groq, Openrouter) fails or times out.
"""

import asyncio
import logging
from typing import Any, Sequence, Union, Dict, Callable

from pydantic import Field
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.callbacks import CallbackManagerForLLMRun, AsyncCallbackManagerForLLMRun
from langchain_core.tools import BaseTool

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import ROUTER, ONLINE_LLM_PROVIDER
from llm.online_llm import get_groq, get_gemini, get_openrouter
from llm.ollama_llm import get_ollama

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mode Management
# ---------------------------------------------------------------------------

def get_mode() -> str:
    return getattr(ROUTER, "MODE", "hybrid").lower()


def set_mode(mode: str) -> str:
    """
    Set active mode ('hybrid' or 'offline').
    """
    mode_clean = mode.lower().strip()
    if mode_clean not in ("hybrid", "offline"):
        raise ValueError(f"Invalid mode '{mode}'. Must be 'hybrid' or 'offline'.")

    ROUTER.MODE = mode_clean
    ROUTER.PREFER_ONLINE = (mode_clean == "hybrid")

    logger.info("[Router] Active mode changed to: %s (prefer_online=%s)", mode_clean, ROUTER.PREFER_ONLINE)
    print(f"\n[Nova Router] Mode switched to: {mode_clean.upper()} (Online: {ROUTER.PREFER_ONLINE})", flush=True)
    return mode_clean


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_online_llm(temperature: float = 0.7) -> BaseChatModel:
    if ONLINE_LLM_PROVIDER == "gemini":
        return get_gemini(temperature=temperature)
    elif ONLINE_LLM_PROVIDER == 'openrouter':
        return get_openrouter(temperature=temperature)
    return get_groq(temperature=temperature)


def get_llm(temperature: float = 0.7) -> BaseChatModel:
    return RouterLLM(temperature=temperature)


# ---------------------------------------------------------------------------
# RouterLLM
# ---------------------------------------------------------------------------

class RouterLLM(BaseChatModel):
    tools: list[Any] = Field(default_factory=list)
    bound_kwargs: dict[str, Any] = Field(default_factory=dict)
    temperature: float = 0.7

    @property
    def _llm_type(self) -> str:
        return "nova-router"

    def bind_tools(
        self,
        tools: Sequence[Union[Dict[str, Any], type, Callable, BaseTool]],
        **kwargs: Any,
    ) -> "RouterLLM":
        return RouterLLM(
            tools=list(tools),
            bound_kwargs=kwargs,
            temperature=self.temperature,
        )

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        offline = get_ollama(temperature=self.temperature)
        if self.tools:
            offline = offline.bind_tools(self.tools, **self.bound_kwargs)

        current_mode = get_mode()

        if current_mode == "offline" or not ROUTER.PREFER_ONLINE:
            if ROUTER.LOG_PROVIDER_CHOICE:
                logger.info("[RouterLLM] Offline mode active → using Ollama")
            resp = offline.invoke(messages, stop=stop, **kwargs)
            return ChatResult(generations=[ChatGeneration(message=resp)])

        online = _get_online_llm(temperature=self.temperature)
        if self.tools:
            online = online.bind_tools(self.tools, **self.bound_kwargs)

        try:
            if ROUTER.LOG_PROVIDER_CHOICE:
                logger.info("[RouterLLM] Hybrid mode: Trying online provider (%s)...", ONLINE_LLM_PROVIDER)
            resp = online.invoke(messages, stop=stop, **kwargs)
            if ROUTER.LOG_PROVIDER_CHOICE:
                logger.info("[RouterLLM] Online provider responded ✓")
            return ChatResult(generations=[ChatGeneration(message=resp)])
        except Exception as exc:
            logger.warning(
                "[RouterLLM] Online provider failed (%s). Falling back to Ollama. Error: %s",
                ONLINE_LLM_PROVIDER,
                exc,
            )
            print(f"\n[RouterLLM Warning] Online provider failed ({exc}). Falling back to Ollama...", flush=True)
            resp = offline.invoke(messages, stop=stop, **kwargs)
            return ChatResult(generations=[ChatGeneration(message=resp)])

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        offline = get_ollama(temperature=self.temperature)
        if self.tools:
            offline = offline.bind_tools(self.tools, **self.bound_kwargs)

        current_mode = get_mode()

        if current_mode == "offline" or not ROUTER.PREFER_ONLINE:
            if ROUTER.LOG_PROVIDER_CHOICE:
                logger.info("[RouterLLM] Offline mode active → using Ollama")
            resp = await offline.ainvoke(messages, stop=stop, **kwargs)
            return ChatResult(generations=[ChatGeneration(message=resp)])

        online = _get_online_llm(temperature=self.temperature)
        if self.tools:
            online = online.bind_tools(self.tools, **self.bound_kwargs)

        timeout_sec = getattr(ROUTER, "ONLINE_TIMEOUT", 15)

        try:
            if ROUTER.LOG_PROVIDER_CHOICE:
                logger.info("[RouterLLM] Async: Trying online provider (%s)...", ONLINE_LLM_PROVIDER)
            resp = await asyncio.wait_for(
                online.ainvoke(messages, stop=stop, **kwargs),
                timeout=timeout_sec,
            )
            if ROUTER.LOG_PROVIDER_CHOICE:
                logger.info("[RouterLLM] Async: Online provider responded ✓")
            return ChatResult(generations=[ChatGeneration(message=resp)])
        except Exception as exc:
            logger.warning(
                "[RouterLLM] Async: Online failed or timed out after %ss (%s). Falling back to Ollama. Error: %s",
                timeout_sec,
                ONLINE_LLM_PROVIDER,
                exc,
            )
            print(f"\n[RouterLLM Warning] Online failed or timed out after {timeout_sec}s ({exc}). Falling back to Ollama...", flush=True)
            resp = await offline.ainvoke(messages, stop=stop, **kwargs)
            return ChatResult(generations=[ChatGeneration(message=resp)])
