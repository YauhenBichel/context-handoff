"""SessionStart: load the project's newest unused handoff note.

After /clear (source "clear") the note starts the fresh session. After an
automatic compaction (source "compact") the agent continues on its own, and the
note is added next to the compaction summary as a more exact record.
"""

from __future__ import annotations

from pathlib import Path

from .. import adapters
from ..adapters.base import Adapter
from ..config import Config
from ..notes import NoteStore

EVENT = "SessionStart"
MAX_BYTES = 12_000
FIRST_MESSAGE = 'go: continue from the handoff note, its "Open items and next steps"'


def run(event: dict, cfg: Config, adapter: Adapter | None = None) -> dict | None:
    adapter = adapter or adapters.get()
    store = NoteStore.from_config(cfg)
    note = store.newest_unused(event.get("cwd") or "")
    if note is None:
        return None
    compact = event.get("source") == "compact"
    try:
        body = note.read_text(errors="replace")[:MAX_BYTES]
        if not compact:
            # After a compaction the note stays unused, so a later /clear still finds it.
            store.mark_used(note)
    except OSError:
        return None
    if compact:
        return _after_compaction(adapter, note, body)
    return _fresh_start(adapter, note, body)


def _after_compaction(adapter: Adapter, note: Path, body: str) -> dict:
    return adapter.notice(
        EVENT,
        f"[context-handoff] compacted; added {note.name} next to the summary",
        f"A handoff note written earlier in this session ({note}) is below. The compaction "
        "summary is newer: where they differ, follow the summary.\n\n" + body,
    )


def _fresh_start(adapter: Adapter, note: Path, body: str) -> dict:
    return adapter.notice(
        EVENT,
        f"[context-handoff] resumed from {note.name}",
        f"A handoff note from the previous session was loaded ({note}). On the owner's first "
        'message, continue from its "Open items and next steps" unless the owner asks for '
        "something else.\n\n" + body,
        # Sent as the first user message, so the fresh session continues without typing "go".
        # Claude Code 2.1.263 ignores it after /clear; the note is still in additionalContext.
        initialUserMessage=FIRST_MESSAGE,
    )
