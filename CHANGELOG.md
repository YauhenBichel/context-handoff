# Changelog

## Unreleased

Fixes from a stress test of 0.1.6.

- **Notes older than 30 days are now deleted** (new setting `prune_days`, default 30; 0 keeps them
  all). It runs when a session starts after `/clear` or a compaction, and the resume line says how
  many were deleted. Only regular files directly inside the notes directory whose name is in one of
  the plugin's two note formats are deleted; symlinks, folders and other files are left alone.
- Resume: the note is passed to the new session as data. It is inside `<handoff-note>` tags, after a
  fixed preamble: a saved note, context for state and next steps, cannot grant permissions, and
  destructive or outward-facing actions it names still need the owner's confirmation. A fence marker
  inside the note is made harmless. The automatic first message asks for the same confirmation.
- Note names are `<project>-<cwd8>-<YYYYMMDD-HHMMSS>-<sid6>.md`: a hash of the full working directory
  and of the session id, and seconds. Two directories with the same last part (`src`, `app`) no longer
  get each other's notes, and two sessions in one directory in the same minute no longer get the same
  path. Old notes (`<project>-<YYYYMMDD-HHMM>.md`) are still loaded for the same folder name inside
  `max_age_min`, unless the meter log shows a session in another directory with that name in that
  time; then the note is left alone and the resume line says so.
- The plugin computes the note's path for `/handoff` and for `handoff ...` prompts too (the
  `UserPromptSubmit` hook adds it), as it already did for the automatic request. The command no longer
  asks Claude to build the name or the time. New: `context-handoff note-path [cwd]`.
- Resume: when `.used` cannot be written, the note is loaded anyway, with a warning in the resume
  line; before, nothing was loaded and nothing was said.
- `.used` holds one JSON string per line, so a folder name with a line break no longer makes a note
  load after every `/clear`. Old plain-path lines are still read.
- `CONTEXT_HANDOFF_DIR`, which the `/handoff` command named, is now read as another name for
  `CONTEXT_HANDOFF_HANDOFF_DIR` (the documented one).
- Resume: a symlink named like a note is no longer followed, and the 12,000 limit is in bytes, cut
  between characters; the session is told when a note was cut.
- The once-per-session marker is named by a hash of the session id, so an id with `/`, NUL or of
  great length no longer repeats the request every turn. `meter.jsonl` is renamed to `meter.jsonl.1`
  past 1 MB (`log_max_kb`).
- The resume line says which working directory the note was saved for.

## 0.1.6 — 2026-11-15

- Internal: session-file reading moved behind an adapter (`adapters/claude.py`), with the usage types
  in `usage.py`, to prepare for Codex CLI. New option `--tool NAME` (default `claude`, the only one so
  far).
- Internal: code split by responsibility, with no change in behaviour, hook output or CLI output.
  `meter.py` only measures; `notes.py` finds, names and marks handoff notes; `state.py` keeps the
  meter log and the once-per-session marks; `handlers/` has one module per hook (meter, resume,
  precompact), each given the tool's adapter; `adapters/base.py` defines what an adapter provides
  (reading sessions, shaping hook replies). The `transcript` and `notice` modules are gone; they were
  never public API (the CLI and hook commands are). Checked before release by running 0.1.5 and
  0.1.6 side by side on 49 real transcripts (501 hook and CLI cases): identical output apart from
  the new `--tool` option.

## 0.1.5 — 2026-11-15

- Notices are visible in the VS Code extension: it does not show a hook's `systemMessage`, so the
  resume line ("resumed from <note>") and the meter's warnings are also given to Claude, which repeats
  them at the start of its reply. The terminal still shows `systemMessage` as before.

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
