"""Claude Code adapter: session transcripts and hook replies."""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Iterator
from pathlib import Path

from ..usage import Session, Turn


def _turn(usage: dict, model: str) -> Turn:
    creation = usage.get("cache_creation") or {}
    w5 = creation.get("ephemeral_5m_input_tokens")
    w1 = creation.get("ephemeral_1h_input_tokens")
    total_write = usage.get("cache_creation_input_tokens") or 0
    if w5 is None and w1 is None:
        # No TTL breakdown: Claude Code writes with the 1-hour TTL, so price it as that.
        w5, w1 = 0, total_write
    return Turn(
        model=model,
        input=usage.get("input_tokens") or 0,
        cache_write_5m=w5 or 0,
        cache_write_1h=w1 or 0,
        cache_read=usage.get("cache_read_input_tokens") or 0,
        output=usage.get("output_tokens") or 0,
    )


def _epoch(stamp) -> float | None:
    try:
        return dt.datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def read(path: str | Path) -> Session:
    """Main-thread Claude replies, one per message id, in order.

    A reply is written as several transcript lines repeating the same usage,
    so only the last line seen for each message id counts.
    """
    replies: dict[str, Turn] = {}
    try:
        f = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return Session()
    with f:
        for line in f:
            if '"usage"' not in line or '"assistant"' not in line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("type") != "assistant" or rec.get("isSidechain"):
                continue
            msg = rec.get("message") or {}
            usage = msg.get("usage")
            model = msg.get("model") or ""
            if not usage or not model.startswith("claude"):
                continue
            key = msg.get("id") or f"line-{len(replies)}"
            replies.pop(key, None)  # keep insertion order at the latest position
            turn = _turn(usage, model)
            turn.at = _epoch(rec.get("timestamp"))
            replies[key] = turn
    return Session(list(replies.values()))


def relay(line: str) -> str:
    """Context asking Claude to repeat `line` to the owner.

    A hook's `systemMessage` is shown in the terminal, but the VS Code extension
    does not show it. So each notice is also given to Claude, which repeats it at
    the start of its reply.
    """
    return (
        "Some Claude Code clients (the VS Code extension) do not show hook messages. Start your next "
        f"reply with this line, as is, on its own line:\n{line}"
    )


class ClaudeCode:
    name = "claude"
    agent = "Claude"
    clear_command = "/clear"

    def read(self, path: str | Path) -> Session:
        return read(path)

    def session_files(self, root: Path | None = None) -> Iterator[tuple[str, Path]]:
        root = root or Path.home() / ".claude" / "projects"
        for f in root.glob("*/*.jsonl"):
            yield f.parent.name, f

    def notice(self, event: str, line: str, context: str = "", **extra) -> dict:
        ctx = relay(line) + ("\n\n" + context if context else "")
        return {
            "systemMessage": line,
            "hookSpecificOutput": {"hookEventName": event, **extra, "additionalContext": ctx},
        }

    def block(self, reason: str) -> dict:
        return {"decision": "block", "reason": reason}


ADAPTER = ClaudeCode()
