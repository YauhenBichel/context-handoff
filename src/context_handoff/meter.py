"""UserPromptSubmit hook: decide whether this session has become too expensive.

Every turn re-sends the whole conversation. While the prompt cache is warm the
re-read is cheap; after a pause the whole context is written again at the
cache-write price, and that is where long sessions get expensive. The meter
looks at three numbers from the transcript:

  * context: tokens the last reply read (what the next turn re-sends)
  * last turn: what the last reply cost
  * session: what all replies in this session cost so far

and also projects what one cold turn (cache expired) would cost now.

Over a warn limit it asks Claude, once per session, to write a handoff note
when the current task is done. Over a block limit it blocks the prompt until
the owner asks for the handoff (prompt starts with "handoff") or overrides it
("#override").
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path

from . import adapters, notice
from .config import Config
from .prices import lookup

BYPASS = re.compile(r"^\s*/?([a-z0-9-]+:)?handoff\b|#override", re.IGNORECASE)
# The plugin's /handoff command defines the note's format; the meter reuses it.
COMMAND_FILE = Path(__file__).resolve().parents[2] / "commands" / "handoff.md"


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


def measure(path: str, cfg: Config, tool: str = adapters.DEFAULT) -> Reading | None:
    session = adapters.get(tool).read(path)
    last = session.last
    if last is None:
        return None
    price = lookup(last.model, cfg.prices)
    return Reading(
        model=price.model,
        context=last.context,
        last_turn_usd=last.cost(price),
        session_usd=session.cost(cfg.prices),
        cold_turn_usd=last.context * price.write_1h / 1e6,
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


def note_path(cfg: Config, cwd: str, now: dt.datetime | None = None) -> Path:
    now = now or dt.datetime.now()
    project = Path(cwd).name or "session"
    return cfg.notes / f"{project}-{now:%Y%m%d-%H%M}.md"


def note_instructions() -> str:
    """The handoff command's body: the one place the note's format is defined."""
    try:
        text = COMMAND_FILE.read_text()
    except OSError:
        return "Write the goal, state, decisions, open items and next steps, where things are, and gotchas."
    if text.startswith("---"):
        text = text.split("---", 2)[2]
    return text.replace("$ARGUMENTS", "").strip()


def _log(cfg: Config, event: dict) -> None:
    try:
        cfg.state.mkdir(parents=True, exist_ok=True)
        with open(cfg.state / "meter.jsonl", "a") as f:
            f.write(json.dumps(event) + "\n")
    except OSError:
        pass


def run(event: dict, cfg: Config, tool: str = adapters.DEFAULT) -> dict | None:
    """Hook output as a dict, or None for no output."""
    path = event.get("transcript_path") or ""
    session = event.get("session_id") or ""
    cwd = event.get("cwd") or ""
    prompt = event.get("prompt") or ""
    if not path or not Path(path).is_file():
        return None
    r = measure(path, cfg, tool)
    if r is None:
        return None

    _log(cfg, {
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "session": session, "cwd": cwd, "model": r.model, "ctx": r.context,
        "turn_usd": round(r.last_turn_usd, 4), "session_usd": round(r.session_usd, 4),
    })

    block, warn = reasons(r, cfg)
    if BYPASS.search(prompt):
        if block or warn:
            return notice.output("UserPromptSubmit", f"[context-handoff] {r.summary()}; prompt let through.")
        return None

    if block:
        return {
            "decision": "block",
            "reason": (
                f"[context-handoff] {'; '.join(block)}. {r.summary()}. Every turn re-sends the whole "
                "session. Type: handoff (Claude saves a note), then /clear and type go. "
                "Add #override to send this prompt anyway."
            ),
        }
    if not warn:
        return None

    marker = cfg.state / f"asked-{session}"
    if cfg.auto_handoff and session and not marker.exists():
        try:
            cfg.state.mkdir(parents=True, exist_ok=True)
            marker.touch()
        except OSError:
            pass
        target = note_path(cfg, cwd)
        context = (
            f"[context-handoff] This session has become expensive: {'; '.join(warn)}. {r.summary()}. "
            "Answer the owner's message first. Then, at the end of the current task (or now, if "
            f"nothing is in progress), write a handoff note to {target} following these "
            "instructions:\n\n" + note_instructions()
        )
        return notice.output(
            "UserPromptSubmit",
            f"[context-handoff] {r.summary()}. Claude will write a handoff note after this "
            "task; then /clear and type go.",
            context,
        )
    return notice.output(
        "UserPromptSubmit",
        f"[context-handoff] {r.summary()}. Finish this task, type handoff, then /clear and go.",
    )
