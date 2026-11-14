"""context-handoff entry point.

    context-handoff meter    UserPromptSubmit hook (reads hook JSON on stdin)
    context-handoff resume   SessionStart hook (reads hook JSON on stdin)
    context-handoff precompact   PreCompact hook: prints compaction instructions
    context-handoff report [days]
    context-handoff check <transcript.jsonl>   print what the meter sees

Options (before the command):
    --tool NAME   the agent tool whose session files are read (default: claude)

Hooks never fail the session: any error ends with no output and exit 0.
"""

from __future__ import annotations

import json
import sys

from . import adapters, compact, config, meter, report, resume


def _hook(fn, **kwargs) -> int:
    try:
        event = json.load(sys.stdin)
        out = fn(event, config.load(), **kwargs)
    except Exception as exc:  # a hook must never break the session
        print(f"context-handoff: {exc}", file=sys.stderr)
        return 0
    if out:
        print(out if isinstance(out, str) else json.dumps(out))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    tool = adapters.DEFAULT
    if argv[:1] == ["--tool"]:
        if len(argv) < 2 or argv[1] not in adapters.TOOLS:
            print(f"context-handoff: --tool takes one of: {', '.join(adapters.TOOLS)}", file=sys.stderr)
            return 2
        tool, argv = argv[1], argv[2:]
    cmd = argv[0] if argv else ""
    if cmd == "meter":
        return _hook(meter.run, tool=tool)
    if cmd == "resume":
        return _hook(resume.run)
    if cmd == "precompact":
        return _hook(compact.run)
    if cmd == "report":
        days = int(argv[1]) if len(argv) > 1 else 7
        print(report.render(config.load(), days))
        return 0
    if cmd == "check" and len(argv) > 1:
        cfg = config.load()
        r = meter.measure(argv[1], cfg, tool)
        if r is None:
            print(f"no {tool} replies in that transcript")
            return 1
        block, warn = meter.reasons(r, cfg)
        print(r.summary())
        print("block:", "; ".join(block) or "no")
        print("warn: ", "; ".join(warn) or "no")
        return 0
    print(__doc__.strip())
    return 2


if __name__ == "__main__":
    sys.exit(main())
