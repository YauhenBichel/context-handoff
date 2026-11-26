---
description: Save a short handoff note so this session can end and a fresh one can continue cheaply
---

This session is being closed to stop re-sending its long context on every turn. Write a handoff note that lets a fresh session continue with no other context.

Save it to the path the context-handoff hook gave you in this turn: the line that starts with `[context-handoff] Handoff note path:`. Use that path exactly as given and write one file only. Do not build the file name, the project or the time yourself, and do not save copies under other names. If this turn has no such line (the hook did not run), run `python3 "${CLAUDE_PLUGIN_ROOT}/bin/context-handoff" note-path` once and use the path it prints. Create the folder if needed. Keep it under 60 lines and write only what the next session cannot get from the repository, git history or memory:

- **Goal**: what the owner asked for, in one or two lines.
- **State**: what is done and verified, what is half-done, and what is unverified.
- **Decisions made**, with the reason, so they are not re-litigated.
- **Open items and next steps**, in order.
- **Where things are**: branches, PR numbers, files, services, commands to re-check state.
- **Gotchas** found this session.

No code dumps or logs: point to files and commits instead. Do not include secrets, keys, tokens or personal data.

$ARGUMENTS

Then reply with only two lines: the note's path, and "Run /clear, then type go." (The plugin's SessionStart hook loads the newest unused note for this working directory after /clear.) If the owner opens a new window instead of /clear, the fallback first prompt is `Read <path> and continue from "Open items and next steps".`
