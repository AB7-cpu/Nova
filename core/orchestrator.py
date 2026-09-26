"""
core/orchestrator.py
====================

The Nova orchestrator — the brain of the system.
"""

import asyncio
from langchain_core.messages import SystemMessage, HumanMessage
from tools.orchestrator_tools import _speak_tool, _spawn_agent_tool
from prompts.orchestrator_prompt import system_prompt
from core.context_builder import build_context
from core.speak_queue import enqueue_speech
from core.dispatcher import spawn_agents
from core.session import Session
from llm.router import RouterLLM



# ─── LLM instance ────────────────────────────────────────────────────────────

_llm = RouterLLM().bind_tools([_speak_tool, _spawn_agent_tool])


# ─── Main orchestrator ───────────────────────────────────────────────

async def invoke_orchestrator(
    session: Session,
    user_input:    str | None = None,
    agent_results: str | None = None,
) -> None:

    full_system = system_prompt + build_context()

    messages = [SystemMessage(content=full_system)]
    messages += session.get_history()

    if user_input:
        new_msg = HumanMessage(content=user_input)
        session.add_user_message(user_input)
    elif agent_results:
        new_msg = HumanMessage(content=f"[Agent Results]\n{agent_results}")
        session.add_agent_results(agent_results)
    else:
        return

    messages.append(new_msg)

    print(f"\n🤖 Orchestrator thinking...", flush=True)
    try:
        response = await _llm.ainvoke(messages)
    except Exception as e:
        print(f"❌ Orchestrator LLM error: {e}")
        await enqueue_speech("Sorry, I ran into an issue. Give me a moment.")
        return

    session.add_assistant_response(response)

    executed_speak = False
    spawned_agents = False

    for tool_call in (response.tool_calls or []):
        name = tool_call["name"]
        args = tool_call["args"]

        if name == "speak":
            text = args.get("text", "").strip()
            if text:
                print(f"\n💬 Nova: {text}")
                await enqueue_speech(text)
                executed_speak = True

        elif name == "spawnAgent":
            raw_agents = args.get("agents", [])
            agent_dicts = [
                a.model_dump() if hasattr(a, "model_dump") else dict(a)
                for a in raw_agents
            ]
            if agent_dicts:
                task_ids = await spawn_agents(agent_dicts)
                print(f"\n🚀 Dispatched agents: {[a['agent'] for a in agent_dicts]} → {task_ids}")
                spawned_agents = True

    if spawned_agents and not executed_speak:
        print("\n💬 Nova (auto-ack): On it.")
        await enqueue_speech("On it.")

    if not response.tool_calls and response.content:
        text = response.content.strip()
        if text:
            print(f"\n💬 Nova (fallback): {text}")
            await enqueue_speech(text)

    session.post_turn_maintenance()
