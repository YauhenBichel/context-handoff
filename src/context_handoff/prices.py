"""Default per-million-token prices (USD) for Claude models on the Anthropic API.

Source: Anthropic's published first-party prices as of November 2026. Prices
change; override them in the config file (see config.py) rather than trusting
these forever. Cache writes cost 1.25x input (5-minute TTL) or 2x input
(1-hour TTL); cache reads have their own rate per model.

Each entry: model-id prefix -> (input, output, cache_read).
The longest matching prefix wins, so "claude-opus-4-8" beats "claude-opus-4".
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_PRICES: dict[str, tuple[float, float, float]] = {
    "claude-fable-5-2": (8.00, 40.00, 0.20),
    "claude-mythos-5-2": (8.00, 40.00, 0.20),
    "claude-fable-5-1": (10.00, 50.00, 0.25),
    "claude-mythos-5-1": (10.00, 50.00, 0.25),
    "claude-fable-5": (10.00, 50.00, 1.00),
    "claude-mythos-5": (10.00, 50.00, 1.00),
    "claude-opus-5-5": (4.00, 20.00, 0.20),
    "claude-opus-5": (5.00, 25.00, 0.50),
    "claude-opus-4": (5.00, 25.00, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00, 0.10),
    "claude-sonnet-5": (2.00, 10.00, 0.20),
    "claude-sonnet-4": (3.00, 15.00, 0.30),
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
    "claude-haiku-4": (1.00, 5.00, 0.10),
}

# Used when the model id matches nothing above: priced like the default Opus.
FALLBACK = "claude-opus-5-5"

WRITE_5M = 1.25
WRITE_1H = 2.0


@dataclass(frozen=True)
class Price:
    model: str
    input: float
    output: float
    cache_read: float

    @property
    def write_5m(self) -> float:
        return self.input * WRITE_5M

    @property
    def write_1h(self) -> float:
        return self.input * WRITE_1H


def lookup(model: str, table: dict[str, tuple[float, float, float]] | None = None) -> Price:
    table = table or DEFAULT_PRICES
    model = (model or "").lower()
    best = ""
    for prefix in table:
        if model.startswith(prefix) and len(prefix) > len(best):
            best = prefix
    if not best:
        best = FALLBACK if FALLBACK in table else next(iter(table))
    i, o, r = table[best]
    return Price(best, i, o, r)
