"""PreCompact hook: make the compaction summary work like a handoff note.

Claude Code appends this hook's stdout to its compaction instructions. After an
automatic compaction the session continues by itself, so with a lower
auto-compact window (the `autoCompactWindow` setting or
CLAUDE_CODE_AUTO_COMPACT_WINDOW) a long session shrinks and goes on without
/clear and without typing go.
"""

from __future__ import annotations

from .config import Config

INSTRUCTIONS = """\
Write the summary as a handoff note that lets the session continue with no other context:
- Goal: what the owner asked for, in one or two lines.
- State: what is done and verified, what is half-done, what is unverified.
- Decisions made, with the reason, so they are not re-litigated.
- Open items and next steps, in order, the very next step first.
- Where things are: exact branches, PR numbers, file paths, services, commands to re-check state.
- Gotchas found in this session.
Keep exact names, paths and numbers. Leave out code dumps and logs; point to files instead.
Do not include secrets, keys, tokens or personal data."""


def run(event: dict, cfg: Config) -> str:
    return INSTRUCTIONS
