"""
agents/search_agent.py
======================
Search Agent:

Uses the modern `create_agent` factory from `langchain.agents`.

Agent loop:
  1. Receives the task description from the orchestrator
  2. Calls Tavily search (1-3 times based on what it finds)
  3. Synthesises the results into a plain-prose answer
  4. Returns when no more tool calls are made

The synthesised result goes back to the orchestrator, which then speaks it.
"""

import asyncio
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from agents.base import AgentResult
from tools.search_tools import search_tool
from prompts.agents_prompt import search_agent_prompt
from llm.ollama_llm import get_ollama

AGENT_TIMEOUT_SECONDS = 60
MAX_RECURSION = 10  # max graph steps (LLM calls + tool calls) before giving up


class SearchAgent:
    """
    Each ainvoke() call is stateless — no shared memory between tasks.
    """

    _agent = None

    @classmethod
    def _get_agent(cls):
        if cls._agent is None:
            from llm.router import RouterLLM
            cls._agent = create_agent(
                model=RouterLLM(),
                tools=[search_tool],
                system_prompt=search_agent_prompt,
            )
        return cls._agent

    @classmethod
    async def run(cls, task: str) -> AgentResult:
        print(f"[SearchAgent] Starting: {task[:80]}")

        try:
            agent = cls._get_agent()

            result = await asyncio.wait_for(
                agent.ainvoke(
                    {"messages": [HumanMessage(content=task)]},
                    config={"recursion_limit": MAX_RECURSION},
                ),
                timeout=AGENT_TIMEOUT_SECONDS,
            )

            messages = result.get("messages", [])
            if not messages:
                raise ValueError("Agent returned no messages")

            final = messages[-1]
            answer = final.content if hasattr(final, "content") else str(final)

            # Guard: if last message has tool_calls, agent stopped mid-loop
            if not answer.strip() or (hasattr(final, "tool_calls") and final.tool_calls):
                raise ValueError("Agent loop ended without producing a final answer")

            print(f"[SearchAgent] Done: {answer[:120]}...")
            return AgentResult(
                agent="search_agent",
                task=task,
                status="completed",
                result=answer,
            )

        except asyncio.TimeoutError:
            err = f"Search timed out after {AGENT_TIMEOUT_SECONDS}s — likely a network issue."
            print(f"[SearchAgent] Timeout: {err}")
            return AgentResult(
                agent="search_agent",
                task=task,
                status="failed",
                error=err,
            )

        except Exception as e:
            print(f"[SearchAgent] Error: {e}")
            return AgentResult(
                agent="search_agent",
                task=task,
                status="failed",
                error=str(e),
            )
