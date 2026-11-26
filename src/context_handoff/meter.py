"""The meter: what a session costs now, and whether that is too much.

Every turn re-sends the whole conversation. While the prompt cache is warm the
re-read is cheap; after a pause the whole context is written again at the
cache-write price, and that is where long sessions get expensive. The meter
looks at three numbers:

  * context: tokens the last reply read (what the next turn re-sends)
  * last turn: what the last reply cost
  * session: what all replies in this session cost so far

and also projects what one cold turn (cache expired) would cost now.

This module only measures and decides; `handlers/meter.py` turns the decision
into a hook reply.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .config import Config
from .prices import lookup
from .usage import Session

# A prompt that asks for the handoff, or overrides the meter, is never blocked.
HANDOFF = r"^\s*/?([a-z0-9-]+:)?handoff\b"
BYPASS = re.compile(HANDOFF + "|#override", re.IGNORECASE)
HANDOFF_REQUEST = re.compile(HANDOFF, re.IGNORECASE)


@dataclass
class Reading:
    model: str
    context: int
    last_turn_usd: float
    session_usd: float
    cold_turn_usd: float
    turns: int

    def summary(self) -> str:
        return (
            f"{self.context // 1000}K context, last turn ${self.last_turn_usd:.2f}, "
            f"session ${self.session_usd:.2f}, a cold turn would cost ${self.cold_turn_usd:.2f} "
            f"({self.model} prices)"
        )


def measure(session: Session, prices: dict | None = None) -> Reading | None:
    last = session.last
    if last is None:
        return None
    price = lookup(last.model, prices)
    return Reading(
        model=price.model,
        context=last.context,
        last_turn_usd=last.cost(price),
        session_usd=session.cost(prices),
        cold_turn_usd=last.cold_cost(price),
        turns=len(session.turns),
    )


def _over(value: float, limit: float) -> bool:
    return limit > 0 and value >= limit


def reasons(r: Reading, cfg: Config) -> tuple[list[str], list[str]]:
    """(block reasons, warn reasons)."""
    block, warn = [], []
    if _over(r.context, cfg.block_k * 1000):
        block.append(f"context {r.context // 1000}K >= {cfg.block_k}K")
    if _over(r.last_turn_usd, cfg.block_turn_usd):
        block.append(f"last turn ${r.last_turn_usd:.2f} >= ${cfg.block_turn_usd:.2f}")
    if _over(r.context, cfg.warn_k * 1000):
        warn.append(f"context {r.context // 1000}K >= {cfg.warn_k}K")
    if _over(r.last_turn_usd, cfg.warn_turn_usd):
        warn.append(f"last turn ${r.last_turn_usd:.2f} >= ${cfg.warn_turn_usd:.2f}")
    if _over(r.session_usd, cfg.warn_session_usd):
        warn.append(f"session ${r.session_usd:.2f} >= ${cfg.warn_session_usd:.2f}")
    return block, warn


def bypassed(prompt: str) -> bool:
    return bool(BYPASS.search(prompt or ""))


def asks_for_handoff(prompt: str) -> bool:
    """True when the owner's prompt asks for a handoff note (`handoff ...` or the /handoff command)."""
    return bool(HANDOFF_REQUEST.search(prompt or ""))
