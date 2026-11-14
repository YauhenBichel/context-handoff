"""Notices the owner should see, in every Claude Code client.

A hook's `systemMessage` is shown in the terminal, but the VS Code extension
does not show it. So each notice is also given to Claude, which repeats it at
the start of its reply. Hooks return both.
"""

from __future__ import annotations


def relay(line: str) -> str:
    """Context asking Claude to repeat `line` to the owner."""
    return (
        "Some Claude Code clients (the VS Code extension) do not show hook messages. Start your next "
        f"reply with this line, as is, on its own line:\n{line}"
    )


def output(event: str, line: str, context: str = "", **extra) -> dict:
    """Hook output that shows `line` in the terminal and has Claude repeat it elsewhere."""
    ctx = relay(line) + ("\n\n" + context if context else "")
    return {
        "systemMessage": line,
        "hookSpecificOutput": {"hookEventName": event, **extra, "additionalContext": ctx},
    }
