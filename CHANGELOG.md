# Changelog

## 0.1.4 — 2026-11-14

- Continue without typing `go`: a `PreCompact` hook makes Claude Code's compaction summary follow the
  handoff note's sections, and the `SessionStart` hook also runs after a compaction, adding the newest
  unused note next to the summary (the note stays unused, so a later `/clear` still loads it). With a
  lower auto-compact window (`autoCompactWindow` or `CLAUDE_CODE_AUTO_COMPACT_WINDOW`) a long session
  shrinks and carries on by itself. See README, "Hands-free: auto-compact".
- Found: Claude Code 2.1.263 ignores `initialUserMessage` after `/clear`, so `go` is still needed there.

## 0.1.3 — 2026-11-14

- Resume: the `SessionStart` hook also sends `initialUserMessage`, so after `/clear` the new session
  continues from the note without typing `go`. If a Claude Code version ignores it after `/clear`, typing
  `go` still works as before.

## 0.1.2 — 2026-11-14

- Fix: `report N` counted every reply of any session file touched in the last N days, including
  replies from weeks before. It now counts only replies dated inside the window, so long-lived
  sessions no longer inflate the total.
- README: a demo of `report` and `check` on real sessions, and a FAQ.
- A GitHub Pages site in `docs/` with a sitemap and `llms.txt`, so search engines and LLM tools can find the project.

## 0.1.1 — 2026-11-14

- Also published on PyPI: `pipx install context-handoff` gives the `context-handoff` command (`report`,
  `check`) without Claude Code plugins. The plugin itself is unchanged and still needs no pip install.
- One version for both: `plugin.json` and the package version are checked by a test, and the release tag
  must match.

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
