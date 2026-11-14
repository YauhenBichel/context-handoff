"""SessionStart hook (after /clear): load the project's newest unused handoff note."""

from __future__ import annotations

import re
import time
from pathlib import Path

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
    try:
        body = note.read_text(errors="replace")[:MAX_BYTES]
        with open(cfg.notes / ".used", "a") as f:
            f.write(str(note) + "\n")
    except OSError:
        return None
    return {
        "systemMessage": f"[context-handoff] loaded {note}; continuing (if nothing starts, type go)",
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            # Sent as the first user message, so the fresh session continues without typing "go".
            # Claude Code versions that ignore it after /clear still have the note in additionalContext.
            "initialUserMessage": FIRST_MESSAGE,
            "additionalContext": (
                f"A handoff note from the previous session was loaded ({note}). On the owner's first "
                'message, continue from its "Open items and next steps" unless the owner asks for '
                "something else.\n\n" + body
            ),
        },
    }
