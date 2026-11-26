"""The meter's own small state: a log of readings and a once-per-session marker.

Writing state is best effort: a full disk or a read-only home must never stop a
hook, so every OSError is swallowed here.

The log is `meter.jsonl`. Past `log_max_kb` it is renamed to `meter.jsonl.1`
(replacing the one before) and a new one is started, so it never grows without
limit.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path

LOG = "meter.jsonl"


class State:
    def __init__(self, directory: Path, log_max_kb: int = 1024):
        self.directory = directory
        self.log_max_kb = log_max_kb

    def log(self, record: dict) -> None:
        path = self.directory / LOG
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            self._rotate(path)
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except OSError:
            pass

    def _rotate(self, path: Path) -> None:
        if self.log_max_kb <= 0:
            return
        try:
            if path.stat().st_size >= self.log_max_kb * 1024:
                os.replace(path, path.with_name(LOG + ".1"))
        except OSError:
            pass

    def cwds_since(self, since: float) -> set[str]:
        """Working directories of the sessions the log has seen from `since` (epoch seconds) on."""
        seen: set[str] = set()
        for name in (LOG + ".1", LOG):
            try:
                f = open(self.directory / name, encoding="utf-8", errors="replace")
            except OSError:
                continue
            with f:
                for line in f:
                    try:
                        rec = json.loads(line)
                        at = dt.datetime.fromisoformat(rec["ts"]).timestamp()
                        cwd = rec["cwd"]
                    except (ValueError, KeyError, TypeError, AttributeError):
                        continue
                    if at >= since and isinstance(cwd, str) and cwd:
                        seen.add(cwd)
        return seen

    def first_time(self, session: str) -> bool:
        """True the first time this is asked for `session`, False after that.

        The marker's name is a hash of the session id, so an id with `/`, NUL
        or of any length still gives a file name that can be created.
        """
        digest = hashlib.sha256(session.encode("utf-8", "surrogatepass")).hexdigest()[:16]
        marker = self.directory / f"asked-{digest}"
        # Up to 0.1.6 the marker was named after the session id itself.
        old = self.directory / f"asked-{session}" if re.fullmatch(r"[\w-]{1,128}", session) else None
        try:
            if marker.exists() or (old is not None and old.exists()):
                return False
        except OSError:
            pass
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            marker.touch()
        except OSError:
            pass
        return True
