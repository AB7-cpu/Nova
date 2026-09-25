"""
agents/base.py
==============
Shared dataclass and interface for all Mycroft agents.

Every agent's .run() method must return an AgentResult.
The dispatcher puts these into the results_queue for the bundler to collect.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResult:
    agent:   str           # e.g. "system_agent"
    task:    str           # the original task description
    status:  str           # "completed" | "failed"
    result:  str = ""      # plain-English result summary for the orchestrator
    error:   str = ""      # error message if status == "failed"
    data:    Any = None    # structured data (optional, for future display use)
