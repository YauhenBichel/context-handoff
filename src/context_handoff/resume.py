"""SessionStart hook: load the project's newest unused handoff note.

After /clear (source "clear") the note starts the fresh session. After an
automatic compaction (source "compact") Claude Code continues on its own, and
the note is added next to the compaction summary as a more exact record.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from . import notice
from .config import Config

MAX_BYTES = 12_000
FIRST_MESSAGE = 'go: continue from the handoff note, its "Open items and next steps"'


def find_note(cfg: Config, cwd: str, now: float | None = None) -> Path | None:
    notes = cfg.notes
    if not cwd or not notes.is_dir():
        return None
    project = Path(cwd).name
    pattern = re.compile(re.escape(project) + r"-\d{8}-\d{4}\.md$")
    used = _used(cfg)
    now = now or time.time()
    candidates = []
    for p in notes.iterdir():
        if not pattern.fullmatch(p.name) or str(p) in used:
            continue
        try:
            mtime = p.stat().st_mtime
        except OSError:
            continue
        if cfg.max_age_min > 0 and now - mtime > cfg.max_age_min * 60:
            continue
        candidates.append((mtime, p))
    return max(candidates)[1] if candidates else None


def _used(cfg: Config) -> set[str]:
    try:
        return set((cfg.notes / ".used").read_text().split("\n"))
    except OSError:
        return set()


def run(event: dict, cfg: Config) -> dict | None:
    note = find_note(cfg, event.get("cwd") or "")
    if note is None:
        return None
    compact = event.get("source") == "compact"
    try:
        body = note.read_text(errors="replace")[:MAX_BYTES]
        if not compact:
            # After a compaction the note stays unused, so a later /clear still finds it.
            with open(cfg.notes / ".used", "a") as f:
                f.write(str(note) + "\n")
    except OSError:
        return None
    if compact:
        return notice.output(
            "SessionStart",
            f"[context-handoff] compacted; added {note.name} next to the summary",
            f"A handoff note written earlier in this session ({note}) is below. The compaction "
            "summary is newer: where they differ, follow the summary.\n\n" + body,
        )
    return notice.output(
        "SessionStart",
        f"[context-handoff] resumed from {note.name}",
        f"A handoff note from the previous session was loaded ({note}). On the owner's first "
        'message, continue from its "Open items and next steps" unless the owner asks for '
        "something else.\n\n" + body,
        # Sent as the first user message, so the fresh session continues without typing "go".
        # Claude Code 2.1.263 ignores it after /clear; the note is still in additionalContext.
        initialUserMessage=FIRST_MESSAGE,
    )
