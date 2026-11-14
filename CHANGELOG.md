# Changelog

## 0.1.0 — 2026-11-14

First release.

- Meter (`UserPromptSubmit` hook): context size, last-turn cost, session cost
  and cold-turn cost at API list prices, shown above each prompt.
- Auto handoff: over a warn limit Claude writes a handoff note at the end of
  the current task; over a block limit prompts are held until `handoff` or
  `#override`.
- Resume (`SessionStart` hook): after `/clear` the newest unused note for the
  project is loaded, so `go` continues the work.
- `/context-handoff:handoff` command, `check` and `report` CLI.
- Python 3.10+, standard library only. Tested on Ubuntu and macOS.
