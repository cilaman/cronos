---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-06T06:03:07Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-06-0603-prevent-pat-leaks-in-committed-trace-jso
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: Prevent PAT leaks in committed trace JSONs
type: goal
updated_at: '2026-06-13T07:30:16Z'
waiting_question: null
---

# Brief

## Why

During the `harness-editor-usability` finalize on 2026-06-06, GitHub push-protection blocked the merge because commit `ccf62fd` (`doc – backend-harness-tools-resolver`) committed `.cronos/traces/2026-06-04-1039-tests-merge-harnesses-page/0000.json` containing the literal value of `CRONOS_GIT_TOKEN` (`ghp_u8UXOE6Xvb…`). Root cause: an earlier agent run executed `echo "Remote: $REMOTE_URL"` while `$REMOTE_URL` carried the token-in-URL form `https://ghp_xxx@github.com/cilaman/cronos.git`, and the runtime captured that output into the trace JSON's `output_summary`. The doc-sync agent then committed the trace file.

We scrubbed the trace files (26 affected; new doc commit `5e11ea9`) and merged the goal (main tip now `6cf4389`), but the underlying leak path is still open.

## Threat model

Every Bash tool call's output is preserved verbatim in the trace JSON. Any command that *prints* a string carrying the PAT — whether by accident (`echo $REMOTE_URL`), by side effect (`git push` error output that quotes the URL), or by intent (curl `-v` to GitHub) — leaks the secret to a tracked file. The doc-sync phase then commits the trace dir. GitHub push-protection catches the leak only at the merge push, which is too late: the secret already lives in the local commit history.

## Defense layers (this goal builds all three)

1. **Runtime redaction**: at the trace-capture layer in the backend, redact known PAT/token patterns (`ghp_*`, `github_pat_*`, `gho_*`, `ghs_*`, `ghr_*`, `https://[^@]+@github.com`) inside every `input_summary` and `output_summary` field before the JSON is written to disk. This is the strongest layer because it covers every command, regardless of which skill ran.
2. **Source prevention in skills**: remove `echo "Remote: $REMOTE_URL"` and equivalent from `goal-finalize` / `goal-task-commit` SKILL.md. Document the rule: scripts running in agent context MUST NOT print the origin URL.
3. **CI guard**: a pytest test that grep-scans `.cronos/traces/**/*.json` for PAT patterns and fails the suite if any are present. Catches new leaks before they reach `git push`.

## Out of scope / manual

- **Rotate `CRONOS_GIT_TOKEN`** — the leaked PAT (`ghp_u8UXOE6Xvb…`) is still a valid GitHub credential and was just published in the rebase/recovery flow. Owner must revoke and regenerate it in GitHub Developer settings, then update the `.env` on the host. No agent task can do this safely.
- Historical trace files on other long-lived `cronos/*` branches may still contain the old PAT; once the PAT is rotated, those become inert and need no scrub.

## Child tasks

1. Backend: runtime redaction in trace capture + unit tests
2. Skills: remove origin-URL echoes from goal-finalize / goal-task-commit
3. Tests: pytest guard that fails if `.cronos/traces/**/*.json` contains PAT patterns

# History

```
2026-06-06T07:09:39Z [agent]
All tasks complete. Completed 3, skipped 0 already-done.
```
