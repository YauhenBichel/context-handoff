"""UserPromptSubmit: warn, ask for a handoff note, or block, when a session gets expensive.

Over a warn limit it asks the agent, once per session, to write a handoff note
when the current task is done. Over a block limit it blocks the prompt until the
owner asks for the handoff (prompt starts with "handoff") or overrides it
("#override").

Whenever a note is asked for, by the meter or by the owner (`handoff ...` or the
/handoff command), this hook computes the note's full path and gives it to the
agent. The agent never builds the file name, the project or the time itself.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from .. import adapters, meter, notes
from ..adapters.base import Adapter
from ..config import Config
from ..meter import Reading
from ..state import State

EVENT = "UserPromptSubmit"
# commands/handoff.md tells the agent to look for this line.
PATH_LINE = "[context-handoff] Handoff note path: "
PATH_RULES = (
    "Save the handoff note to exactly this path, creating the folder if needed. Write one file only: "
    "do not change the name, the project or the time in it, and do not save copies under other names."
)


def _text(value) -> str:
    return value if isinstance(value, str) else ""


def run(event: dict, cfg: Config, adapter: Adapter | None = None) -> dict | None:
    """Hook reply as a dict, or None for no reply."""
    adapter = adapter or adapters.get()
    path = _text(event.get("transcript_path"))
    session = _text(event.get("session_id"))
    cwd = _text(event.get("cwd"))
    prompt = _text(event.get("prompt"))
    # The owner asks for the note: say where it goes, metered session or not.
    where = _owner_asked(cfg, cwd, session, prompt) if meter.asks_for_handoff(prompt) else ""
    only_where = adapter.notice(EVENT, "", where) if where else None

    if not path or not Path(path).is_file():
        return only_where
    r = meter.measure(adapter.read(path), cfg.prices)
    if r is None:
        return only_where

    state = State(cfg.state, cfg.log_max_kb)
    state.log(_record(r, session, cwd))

    block, warn = meter.reasons(r, cfg)
    if meter.bypassed(prompt):
        if block or warn:
            return adapter.notice(EVENT, f"[context-handoff] {r.summary()}; prompt let through.", where)
        return only_where
    if block:
        return adapter.block(
            f"[context-handoff] {'; '.join(block)}. {r.summary()}. Every turn re-sends the whole "
            f"session. Type: handoff ({adapter.agent} saves a note), then {adapter.clear_command} and "
            "type go. Add #override to send this prompt anyway."
        )
    if not warn:
        return None
    if cfg.auto_handoff and session and state.first_time(session):
        return _ask_for_note(adapter, cfg, cwd, session, r, warn)
    return adapter.notice(
        EVENT,
        f"[context-handoff] {r.summary()}. Finish this task, type handoff, then "
        f"{adapter.clear_command} and go.",
    )


def _record(r: Reading, session: str, cwd: str) -> dict:
    return {
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "session": session, "cwd": cwd, "model": r.model, "ctx": r.context,
        "turn_usd": round(r.last_turn_usd, 4), "session_usd": round(r.session_usd, 4),
    }


def _where(cfg: Config, cwd: str, session: str) -> str:
    target = notes.NoteStore.from_config(cfg).new_path(cwd, session=session)
    return f"{PATH_LINE}{target}\n{PATH_RULES}"


def _owner_asked(cfg: Config, cwd: str, session: str, prompt: str) -> str:
    where = _where(cfg, cwd, session)
    if prompt.lstrip().startswith("/"):
        return where  # the /handoff command brings the instructions itself
    return (
        f"{where}\n\nIf the owner is asking for a handoff note, follow these instructions:\n\n"
        + notes.instructions()
    )


def _ask_for_note(adapter: Adapter, cfg: Config, cwd: str, session: str, r: Reading, warn: list[str]) -> dict:
    context = (
        f"[context-handoff] This session has become expensive: {'; '.join(warn)}. {r.summary()}. "
        "Answer the owner's message first. Then, at the end of the current task (or now, if "
        "nothing is in progress), write a handoff note.\n\n"
        f"{_where(cfg, cwd, session)}\n\nFollow these instructions:\n\n" + notes.instructions()
    )
    return adapter.notice(
        EVENT,
        f"[context-handoff] {r.summary()}. {adapter.agent} will write a handoff note after this "
        f"task; then {adapter.clear_command} and type go.",
        context,
    )
