"""The meter's own small state: a log of readings and a once-per-session marker.

Writing state is best effort: a full disk or a read-only home must never stop a
hook, so every OSError is swallowed here.
"""

from __future__ import annotations

import json
from pathlib import Path


class State:
    def __init__(self, directory: Path):
        self.directory = directory

    def log(self, record: dict) -> None:
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with open(self.directory / "meter.jsonl", "a") as f:
                f.write(json.dumps(record) + "\n")
        except OSError:
            pass

    def first_time(self, session: str) -> bool:
        """True the first time this is asked for `session`, False after that."""
        marker = self.directory / f"asked-{session}"
        if marker.exists():
            return False
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            marker.touch()
        except OSError:
            pass
        return True
