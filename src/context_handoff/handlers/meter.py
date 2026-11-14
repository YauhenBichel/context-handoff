"""UserPromptSubmit: warn, ask for a handoff note, or block, when a session gets expensive.

Over a warn limit it asks the agent, once per session, to write a handoff note
when the current task is done. Over a block limit it blocks the prompt until the
owner asks for the handoff (prompt starts with "handoff") or overrides it
("#override").
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


def run(event: dict, cfg: Config, adapter: Adapter | None = None) -> dict | None:
    """Hook reply as a dict, or None for no reply."""
    adapter = adapter or adapters.get()
    path = event.get("transcript_path") or ""
    session = event.get("session_id") or ""
    cwd = event.get("cwd") or ""
    if not path or not Path(path).is_file():
        return None
    r = meter.measure(adapter.read(path), cfg.prices)
    if r is None:
        return None

    state = State(cfg.state)
    state.log(_record(r, session, cwd))

    block, warn = meter.reasons(r, cfg)
    if meter.bypassed(event.get("prompt") or ""):
        if block or warn:
            return adapter.notice(EVENT, f"[context-handoff] {r.summary()}; prompt let through.")
        return None
    if block:
        return adapter.block(
            f"[context-handoff] {'; '.join(block)}. {r.summary()}. Every turn re-sends the whole "
            f"session. Type: handoff ({adapter.agent} saves a note), then {adapter.clear_command} and "
            "type go. Add #override to send this prompt anyway."
        )
    if not warn:
        return None
    if cfg.auto_handoff and session and state.first_time(session):
        return _ask_for_note(adapter, cfg, cwd, r, warn)
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


def _ask_for_note(adapter: Adapter, cfg: Config, cwd: str, r: Reading, warn: list[str]) -> dict:
    target = notes.NoteStore.from_config(cfg).new_path(cwd)
    context = (
        f"[context-handoff] This session has become expensive: {'; '.join(warn)}. {r.summary()}. "
        "Answer the owner's message first. Then, at the end of the current task (or now, if "
        f"nothing is in progress), write a handoff note to {target} following these "
        "instructions:\n\n" + notes.instructions()
    )
    return adapter.notice(
        EVENT,
        f"[context-handoff] {r.summary()}. {adapter.agent} will write a handoff note after this "
        f"task; then {adapter.clear_command} and type go.",
        context,
    )
