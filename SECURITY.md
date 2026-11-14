# Security

Please report security problems privately through GitHub's
"Report a vulnerability" button on the Security tab of this repository, not in
a public issue. You will get an answer within a week.

What this plugin touches: it reads Claude Code transcripts under `~/.claude`,
and writes handoff notes, a log and small marker files there. It makes no
network calls. Handoff notes are plain text; do not put secrets in them.
