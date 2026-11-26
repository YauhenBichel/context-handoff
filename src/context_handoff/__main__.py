"""context-handoff entry point.

    context-handoff meter    UserPromptSubmit hook (reads hook JSON on stdin)
    context-handoff resume   SessionStart hook (reads hook JSON on stdin)
    context-handoff precompact   PreCompact hook: prints compaction instructions
    context-handoff report [days]
    context-handoff check <transcript.jsonl>   print what the meter sees
    context-handoff note-path [cwd]   print the path for a new handoff note

Options (before the command):
    --tool NAME   the agent tool whose session files are read (default: claude)

Hooks never fail the session: any error ends with no output and exit 0.
"""

from __future__ import annotations

import json
import os
import sys

from . import adapters, config, meter, notes, report
from .adapters.base import Adapter
from .handlers import compact as compact_handler
from .handlers import meter as meter_handler
from .handlers import resume as resume_handler

HOOKS = {
    "meter": meter_handler.run,
    "resume": resume_handler.run,
    "precompact": compact_handler.run,
}


def _hook(handler, adapter: Adapter) -> int:
    try:
        event = json.load(sys.stdin)
        out = handler(event, config.load(), adapter)
    except Exception as exc:  # a hook must never break the session
        print(f"context-handoff: {exc}", file=sys.stderr)
        return 0
    if out:
        print(out if isinstance(out, str) else json.dumps(out))
    return 0


def _report(args: list[str], adapter: Adapter) -> int:
    days = int(args[0]) if args else 7
    print(report.render(config.load(), days, adapter=adapter))
    return 0


def _check(args: list[str], adapter: Adapter) -> int:
    cfg = config.load()
    r = meter.measure(adapter.read(args[0]), cfg.prices)
    if r is None:
        print(f"no {adapter.agent} replies in that transcript")
        return 1
    block, warn = meter.reasons(r, cfg)
    print(r.summary())
    print("block:", "; ".join(block) or "no")
    print("warn: ", "; ".join(warn) or "no")
    return 0


def _note_path(args: list[str]) -> int:
    """For the /handoff command when the hook gave no path: the code names the note, not the agent."""
    print(notes.NoteStore.from_config(config.load()).new_path(args[0] if args else os.getcwd()))
    return 0


def _usage() -> int:
    print(__doc__.strip())
    return 2


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    tool = adapters.DEFAULT
    if argv[:1] == ["--tool"]:
        if len(argv) < 2 or argv[1] not in adapters.TOOLS:
            print(f"context-handoff: --tool takes one of: {', '.join(adapters.TOOLS)}", file=sys.stderr)
            return 2
        tool, argv = argv[1], argv[2:]
    adapter = adapters.get(tool)
    cmd, args = (argv[0], argv[1:]) if argv else ("", [])
    if cmd in HOOKS:
        return _hook(HOOKS[cmd], adapter)
    if cmd == "report":
        return _report(args, adapter)
    if cmd == "check" and args:
        return _check(args, adapter)
    if cmd == "note-path":
        return _note_path(args)
    return _usage()


if __name__ == "__main__":
    sys.exit(main())
