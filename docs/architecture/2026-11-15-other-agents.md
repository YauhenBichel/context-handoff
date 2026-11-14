# Can context-handoff be ported to Cursor and Codex CLI?

Date: 15 Nov 2026. Method: official docs fetched on this date, plus Cursor forum threads and third-party pages where the docs are silent. Anything I could not confirm is marked "unconfirmed". Docs pages for Codex have moved: developers.openai.com/codex/* now redirects (HTTP 308) to learn.chatgpt.com/docs/*.

## Answer

Codex CLI: yes, almost one to one. It has the same hook shape as Claude Code (`UserPromptSubmit`, `SessionStart` with a `clear`/`compact` source, `PreCompact`), and it can inject context, block a prompt and show a message. Per-turn token usage arrives in the `PostModelRequest` hook input and in session logs.

Cursor: partly. The hooks exist, but there is no way to inject context in the prompt hook (`beforeSubmitPrompt` can only block), the `sessionStart` context injection is a confirmed Cursor bug, and no token usage is stored in transcripts or hook payloads. A Cursor port can warn and block, but it cannot compute cost. It can only estimate context size, or read it from `preCompact`.

## Comparison

| Capability | Claude Code | Cursor (editor + cursor-agent) | Codex CLI |
|---|---|---|---|
| Meter (context, turn and session cost) | yes: reads transcript JSONL | partial: no usage data on disk or in hooks; size only by estimate | yes: `token_count` in session logs, `token_usage` in `PostModelRequest` hook |
| Warn via injected context | yes: `additionalContext` on UserPromptSubmit | partial: not on `beforeSubmitPrompt`; `sessionStart`/`postToolUse` `additional_context` exist but are buggy; `stop` `followup_message` can auto-send a follow-up | yes: `hookSpecificOutput.additionalContext` on UserPromptSubmit |
| Block a prompt | yes | yes: `beforeSubmitPrompt` `continue:false` + `user_message` | yes: `decision:"block"` + `reason`, or exit code 2 |
| Visible notice to user | yes | yes: `user_message` | yes: `systemMessage` |
| Resume after reset | yes: SessionStart `clear\|compact` | partial: `sessionStart` fires but injection is a known bug; no after-compact trigger confirmed | yes: SessionStart with source `clear`, `compact`, `startup`, `resume`, `fork` |
| Compaction hook | yes: PreCompact | partial: `preCompact` exists but is observational (only `user_message`) | yes: `PreCompact` and `PostCompact`; no `additionalContext` on PreCompact; `compact_prompt` config overrides the prompt |
| Usage data | yes | no (as of the forum posts below) | yes, with caveats |
| Cache pricing | yes: cache write surcharge (per local meter) | partial: pass-through list price; write surcharge on some models | partial: auto cache, discounted reads; write charge depends on billing mode |

"Claude Code" column is from the local repo (README.md, hooks/hooks.json), not from the web.

## Cursor (editor and cursor-agent CLI)

### Hooks
Source: https://cursor.com/docs/hooks

- Events (names as documented): `sessionStart`, `sessionEnd`, `preToolUse`, `postToolUse`, `postToolUseFailure`, `subagentStart`, `subagentStop`, `beforeShellExecution`, `afterShellExecution`, `beforeMCPExecution`, `afterMCPExecution`, `beforeReadFile`, `afterFileEdit`, `beforeSubmitPrompt`, `preCompact`, `stop`, `afterAgentResponse`, `afterAgentThought`, `beforeTabFileRead`, `afterTabFileEdit`, `workspaceOpen`.
- Common input: `conversation_id`, `generation_id`, `model`, `hook_event_name`, `cursor_version`, `workspace_roots`, `user_email`, `transcript_path`.
- (a) Inject context: `additional_context` on `sessionStart`, `postToolUse`, `postToolUseFailure`. `beforeSubmitPrompt` output is only `continue` and `user_message`. `stop` and `subagentStop` return `followup_message`, which auto-submits a next message.
- (b) Block: `beforeSubmitPrompt` with `continue:false`, and `user_message` is shown to the user.
- (c) Show message: `user_message` on `beforeSubmitPrompt`, `preCompact` and the tool hooks.
- (d) Session start: `sessionStart` (input adds `session_id`, `is_background_agent`, `composer_mode`). The docs say the agent loop does not wait for it. Cloud agents do not run it.
- (e) Compaction: `preCompact` input has `trigger`, `context_usage_percent`, `context_tokens`, `context_window_size`, `message_count`, `messages_to_compact`, `is_first_compaction`. Docs: it "cannot block or modify the compaction behavior". No post-compaction hook is listed.
- Known bug: `sessionStart` `additional_context` is not injected. Cursor staff (Dean Rie, 20 Apr 2026, Cursor 3.1.15) wrote "This is a bug on our side": https://forum.cursor.com/t/sessionstart-hook-additional-context-is-never-injected-into-agents-initial-system-context/158452 . More reports of the same symptom on 3.24.9 and SDK 1.0.28 exist (titles only, via search results). No fix is confirmed in the threads I read.
- Hooks after compaction: a request for `sessionStart` to fire after compaction (23 Apr 2026) has no confirmed implementation: https://forum.cursor.com/t/sessionstart-hook-should-fire-after-compact/158873 . One user there says earlier injected context survives compaction; this is unverified (not staff).
- cursor-agent CLI hooks: the official CLI page (https://cursor.com/docs/cli/overview) does not mention hooks. A third-party integration guide says events fire in recent CLI builds, with early-2026 builds firing only shell hooks. Official confirmation: unconfirmed. A forum report says CLI 2026.08.11 does not run user-level hooks in an interactive session on Windows (via search summary, not opened).

### Transcripts and usage
- Path (forum, not official docs): `~/.cursor/projects/<encoded-cwd>/agent-transcripts/<conversation_id>/<conversation_id>.jsonl`, rows carry `role` and `message` only: https://forum.cursor.com/t/richer-agent-transcripts-lifecycle-data-for-observability-langfuse-stop-hooks/166592 . No official schema found: unconfirmed.
- Token usage: not in transcripts, and `tokenCount` in `state.vscdb` is always 0 (user report, 18 Oct 2026, no staff reply): https://forum.cursor.com/t/record-token-usage-in-local-agent-transcripts/175149
- Not in the `stop` payload either (Cursor staff, 26 Jul 2026, same thread as above). Whether this changed since: unconfirmed.
- The Cursor dashboard/Analytics API shows usage, but I did not verify what it exposes per session: unconfirmed.

### Reset and compaction
- CLI: `/summarize` frees context, `/compress` is an alias; `/resume`, `/plan`, `/ask` exist: https://cursor.com/docs/cli/using . `/new` in the CLI: unconfirmed.
- Editor: the way to start a new chat is not stated on the pages I fetched: unconfirmed. Automatic summarisation exists in practice (the `preCompact` hook has `trigger`), but whether and how it is configurable: unconfirmed. The summarisation docs page did not cover it: https://cursor.com/docs/agent/chat/summarization

### Pricing
Source: https://cursor.com/docs/account/pricing
- Paid plans have a weekly pool for Cursor models. Claude, GPT and Gemini models bill at API list price from prepaid credit on Premium and above. Teams and Enterprise add $0.25 per 1M tokens on eligible third-party models.
- Cache read is discounted (Claude 4.6 Sonnet: $3 input, $0.3 cache read, $3.75 cache write per 1M). GPT-5.6 Sol cache writes are 1.25x uncached input. Cursor's own models show no cache-write charge.
- Cache lifetime (TTL) is not stated on that page: unconfirmed.

### Rules and commands
- Rules: `.cursor/rules/*.mdc` with `alwaysApply`, `globs`, `description`; `AGENTS.md` in the project root; user and team rules: https://cursor.com/docs/context/rules
- The CLI reads the same rules plus `AGENTS.md` and `CLAUDE.md`: https://cursor.com/docs/cli/using
- Custom slash commands: the docs I fetched only mention them via `/migrate-to-skills`. Skills live in `.cursor/skills/<name>/SKILL.md`: https://cursor.com/docs/context/commands . The commands folder and format: unconfirmed.

## Codex CLI

### Hooks
Source: https://learn.chatgpt.com/docs/hooks (formerly developers.openai.com/codex/hooks)

- Events: `SessionStart`, `SessionEnd`, `UserPromptSubmit`, `PreToolUse`, `PermissionRequest`, `PostToolUse`, `PreCompact`, `PostCompact`, `SubagentStart`, `SubagentStop`, `Stop`, `PreModelRequest`, `PostModelRequest`, `Interrupt`.
- Common input: `session_id`, `transcript_path`, `cwd`, `hook_event_name`, `model`. `UserPromptSubmit` adds `prompt`. `SessionStart` adds `source` (`startup`, `resume`, `clear`, `compact`, `fork`). `PreCompact`/`PostCompact` add `trigger` (`manual`, `auto`). `PostModelRequest` adds `status`, `error`, `token_usage`.
- (a) Inject: `hookSpecificOutput.additionalContext` on `SessionStart`, `UserPromptSubmit` and others; plain stdout also works on those three.
- (b) Block: `UserPromptSubmit` with `decision:"block"` and `reason`, or exit code 2.
- (c) Show: `systemMessage`, shown as a warning.
- (d) Start/reset: `SessionStart` with matcher on `clear|compact`.
- (e) Compaction: `PreCompact` and `PostCompact`. `continue:false` on `PreCompact` stops compaction. `PreCompact` does not accept `additionalContext`. Whether `PostCompact` can inject context: not listed, so I treat it as no.
- Config: `~/.codex/hooks.json` or `config.toml`, and `<repo>/.codex/...` (only if the project layer is trusted). Non-managed hooks must be reviewed with `/hooks` before they run. Hooks can be turned off with `[features] hooks = false`.
- Hook JSON shape matches Claude Code's `hooks.json` closely (matcher, `type:"command"`, `timeout`).
- Exact `token_usage` field names inside `PostModelRequest`: unconfirmed (the page summary did not list them).

### Transcripts and usage
- Path and format: JSONL "rollout" files under `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`. This comes from GitHub issues and third-party write-ups, not an official doc page I found: https://github.com/openai/codex/issues/32479 , https://codex.danielvaughan.com/2026/03/30/codex-cli-session-analytics-jsonl-rollout . Official schema: unconfirmed.
- `token_count` events hold `info.total_token_usage` and `info.last_token_usage`, with `cached_input_tokens` as a subset of `input_tokens` (same sources). Use deltas of the totals, not sums, to avoid double counting.
- `cache_write_input_tokens` was added in openai/codex#33454, merged 16 Jul 2026, so older sessions lack it (via https://github.com/microsoft/AI-Engineering-Coach/issues/355). Schema changes across versions: parse defensively.
- Separately, `history.persistence` (`save-all` or `none`) controls whether transcripts go to `history.jsonl`: https://learn.chatgpt.com/docs/config-file/config-reference

### Reset and compaction
Source: https://learn.chatgpt.com/docs/developer-commands?surface=cli
- `/new` starts a new chat; `/clear` clears the terminal and starts a new chat; `/compact` summarises and frees context; `/resume` resumes a saved chat; `/status` shows token usage; `/usage` shows ChatGPT token activity.
- Auto compaction exists and is configurable: `model_auto_compact_token_limit` (token threshold), `compact_prompt` (inline override), `experimental_compact_prompt_file`: https://learn.chatgpt.com/docs/config-file/config-reference . So the compaction prompt can carry the handoff sections, without a hook.

### Pricing
- Codex is included in ChatGPT plans (usage limits, credits). With an API key it bills at API rates. The credit table has a cached-input column (for example 50 credits vs 2.5 credits per 1M for one model). "Codex credit billing has no separate cache-write charge": https://learn.chatgpt.com/docs/pricing
- API prompt caching: automatic, needs prompts of 1024 tokens or more, cached prefix eligible for at least 30 minutes, extended retention up to 24 hours: https://developers.openai.com/docs/guides/prompt-caching
- For GPT-5.6 and later, API cache writes at 1.25x input rate: stated on the Cursor pricing page for GPT-5.6 Sol (above); for the OpenAI API itself it is only a community post, so unconfirmed there.
- Exact cached-read discount for the API: third parties say 90%; OpenAI's guide points to its pricing page. Unconfirmed from primary source.

### Instructions and commands
- `AGENTS.md` is the instruction file; `/init` creates it. `/skills` selects skills. `/presets` saves prompts or slash commands in slots: https://learn.chatgpt.com/docs/developer-commands?surface=cli
- Custom prompt files such as `~/.codex/prompts/*.md`: unconfirmed.

## Proposed design

Split the package into a tool-neutral core plus one thin adapter per tool.

Core (reuse the existing Python):
- Notes: write, list, mark-used. Today in `~/.claude/handoffs`; make the directory configurable, one store shared by all tools (decision needed).
- Resume: pick the newest unused note for a project, return text.
- Report: cost table. Needs a `Usage` record (input, cached input, cache write, output, model, time) that each adapter fills in.
- Pricing table per model, with separate cache-read and cache-write prices. List prices only, as today.

Adapters and rough size:

| Adapter | Size | What it does |
|---|---|---|
| Claude Code (exists) | done | as today |
| Codex CLI | S to M | `hooks.json` with `UserPromptSubmit` (meter, warn, block), `SessionStart` `clear\|compact` (resume), `PreCompact` (log only). Parser for rollout JSONL, or use `PostModelRequest.token_usage`. Put the handoff section list into `compact_prompt`. Add an `AGENTS.md` snippet for the "write a handoff note" instruction. Install by copying config and trusting via `/hooks`. |
| Cursor | M to L | `beforeSubmitPrompt` for block only. Warning via `stop` `followup_message` (asks the model to write the note) or `.cursor/rules` always-apply rule. Resume via `sessionStart` once the bug is fixed; fallback is a rule or a manual command that reads the newest note. Meter without usage data: estimate tokens from transcript size, or use `preCompact` `context_tokens`. No real cost report. |

Why Cursor is bigger: the missing prompt-time injection, the sessionStart bug, and the lack of usage data. Cost figures would be estimates, and the report would say so.

## Open questions

1. Does Cursor now put token usage in any hook payload or file (the forum posts are from Jul and Oct 2026)? Check on a current build.
2. Has the Cursor `sessionStart` `additional_context` bug been fixed in the current release? Test with a marker string.
3. Does cursor-agent (CLI) run all hook events, user-level and project-level? Official docs silent.
4. Exact field names of `token_usage` in the Codex `PostModelRequest` hook, and the rollout schema in the installed Codex version. Check a real file.
5. Can Codex `PostCompact` inject context? Docs list `additionalContext` only for other events. Test.
6. Cursor billing: does the meter even make sense on a plan with a weekly pool? Dollars apply only to pass-through models.
7. One shared note directory for all three tools, or one per tool? Notes are plain Markdown, so sharing looks possible.
8. Cache TTL for Cursor and Codex: Codex API gives at least 30 minutes (up to 24 h); Cursor not stated. The "cold turn" cost needs a per-tool TTL.
9. Does the Codex plan-billing mode (credits) match list prices well enough for a dollar figure? Codex has no cache-write charge in credits, but the API may.
