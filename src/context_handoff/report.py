"""What past sessions cost, from local session files (API list prices)."""

from __future__ import annotations

import time
from pathlib import Path

from . import adapters
from .adapters.base import SessionReader
from .config import Config
from .prices import lookup


def rows(cfg: Config, days: int, root: Path | None = None, adapter: SessionReader | None = None):
    adapter = adapter or adapters.get()
    cutoff = time.time() - days * 86400
    for project, f in adapter.session_files(root):
        try:
            if f.stat().st_mtime < cutoff:
                continue
        except OSError:
            continue
        # A session file can span weeks: count only the replies inside the window.
        s = adapter.read(f).since(cutoff)
        if not s.turns:
            continue
        yield {
            "project": project, "session": f.stem[:8], "turns": len(s.turns),
            "usd": s.cost(cfg.prices), "peak_k": max(t.context for t in s.turns) // 1000,
            "cold_usd": s.last.cold_cost(lookup(s.last.model, cfg.prices)),
        }


def render(cfg: Config, days: int = 7, root: Path | None = None, top: int = 15,
           adapter: SessionReader | None = None) -> str:
    data = sorted(rows(cfg, days, root, adapter), key=lambda r: r["usd"], reverse=True)
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
