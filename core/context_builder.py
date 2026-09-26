"""
core/context_builder.py
========================
Builds dynamic context block injected into orchestrator prompt.
"""

from datetime import datetime


def build_context() -> str:
    now = datetime.now()
    day       = now.strftime("%A")          # Monday
    date_str  = now.strftime("%B %d, %Y")   # June 23, 2025
    time_str  = now.strftime("%I:%M %p")    # 09:34 PM

    return (
        f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"CURRENT CONTEXT\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Time: {day}, {date_str}, {time_str}"
    )
