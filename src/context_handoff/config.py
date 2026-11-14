"""Settings: defaults, then ~/.claude/context-handoff.json, then environment.

Config file example (all keys optional):

    {
      "warn_k": 150, "block_k": 400,
      "warn_turn_usd": 0.50, "block_turn_usd": 3.00,
      "warn_session_usd": 20, "auto_handoff": true,
      "prices": {"claude-opus-5-5": [4.0, 20.0, 0.20]}
    }

Environment variables use the same names, upper case, with a
CONTEXT_HANDOFF_ prefix: CONTEXT_HANDOFF_WARN_TURN_USD=1.0 and so on.
A limit set to 0 is turned off.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, fields
from pathlib import Path

from .prices import DEFAULT_PRICES


def _home() -> Path:
    return Path(os.environ.get("HOME") or Path.home())


@dataclass
class Config:
    warn_k: int = 150  # context size (thousands of tokens) that triggers a handoff
    block_k: int = 400  # context size that blocks prompts until a handoff
    warn_turn_usd: float = 0.50  # cost of the last turn that triggers a handoff
    block_turn_usd: float = 3.00  # cost of the last turn that blocks prompts
    warn_session_usd: float = 20.0  # whole-session cost that triggers a handoff
    auto_handoff: bool = True  # ask Claude to write the note itself
    max_age_min: int = 180  # notes older than this are not resumed
    handoff_dir: str = ""
    state_dir: str = ""
    prices: dict = field(default_factory=lambda: dict(DEFAULT_PRICES))

    @property
    def notes(self) -> Path:
        return Path(self.handoff_dir) if self.handoff_dir else _home() / ".claude" / "handoffs"

    @property
    def state(self) -> Path:
        return Path(self.state_dir) if self.state_dir else _home() / ".claude" / "context-handoff"


def _coerce(kind, value):
    if kind is bool or kind == "bool":
        return str(value).strip().lower() in ("1", "true", "yes", "on")
    if kind is int or kind == "int":
        return int(float(value))
    if kind is float or kind == "float":
        return float(value)
    return str(value)


def load(path: str | Path | None = None) -> Config:
    cfg = Config()
    path = Path(path) if path else Path(
        os.environ.get("CONTEXT_HANDOFF_CONFIG") or _home() / ".claude" / "context-handoff.json"
    )
    data: dict = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            data = {}
    for f in fields(Config):
        if f.name == "prices":
            continue
        env = os.environ.get("CONTEXT_HANDOFF_" + f.name.upper())
        raw = env if env not in (None, "") else data.get(f.name)
        if raw is not None:
            try:
                setattr(cfg, f.name, _coerce(f.type, raw))
            except (TypeError, ValueError):
                pass
    for prefix, row in (data.get("prices") or {}).items():
        try:
            i, o, r = (float(x) for x in row)
            cfg.prices[prefix] = (i, o, r)
        except (TypeError, ValueError):
            pass
    return cfg
