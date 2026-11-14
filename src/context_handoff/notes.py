"""Handoff notes on disk: where a new one goes, which one to resume, and their format.

A note is `<project>-YYYYMMDD-HHMM.md` in the notes directory, where `<project>`
is the last part of the session's working directory. A note is resumed once
after a fresh start; `.used` lists the notes already resumed.
"""

from __future__ import annotations

import datetime as dt
import re
import time
from pathlib import Path

from .config import Config

# The plugin's /handoff command defines the note's format; the meter reuses it.
COMMAND_FILE = Path(__file__).resolve().parents[2] / "commands" / "handoff.md"
FALLBACK_INSTRUCTIONS = (
    "Write the goal, state, decisions, open items and next steps, where things are, and gotchas."
)


def instructions() -> str:
    """The handoff command's body: the one place the note's format is defined."""
    try:
        text = COMMAND_FILE.read_text()
    except OSError:
        return FALLBACK_INSTRUCTIONS
    if text.startswith("---"):
        text = text.split("---", 2)[2]
    return text.replace("$ARGUMENTS", "").strip()


class NoteStore:
    def __init__(self, directory: Path, max_age_min: int = 0):
        self.directory = directory
        self.max_age_min = max_age_min

    @classmethod
    def from_config(cls, cfg: Config) -> NoteStore:
        return cls(cfg.notes, cfg.max_age_min)

    @property
    def _used_file(self) -> Path:
        return self.directory / ".used"

    def new_path(self, cwd: str, now: dt.datetime | None = None) -> Path:
        now = now or dt.datetime.now()
        project = Path(cwd).name or "session"
        return self.directory / f"{project}-{now:%Y%m%d-%H%M}.md"

    def newest_unused(self, cwd: str, now: float | None = None) -> Path | None:
        """The project's newest note that is not resumed yet and not too old."""
        if not cwd or not self.directory.is_dir():
            return None
        pattern = re.compile(re.escape(Path(cwd).name) + r"-\d{8}-\d{4}\.md$")
        used = self._used()
        now = now or time.time()
        candidates = []
        for p in self.directory.iterdir():
            if not pattern.fullmatch(p.name) or str(p) in used:
                continue
            try:
                mtime = p.stat().st_mtime
            except OSError:
                continue
            if self.max_age_min > 0 and now - mtime > self.max_age_min * 60:
                continue
            candidates.append((mtime, p))
        return max(candidates)[1] if candidates else None

    def mark_used(self, note: Path) -> None:
        """Raises OSError when the list cannot be written."""
        with open(self._used_file, "a") as f:
            f.write(str(note) + "\n")

    def _used(self) -> set[str]:
        try:
            return set(self._used_file.read_text().split("\n"))
        except OSError:
            return set()
