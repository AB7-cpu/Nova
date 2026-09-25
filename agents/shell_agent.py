"""
agents/shell_agent.py
======================
Shell Agent:

Flow:
  1. If task starts with "CONFIRMED: <cmd>", skip generation and run <cmd> directly.
  2. Otherwise, call Ollama to translate the plain-English task into a PS command.
  3. Classify the command (safe / destructive / blocked).
  4. Blocked → fail immediately with reason.
  5. Destructive → return needs_confirmation with the command for user approval.
  6. Safe → execute via PowerShell with a 15-second timeout.

Safety layers:
  BLOCKED     — disk formatting, System32 manipulation, registry wipes.
                Never executed, always fails with an explanation.
  DESTRUCTIVE — file deletion, process termination, shutdown/restart, service stop.
                Requires explicit user "yes" before execution.
  SAFE        — everything else: opening apps, reading files, querying info, etc.
"""

import re
import asyncio
import subprocess
from langchain_core.messages import SystemMessage, HumanMessage

from agents.base import AgentResult
from prompts.agents_prompt import shell_command_generation_prompt
from llm.ollama_llm import get_ollama

# ─── Safety pattern lists ─────────────────────────────────────────────────────

# Commands that are NEVER allowed — always return a failed result.
_BLOCKED_PATTERNS: list[str] = [
    r"format\s*-volume",                       
    r"format\s+[a-z]:",                        
    r"Remove-Item.*(C:\\Windows|System32)",    
    r"rd\s+.*(C:\\Windows|System32)",
    r"del\s+.*(C:\\Windows|System32)",
    r"Remove-Item.*HKLM:\\SAM",                
    r"Clear-Disk",                             
    r"Initialize-Disk.*-confirm:\$false",      
]

# Commands that need user confirmation before running.
_DESTRUCTIVE_PATTERNS: list[str] = [
    r"\bRemove-Item\b",          
    r"\brd\b.*\s/s",             
    r"\bdel\b.*\s/[fsq]",        
    r"\bStop-Computer\b",        
    r"\bRestart-Computer\b",     
    r"\bStop-Process\b",         
    r"\bStop-Service\b",         
    r"\bUninstall-Package\b",    
    r"\bRemove-AppxPackage\b",   
    r"\bClear-RecycleBin\b",     
    r"\bDisable-NetAdapter\b",   
]

TIMEOUT_SECONDS = 15


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _classify(cmd: str) -> str:
    """Classify a PowerShell command as 'blocked', 'destructive', or 'safe'."""
    lowered = cmd.lower()
    for p in _BLOCKED_PATTERNS:
        if re.search(p, cmd, re.IGNORECASE):
            return "blocked"
    for p in _DESTRUCTIVE_PATTERNS:
        if re.search(p, cmd, re.IGNORECASE):
            return "destructive"
    return "safe"


def _generate_command(task: str) -> str:
    """
    Translate a plain-English task into a PowerShell command.
    Uses RouterLLM: offline mode forces Ollama; hybrid mode tries Groq with 10s timeout before falling back.
    """
    from llm.router import RouterLLM
    llm = RouterLLM(temperature=0)
    messages = [
        SystemMessage(content=shell_command_generation_prompt),
        HumanMessage(content=f"Task: {task}"),
    ]
    response = llm.invoke(messages)
    cmd = response.content.strip()
    cmd = re.sub(r"^```(?:powershell|ps1)?\s*", "", cmd, flags=re.IGNORECASE)
    cmd = re.sub(r"\s*```$", "", cmd)
    return cmd.strip()


def _run_powershell(cmd: str) -> tuple[str, str, int]:
    """
    Execute a PowerShell command with a 15-second timeout.
    Returns (stdout, stderr, returncode).
    """
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
    )
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def _truncate(text: str, max_chars: int = 800) -> str:
    """Truncate long command output."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... [truncated — {len(text) - max_chars} more chars]"


# ─── Agent class ──────────────────────────────────────────────────────────────

class ShellAgent:

    @classmethod
    async def run(cls, task: str) -> AgentResult:
        task = task.strip()
        print(f"[ShellAgent] Task: {task[:80]}")

        # ── Confirmed execution path ──────────────────────────────────────────
        # Orchestrator re-dispatches with "CONFIRMED: <cmd>" after user says yes.
        if task.upper().startswith("CONFIRMED:"):
            cmd = task.split(":", 1)[1].strip()
            print(f"[ShellAgent] Confirmed execution: {cmd}")
            return await cls._execute(cmd, task)

        # ── Generate command from plain-English task ──────────────────────────
        try:
            cmd = await asyncio.to_thread(_generate_command, task)
            print(f"[ShellAgent] Generated command: {cmd}")
        except Exception as e:
            return AgentResult(
                agent="shell_agent", task=task, status="failed",
                error=f"Could not generate a PowerShell command for this task: {e}",
            )

        # ── Safety classification ─────────────────────────────────────────────
        classification = _classify(cmd)
        print(f"[ShellAgent] Classification: {classification}")

        if classification == "blocked":
            return AgentResult(
                agent="shell_agent", task=task, status="failed",
                error=(
                    f"Blocked command — this operation is not permitted for safety reasons. "
                    f"Command would have been: {cmd}"
                ),
            )

        if classification == "destructive":
            # Return a confirmation request. The orchestrator will ask the user,
            # then re-dispatch with "CONFIRMED: <cmd>" if they agree.
            return AgentResult(
                agent="shell_agent", task=task, status="needs_confirmation",
                result=(
                    f"CONFIRM_REQUIRED: This command requires your approval before running.\n"
                    f"Command: {cmd}\n"
                    f"To confirm, dispatch shell_agent with task: \"CONFIRMED: {cmd}\""
                ),
            )

        # ── Execute safe command ──────────────────────────────────────────────
        return await cls._execute(cmd, task)

    # ─── Internal ─────────────────────────────────────────────────────────────

    @classmethod
    async def _execute(cls, cmd: str, original_task: str) -> AgentResult:
        """Run the command and return a formatted AgentResult."""
        try:
            stdout, stderr, returncode = await asyncio.to_thread(_run_powershell, cmd)
        except subprocess.TimeoutExpired:
            return AgentResult(
                agent="shell_agent", task=original_task, status="failed",
                error=f"Command timed out after {TIMEOUT_SECONDS} seconds: {cmd}",
            )
        except Exception as e:
            return AgentResult(
                agent="shell_agent", task=original_task, status="failed",
                error=f"Execution error: {e}",
            )

        if returncode != 0:
            error_text = _truncate(stderr or f"Command exited with code {returncode}")
            return AgentResult(
                agent="shell_agent", task=original_task, status="failed",
                error=f"Command failed (exit {returncode}): {error_text}",
            )

        # Success
        output = _truncate(stdout) if stdout else "Command completed with no output."
        return AgentResult(
            agent="shell_agent", task=original_task, status="completed",
            result=output,
        )
