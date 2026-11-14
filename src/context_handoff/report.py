"""What Claude Code sessions cost, from local transcripts (API list prices)."""

from __future__ import annotations

import time
from pathlib import Path

from . import transcript
from .config import Config
from .prices import lookup


def rows(cfg: Config, days: int, root: Path | None = None):
    root = root or Path.home() / ".claude" / "projects"
    cutoff = time.time() - days * 86400
    for f in root.glob("*/*.jsonl"):
        try:
            if f.stat().st_mtime < cutoff:
                continue
        except OSError:
            continue
        s = transcript.read(f)
        if not s.turns:
            continue
        peak = max(t.context for t in s.turns)
        cold = s.last.context * lookup(s.last.model, cfg.prices).write_1h / 1e6
        yield {
            "project": f.parent.name, "session": f.stem[:8], "turns": len(s.turns),
            "usd": s.cost(cfg.prices), "peak_k": peak // 1000, "cold_usd": cold,
        }


def render(cfg: Config, days: int = 7, root: Path | None = None, top: int = 15) -> str:
    data = sorted(rows(cfg, days, root), key=lambda r: r["usd"], reverse=True)
    if not data:
        return f"no sessions in the last {days} days"
    total = sum(r["usd"] for r in data)
    over = sum(1 for r in data if r["peak_k"] >= cfg.warn_k)
    out = [
        f"last {days} days: {len(data)} sessions, ${total:.2f} at API list prices, "
        f"{over} sessions peaked over {cfg.warn_k}K context",
        "",
        f"{'usd':>9} {'turns':>6} {'peak(K)':>8} {'cold turn':>10}  project / session",
    ]
    for r in data[:top]:
        out.append(
            f"{r['usd']:>9.2f} {r['turns']:>6} {r['peak_k']:>8} {r['cold_usd']:>10.2f}  "
            f"{r['project']} / {r['session']}"
        )
    return "\n".join(out)
