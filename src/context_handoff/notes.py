"""Handoff notes on disk: where a new one goes, which one to resume, and their format.

A note is `<project>-<cwd8>-YYYYMMDD-HHMMSS-<sid6>.md` in the notes directory:

    project   the last part of the session's working directory, made safe for a
              file name; it is there for people reading the directory
    cwd8      8 hex digits of a hash of the full working directory: what
              matching uses, so two repositories that both end in `src` or
              `app` do not get each other's notes
    sid6      6 hex digits of a hash of the session id (random without one), so
              two sessions in one directory never get the same path

The code computes the whole path; the agent is never asked to build a name or a
time itself.

Up to 0.1.6 a note was `<project>-YYYYMMDD-HHMM.md`. Such notes are still
resumed for a working directory with that last part, inside the same age
window; the resume handler skips one when the folder name is ambiguous (see
`handlers/resume.py`).

A note is resumed once after a fresh start; `.used` lists the notes already
resumed, one JSON string per line (older lines are plain paths and still read).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import secrets
import stat
import time
from pathlib import Path

from .config import Config

# The plugin's /handoff command defines the note's format; the meter reuses it.
PLUGIN_ROOT = Path(__file__).resolve().parents[2]
COMMAND_FILE = PLUGIN_ROOT / "commands" / "handoff.md"
FALLBACK_INSTRUCTIONS = (
    "Write the goal, state, decisions, open items and next steps, where things are, and gotchas."
)

_STAMPS = r"\d{8}-\d{6}-[0-9a-f]{6}\.md"
NEW_NAME = re.compile(r".+-[0-9a-f]{8}-" + _STAMPS, re.DOTALL)
OLD_NAME = re.compile(r".+-\d{8}-\d{4}\.md", re.DOTALL)
PROJECT_MAX_BYTES = 80


def instructions() -> str:
    """The handoff command's body: the one place the note's format is defined."""
    try:
        text = COMMAND_FILE.read_text(encoding="utf-8")
    except OSError:
        return FALLBACK_INSTRUCTIONS
    if text.startswith("---"):
        text = text.split("---", 2)[2]
    # Claude Code fills this in for a command; do the same when a hook passes the text on.
    text = text.replace("${CLAUDE_PLUGIN_ROOT}", str(PLUGIN_ROOT))
    return text.replace("$ARGUMENTS", "").strip()


def _digest(text: str, length: int) -> str:
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()[:length]


def cwd_key(cwd: str) -> str:
    """A short stable id of the full working directory."""
    return _digest(os.path.normpath(cwd), 8)


def project(cwd: str) -> str:
    """The working directory's last part as a safe, short piece of a file name."""
    name = re.sub(r"[^\w.-]+", "_", Path(cwd).name)[:PROJECT_MAX_BYTES]
    while len(name.encode("utf-8")) > PROJECT_MAX_BYTES:
        name = name[:-1]
    return name or "session"


def is_note_name(name: str) -> bool:
    """True for a file name this plugin gives a note, in the current or the old format."""
    return bool(NEW_NAME.fullmatch(name) or OLD_NAME.fullmatch(name))


def _cut(data: bytes, limit: int) -> tuple[bytes, bool]:
    """At most `limit` bytes, never ending inside a UTF-8 character."""
    if len(data) <= limit:
        return data, False
    cut = limit
    while cut > 0 and limit - cut < 4 and (data[cut] & 0xC0) == 0x80:
        cut -= 1
    return data[:cut], True


class NoteStore:
    def __init__(self, directory: Path, max_age_min: int = 0):
        self.directory = directory
        self.max_age_min = max_age_min

    @classmethod
    def from_config(cls, cfg: Config) -> NoteStore:
        return cls(cfg.notes, cfg.max_age_min)

    @property
    def used_file(self) -> Path:
        return self.directory / ".used"

    def new_path(self, cwd: str, now: dt.datetime | None = None, session: str = "") -> Path:
        """Where a session's next note goes. Two sessions never get the same path."""
        now = now or dt.datetime.now()
        sid = _digest(session, 6) if session else secrets.token_hex(3)
        return self.directory / f"{project(cwd)}-{cwd_key(cwd)}-{now:%Y%m%d-%H%M%S}-{sid}.md"

    @staticmethod
    def is_legacy(note: Path) -> bool:
        """True for a note in the old name format, which does not say which directory it is for."""
        return not NEW_NAME.fullmatch(note.name)

    def newest_unused(self, cwd: str, now: float | None = None, legacy: bool = True) -> Path | None:
        """The newest note for `cwd` that is not resumed yet and not too old.

        Notes in the current format are matched by the hash of the full `cwd`;
        with `legacy`, notes in the old format are matched by its last part.
        Only regular files count: a symlink named like a note is ignored.
        """
        if not cwd or not self.directory.is_dir():
            return None
        patterns = [re.compile(re.escape(f"{project(cwd)}-{cwd_key(cwd)}-") + _STAMPS)]
        if legacy and Path(cwd).name:
            patterns.append(re.compile(re.escape(Path(cwd).name) + r"-\d{8}-\d{4}\.md"))
        used = self._used()
        now = now or time.time()
        candidates = []
        for p in self.directory.iterdir():
            if not any(pattern.fullmatch(p.name) for pattern in patterns) or str(p) in used:
                continue
            try:
                st = p.lstat()
            except OSError:
                continue
            if not stat.S_ISREG(st.st_mode):
                continue
            if self.max_age_min > 0 and now - st.st_mtime > self.max_age_min * 60:
                continue
            candidates.append((st.st_mtime, p))
        return max(candidates)[1] if candidates else None

    def read(self, note: Path, max_bytes: int) -> tuple[str, bool]:
        """(text, was it cut) of a note, at most `max_bytes` bytes of it.

        Raises OSError when the note is not a regular file (a symlink is not
        followed) or cannot be read.
        """
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        with os.fdopen(os.open(note, flags), "rb") as f:
            if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
                raise OSError(f"not a regular file: {note}")
            data, cut = _cut(f.read(max_bytes + 4), max_bytes)
        return data.decode("utf-8", errors="replace"), cut

    def mark_used(self, note: Path) -> None:
        """Raises OSError when the list cannot be written."""
        with open(self.used_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(str(note)) + "\n")

    def _used(self) -> set[str]:
        try:
            lines = self.used_file.read_text(encoding="utf-8", errors="replace").split("\n")
        except OSError:
            return set()
        used = set()
        for line in lines:
            if line.startswith('"'):
                try:
                    value = json.loads(line)
                except ValueError:
                    value = None
                if isinstance(value, str):
                    used.add(value)
                    continue
            used.add(line)  # up to 0.1.6: the plain path
        return used

    def prune(self, days: int, now: float | None = None, keep: Path | None = None) -> int:
        """Delete notes last changed more than `days` days ago; returns how many.

        Only regular files directly inside the notes directory whose name is in
        one of the plugin's two note formats are deleted. Symlinks, folders and
        every other file (`.used` too) are left alone. 0 days turns it off.
        """
        if days <= 0:
            return 0
        cutoff = (now or time.time()) - days * 86400
        try:
            entries = list(os.scandir(self.directory))
        except OSError:
            return 0
        removed = 0
        for entry in entries:
            if not is_note_name(entry.name) or (keep is not None and entry.name == keep.name):
                continue
            try:
                st = entry.stat(follow_symlinks=False)
                if not stat.S_ISREG(st.st_mode) or st.st_mtime >= cutoff:
                    continue
                os.unlink(entry.path)
                removed += 1
            except OSError:
                continue
        return removed
