"""
core/session.py
===============

Manages conversation history for the current session and compresses chat history.
"""

import asyncio
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage

MAX_TURNS        = 20   # total messages before compression
KEEP_RECENT      = 6    # how many recent messages to preserve


class Session:
    def __init__(self):
        self.history: list[BaseMessage] = []
        self._is_compressing: bool = False


    def add_user_message(self, text: str) -> None:
        self.history.append(HumanMessage(content=text))

    def add_assistant_response(self, response: AIMessage) -> None:
        """Store the raw AIMessage (includes tool_calls for history continuity)."""
        self.history.append(response)

    def add_agent_results(self, results_text: str) -> None:
        """Inject agent results as a system-style message for the next turn."""
        self.history.append(
            HumanMessage(content=f"[Agent Results]\n{results_text}")
        )

    def get_history(self) -> list[BaseMessage]:
        return list(self.history)


    def post_turn_maintenance(self) -> None:
        if len(self.history) >= MAX_TURNS and not self._is_compressing:
            asyncio.create_task(self._compress())

    # ─── Background compression ──────────────────────────────────────────────

    async def _compress(self) -> None:
        """
        Summarizes old conversation turns using a local Ollama model.
        """
        self._is_compressing = True
        try:
            from llm.ollama_llm import get_ollama
            llm = get_ollama()

            old_turns  = self.history[:-KEEP_RECENT]
            recent     = self.history[-KEEP_RECENT:]

            lines = []
            for msg in old_turns:
                if isinstance(msg, HumanMessage):
                    role = "User"
                elif isinstance(msg, AIMessage):
                    role = "Nova"
                else:
                    role = "System"
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                if content.strip():
                    lines.append(f"{role}: {content.strip()}")

            if not lines:
                return

            history_text = "\n".join(lines)
            prompt = (
                "Summarize the following conversation history in 2–3 concise sentences. "
                "Preserve key facts, preferences, and decisions mentioned.\n\n"
                f"{history_text}"
            )

            summary_response = await llm.ainvoke(prompt)
            summary_text = summary_response.content.strip()

            print(f"\n📝 History compressed ({len(old_turns)} → 1 summary message)")

            self.history = [
                SystemMessage(content=f"[Summary of earlier conversation]: {summary_text}")
            ] + recent

        except Exception as e:
            print(f"⚠️  History compression failed: {e}")
        finally:
            self._is_compressing = False
