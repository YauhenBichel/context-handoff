"""Token usage of a session, the same for every agent tool.

Each adapter in `adapters/` reads its tool's session file into these types; the
meter and the report only see these.
"""

from __future__ import annotations

from dataclasses import dataclass, field

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
    at: float | None = None  # reply time (epoch seconds), when the transcript has it

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
