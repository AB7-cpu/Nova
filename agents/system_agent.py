"""
agents/system_agent.py
======================
Dedicated agent for host system operations and hardware telemetry.
"""

from agents.base import AgentResult


class SystemAgent:
    @classmethod
    async def run(cls, task: str) -> AgentResult:
        return AgentResult(
            agent="system_agent",
            task=task,
            status="failed",
            error="SystemAgent is currently under active development."
        )
