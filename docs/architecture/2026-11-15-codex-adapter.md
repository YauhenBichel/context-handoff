# Codex CLI adapter: design

Date: 15 November 2026. Follows [2026-11-15-other-agents.md](2026-11-15-other-agents.md),
which chose Codex as the second tool, before Cursor.

## Goal

Give Codex sessions the same three behaviours that Claude Code sessions have:

1. **Meter**: on each prompt, read the session's token usage, warn or block when the
   session gets expensive, and ask the agent for a handoff note.
2. **Resume**: after a new session or a compaction, load the newest handoff note.
3. **Compaction as handoff**: make the compaction summary read like a handoff note.

Keep one tool-neutral core and one thin adapter per tool, in this repository.

## Facts checked on this Mac (15 Nov 2026)

Codex CLI 0.155.0-alpha.16.4 (bundled in Codex.app); rollout files also from the
VS Code extension 0.164.0-alpha.11.1.

### Rollout files (answers open question 4)

`~/.codex/sessions/YYYY/MM/DD/rollout-<timestamp>-<thread id>.jsonl`, one JSON object
per line with `timestamp`, `type`, `payload`. Usage appears twice per model reply:

```json
{"type":"event_msg","payload":{"type":"token_count","info":{
  "total_token_usage":{"input_tokens":223685,"cached_input_tokens":194441,
    "cache_write_input_tokens":29217,"output_tokens":1676,
    "reasoning_output_tokens":247,"total_tokens":225361},
  "last_token_usage":{"input_tokens":29220,"cached_input_tokens":29095,
    "cache_write_input_tokens":122,"output_tokens":745,
    "reasoning_output_tokens":103,"total_tokens":29965},
  "model_context_window":258400},"rate_limits":null}}

{"type":"token_usage_record","payload":{"thread_id":"…","turn_id":"…",
  "response_id":"resp_…","usage":{…same fields as last_token_usage…},
  "turn_token_usage":{…}}}
```

- `input_tokens` **includes** cached and cache-write tokens (29220 = 29095 + 122 + 3).
  Claude reports the three separately. Uncached input = input − cached − cache_write.
- `reasoning_output_tokens` is a part of `output_tokens`, not extra.
- The model is in `turn_context.payload.model` (e.g. `gpt-5.6-sol`), not on the usage line.
- `token_usage_record` carries `response_id`: use it as the de-duplication key, as
  `message.id` is for Claude.
- A compaction writes a `{"type":"compacted"}` line (keys include `window_number`,
  `replacement_history`, `latest_token_usage_record`). Usage after it is the new,
  smaller window.

### Hooks

- Config: `~/.codex/hooks.json` (same shape as Claude Code's), feature `hooks`
  (stable, on by default). Events: PreToolUse, PermissionRequest, PostToolUse,
  PreCompact, PostCompact, SessionStart, SessionEnd, UserPromptSubmit,
  SubagentStart, SubagentStop, Stop, Interrupt. **No PostModelRequest** in 0.155.
- **Every hook must be approved once by the user** in the interactive Codex start
  screen ("hooks need review before they can run"). Approval is stored in
  `~/.codex/config.toml` as
  `[hooks.state."<hooks.json path>:<event>:<group>:<index>"] trusted_hash = "sha256:…"`.
  `codex exec` silently skips hooks that have not been approved. Changing the hook
  command changes the hash and needs approval again.
- Payloads carry `session_id`, `transcript_path` (the rollout file), `cwd`, `model`,
  `hook_event_name`; SessionStart adds `source`, PostCompact adds `trigger` and `turn_id`.
- `hookSpecificOutput.additionalContext` is accepted for SessionStart,
  UserPromptSubmit, SubagentStart, PreToolUse, PostToolUse, PermissionRequest.

### PostCompact cannot inject; SessionStart(compact) can (answers open question 5)

Live test: hooks on SessionStart and PostCompact, each returning a marker in
`additionalContext`; auto-compaction forced with `-c model_auto_compact_token_limit=2000`.

- PostCompact ran with `trigger: "auto"`, and Codex reported **"PostCompact Failed"**:
  its output schema has no `hookSpecificOutput`.
- Right after it, **SessionStart ran again with `source: "compact"`**, and the model
  saw that marker. The SessionStart `source` values seen: `startup`, `compact`.

So resume works exactly as on Claude Code: one SessionStart hook that acts on
`compact` (and on `startup`/`clear`, see below).

### Compaction instructions

PreCompact's output has no field for extra instructions. Codex has a
`compact_prompt` key in `config.toml` instead. Behaviour 3 becomes a config value
the installer offers to set, not a hook.

## Design

### Package layout

```
src/context_handoff/
  core/            tool-neutral
    usage.py       Turn, Session (today's transcript.Turn/Session, generalised)
    meter.py       reasons(), thresholds, the warn/block decision, log
    notes.py       note_path(), find_note(), note_instructions()
    prices.py      price table, now with OpenAI models
  adapters/
    claude.py      read_transcript(), hook output shapes  (today's code, moved)
    codex.py       read_rollout(), hook output shapes, compact_prompt
  __main__.py      `context-handoff --tool claude|codex <command>`
```

The move of Claude code into `adapters/claude.py` is a pure refactor in its own PR,
with the existing tests passing unchanged, before any Codex code lands.

### Usage model

Make `Turn` neutral: `uncached_input`, `cache_write`, `cache_read`, `output`, plus a
`cache_write_ttl` field the Claude reader fills (5m / 1h) and the Codex reader
leaves as `None`. `Turn.context` stays "tokens the next turn re-sends":

- Claude: input + cache writes + cache reads (as today).
- Codex: `input_tokens` from `last_token_usage`.

The Codex reader keeps one turn per `response_id`, takes the model from the latest
`turn_context` before it, and ignores lines from sub-agents (to be checked: whether
sub-agent replies share the rollout file).

### Prices

Add OpenAI models to `prices.py` with input, output, cached-input and cache-write
rates. The dollar figure is labelled "list-price equivalent" for Codex sessions on a
ChatGPT plan, where the owner pays in credits, not dollars (open question 9 stays
open; the token figures are exact either way).

### Hooks shipped for Codex

`codex/hooks.json`, installed into `~/.codex/hooks.json` (merged, not overwritten):

| Event | Command | Output |
|---|---|---|
| UserPromptSubmit | `context-handoff --tool codex meter` | `decision: block` + `reason`, or `additionalContext` asking for a note, plus `systemMessage` |
| SessionStart (matcher `startup\|clear\|compact`) | `context-handoff --tool codex resume` | `additionalContext` with the note |

`startup` is included because a Codex user ends a session with a new one rather than
`/clear`; `find_note` already only loads a fresh, unused note for the same `cwd`.
To be confirmed: the `source` value Codex sends for `/new` and `/clear`.

### Install

`context-handoff install codex`:

1. Merges the two hooks into `~/.codex/hooks.json`, keeping other hooks.
2. Offers to set `compact_prompt` in `~/.codex/config.toml` to the handoff
   instructions (shown first; off by default if the key is already set).
3. Prints: "Open Codex once and approve the two context-handoff hooks; until then
   they do not run." `context-handoff doctor codex` checks for the trust entries.

The installer never writes `trusted_hash` itself: approval stays the user's act.

### Notes directory

One shared directory for all tools (open question 7): a note is plain Markdown keyed
by `cwd`, so a note written in Claude Code can be resumed in Codex. Each note records
the tool that wrote it in its header line.

## Plan (one PR each)

1. Refactor: move Claude-specific code into `adapters/claude.py`, add `--tool`
   (default `claude`). No behaviour change; tests unchanged.
2. Codex rollout reader + tests built from a trimmed, anonymised rollout fixture
   (structure only, no conversation text).
3. OpenAI prices.
4. Codex hook outputs (meter, resume) + `codex/hooks.json` + tests on recorded payloads.
5. `install codex` / `doctor codex`, README section, CHANGELOG, release 0.2.0.

## Still open

- `source` values for `/new` and `/clear` in Codex.
- Whether sub-agent turns go into the parent rollout file.
- Whether `UserPromptSubmit` `decision: block` shows the reason to the user in the
  Codex TUI and in the VS Code extension (Claude Code's VS Code extension does not
  show hook messages; 0.1.5 relays them).
- Cache TTL for Codex (30 min to 24 h per OpenAI) for the "cold turn" figure.
- Open question 9 (credits vs list prices).
