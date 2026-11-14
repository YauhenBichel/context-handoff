---
description: Save a short handoff note so this session can end and a fresh one can continue cheaply
---

This session is being closed to stop re-sending its long context on every turn. Write a handoff note that lets a fresh session continue with no other context.

Save it to `~/.claude/handoffs/<project>-<YYYYMMDD-HHMM>.md` (or `$CONTEXT_HANDOFF_DIR` if set), where `<project>` is the basename of the current working directory. Create the folder if needed. Keep it under 60 lines and write only what the next session cannot get from the repository, git history or memory:

- **Goal**: what the owner asked for, in one or two lines.
- **State**: what is done and verified, what is half-done, and what is unverified.
- **Decisions made**, with the reason, so they are not re-litigated.
- **Open items and next steps**, in order.
- **Where things are**: branches, PR numbers, files, services, commands to re-check state.
- **Gotchas** found this session.

No code dumps or logs: point to files and commits instead. Do not include secrets, keys, tokens or personal data.

$ARGUMENTS

Then reply with only two lines: the note's path, and "Run /clear, then type go." (The plugin's SessionStart hook loads the newest unused note for this project after /clear.) If the owner opens a new window instead of /clear, the fallback first prompt is `Read <path> and continue from "Open items and next steps".`
