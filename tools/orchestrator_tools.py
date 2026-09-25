
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

# ─── Tool schemas (Pydantic) ──────────────────────────────────────────────────

class SpeakInput(BaseModel):
    text: str = Field(description="The text to speak to the user via TTS.")


class AgentTask(BaseModel):
    agent:    str = Field(description="Agent identifier: media_agent | system_agent | search_agent | shell_agent")
    task:     str = Field(description="Natural language task description for the agent.")
    priority: int = Field(default=2, description="1=low, 2=normal, 3=high")


class SpawnAgentInput(BaseModel):
    agents: list[AgentTask] = Field(description="List of agents to dispatch in parallel.")


_speak_tool = StructuredTool.from_function(
    func=lambda text: "spoken",
    name="speak",
    description="Say something to the user immediately through the TTS voice system.",
    args_schema=SpeakInput,
)

_spawn_agent_tool = StructuredTool.from_function(
    func=lambda agents: "agents_dispatched",
    name="spawnAgent",
    description=(
        "Dispatch one or more agents to complete tasks in parallel in the background. "
        "Returns immediately — do not wait for results."
    ),
    args_schema=SpawnAgentInput,
)