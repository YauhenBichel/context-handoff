# Changelog

## Unreleased

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
