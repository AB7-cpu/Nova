"""
core/dispatcher.py
==================

Implements the spawnAgent() orchestrator tool.
"""

import asyncio
import uuid
import time

from agents.base import AgentResult

# ─── Shared state ─────────────────────────────────────────────────────────────

task_registry: dict[str, dict] = {}

results_queue: asyncio.Queue = asyncio.Queue()

_current_batch: set[str] = set()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _new_task_id() -> str:
    return "t_" + uuid.uuid4().hex[:8]   # e.g. "t_a3f9b2c1"


# ─── Public API ───────────────────────────────────────────────────────────────

async def spawn_agents(agents: list[dict]) -> list[str]:
    task_ids = []

    for agent_config in agents:
        task_id = _new_task_id()
        task_registry[task_id] = {
            "task_id":    task_id,
            "agent":      agent_config.get("agent", "unknown"),
            "task":       agent_config.get("task", ""),
            "priority":   agent_config.get("priority", 2),
            "status":     "running",
            "started_at": time.monotonic(),
            "result":     None,
            "error":      None,
        }
        _current_batch.add(task_id)
        task_ids.append(task_id)

        asyncio.create_task(_run_agent(task_id, agent_config))

    return task_ids


# ─── Agent runner ─────────────────────────────────────────────────────────────

async def _run_agent(task_id: str, agent_config: dict) -> None:
    """Runs a single agent, updates the registry, and pushes to results_queue."""
    agent_name  = agent_config.get("agent", "unknown")
    task_desc   = agent_config.get("task", "")

    try:
        result: AgentResult = await _dispatch(agent_name, task_desc)

        task_registry[task_id]["status"] = result.status
        task_registry[task_id]["result"] = result.result
        task_registry[task_id]["error"]  = result.error

        await results_queue.put({
            "task_id": task_id,
            "agent":   agent_name,
            "task":    task_desc,
            "status":  result.status,
            "result":  result.result,
            "error":   result.error,
        })

    except Exception as e:
        task_registry[task_id]["status"] = "failed"
        task_registry[task_id]["error"]  = str(e)

        await results_queue.put({
            "task_id": task_id,
            "agent":   agent_name,
            "task":    task_desc,
            "status":  "failed",
            "result":  "",
            "error":   str(e),
        })

    finally:
        _current_batch.discard(task_id)


async def _dispatch(agent_name: str, task_desc: str) -> AgentResult:
    """Route to the correct agent class."""
    if agent_name == "media_agent":
        from agents.media_agent import MediaAgent
        return await MediaAgent.run(task_desc)

    elif agent_name == "system_agent":
        from agents.system_agent import SystemAgent
        return await SystemAgent.run(task_desc)

    elif agent_name == "search_agent":
        from agents.search_agent import SearchAgent
        return await SearchAgent.run(task_desc)

    elif agent_name == "shell_agent":
        from agents.shell_agent import ShellAgent
        return await ShellAgent.run(task_desc)

    else:
        return AgentResult(
            agent=agent_name,
            task=task_desc,
            status="failed",
            error=f"Unknown agent: '{agent_name}'"
        )
