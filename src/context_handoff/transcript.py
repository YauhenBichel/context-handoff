"""Read token usage from a Claude Code session transcript (JSON lines)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .prices import Price, lookup


@dataclass
class Turn:
    """Usage of one model reply."""

    model: str
    input: int = 0
    cache_write_5m: int = 0
    cache_write_1h: int = 0
    cache_read: int = 0
    output: int = 0

    @property
    def context(self) -> int:
        """Tokens the model read for this reply: what the next turn re-sends."""
        return self.input + self.cache_write_5m + self.cache_write_1h + self.cache_read

    def cost(self, price: Price) -> float:
        return (
            self.input * price.input
            + self.cache_write_5m * price.write_5m
            + self.cache_write_1h * price.write_1h
            + self.cache_read * price.cache_read
            + self.output * price.output
        ) / 1e6


@dataclass
class Session:
    turns: list[Turn] = field(default_factory=list)

    @property
    def last(self) -> Turn | None:
        return self.turns[-1] if self.turns else None

    def cost(self, table=None) -> float:
        return sum(t.cost(lookup(t.model, table)) for t in self.turns)


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
            replies[key] = _turn(usage, model)
    return Session(list(replies.values()))
