# context-handoff

A Claude Code plugin that keeps long sessions from getting expensive.

Every Claude Code turn re-sends the whole conversation. While the prompt cache
is warm that re-read is cheap; after a pause the whole context is written to
the cache again at up to 2× the input price. A 400K-token session on Claude
Opus 5.5 pays about $3.20 for one such cold turn, before Claude writes a word.
Long sessions also get slower and lose focus.

context-handoff watches what each turn costs. When a session gets too big or
too expensive, Claude writes a short handoff note at the end of the current
task. You run `/clear`, type `go`, and a fresh, small session continues from
the note.

## How it works

1. **Meter** (`UserPromptSubmit` hook). Before each prompt it reads the
   session transcript and computes, at API list prices:
   - the context the next turn will re-send,
   - what the last turn cost,
   - what the whole session cost,
   - what one cold turn would cost now.
2. **Auto handoff**. Over a warn limit, it asks Claude (once per session) to
   write a handoff note when the current task is done.
3. **Block**. Over a block limit, it holds the prompt until you type `handoff`
   or add `#override`.
4. **Resume** (`SessionStart` hook, after `/clear`). It loads the project's
   newest unused note into the new session, so you type `go` instead of
   pasting a prompt. Each note is loaded once.

## Install

In Claude Code:

```
/plugin marketplace add YauhenBichel/context-handoff
/plugin install context-handoff@context-handoff
```

Requires Python 3.10 or newer on `PATH` as `python3`. No other dependencies.

## Use

- **Normal flow**: keep working. When the meter asks, Claude writes the note
  after the current task and tells you. Run `/clear`, then type `go`.
- **By hand**: `/context-handoff:handoff`, then `/clear` and `go`.
- **Past a block**: start the prompt with `handoff`, or add `#override`.
- **Check a session**: `python3 bin/context-handoff check <transcript.jsonl>`.
- **Report** of the last N days (default 7):
  `python3 bin/context-handoff report 14`.

## Settings

Defaults, then `~/.claude/context-handoff.json`, then environment variables
(`CONTEXT_HANDOFF_` + the key in upper case). A limit of 0 turns it off.

| Key | Default | Meaning |
|---|---|---|
| `warn_k` | 150 | context size (thousands of tokens) that triggers a handoff |
| `block_k` | 400 | context size that blocks prompts |
| `warn_turn_usd` | 0.50 | cost of the last turn that triggers a handoff |
| `block_turn_usd` | 3.00 | cost of the last turn that blocks prompts |
| `warn_session_usd` | 20 | session total that triggers a handoff |
| `auto_handoff` | true | Claude writes the note itself; false = only a warning |
| `max_age_min` | 180 | notes older than this are not resumed |
| `handoff_dir` | `~/.claude/handoffs` | where notes go |
| `state_dir` | `~/.claude/context-handoff` | log (`meter.jsonl`) and per-session markers |
| `prices` | see [prices.py](src/context_handoff/prices.py) | `{"model-prefix": [input, output, cache_read]}` per million tokens |

Example `~/.claude/context-handoff.json`:

```json
{ "warn_turn_usd": 1.0, "warn_session_usd": 50, "prices": { "claude-opus-5-5": [4.0, 20.0, 0.20] } }
```

## Prices

The default table holds Anthropic's first-party API list prices as of November
2026. Cache writes are priced at 1.25× input (5-minute TTL) or 2× input (1-hour
TTL). On a Claude subscription you do not pay per token, but the same numbers
show how fast a session uses your limits. Prices change: override them in the
config file.

## Limits

- A plugin cannot run `/clear` for you. That one step stays manual.
- Notes are matched by the project folder's name, and only those newer than
  `max_age_min` are loaded.
- The meter reads the transcript, so the first prompt of a session is not
  metered.
- Costs are estimates from the transcript's usage fields, not your bill.

## Privacy

Everything runs locally. The plugin reads your transcripts in `~/.claude` and
writes notes and a log there. Nothing is sent anywhere. Do not put secrets in
handoff notes.

## Development

```
python3 -m unittest discover -s tests
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT, see [LICENSE](LICENSE).
