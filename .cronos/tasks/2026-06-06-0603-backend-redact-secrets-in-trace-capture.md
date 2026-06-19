---
agent_mode: auto
agent_model: sonnet
claude_session_id: afcd1723-e383-40ee-829d-f331e9f98eb2
created_at: '2026-06-06T06:03:07Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-06-0603-backend-redact-secrets-in-trace-capture
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-06-0603-prevent-pat-leaks-in-committed-trace-jso
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: 'Backend: redact secrets in trace capture'
type: task
updated_at: '2026-06-13T07:30:16Z'
waiting_question: null
---

# Brief

## What

Add runtime redaction at the trace-write layer so PATs/tokens never reach disk inside trace JSONs.

## Where

The trace capture lives in `backend/app/trace_parser.py` (see `parse_status` / the trace-building helpers it sits next to) and `backend/app/trace_store.py` (the write layer). The fields that carry agent-visible Bash output are `input_summary` and `output_summary` on each tool-call entry. Inspect both files first to confirm the exact hook point — apply redaction at the latest point before serialisation, so we cover every field regardless of upstream changes.

## How

Add a pure helper, e.g. `_redact_secrets(text: str) -> str`, in a new module `backend/app/trace_redact.py`. Patterns (compiled regex; case-sensitive):

- `ghp_[A-Za-z0-9_]{20,}` → `REDACTED-GHP`
- `github_pat_[A-Za-z0-9_]{20,}` → `REDACTED-GITHUB-PAT`
- `gho_[A-Za-z0-9_]{20,}` → `REDACTED-GHO`
- `ghs_[A-Za-z0-9_]{20,}` → `REDACTED-GHS`
- `ghr_[A-Za-z0-9_]{20,}` → `REDACTED-GHR`
- `https://[^@\s]+@github\.com` → `https://REDACTED@github.com`
- (Defense in depth) any `x-access-token:[A-Za-z0-9_]{20,}` literal → `x-access-token:REDACTED`

Wire the helper into the trace-write code so every string field of a trace entry is redacted before `json.dumps`. Do NOT walk the structure ad hoc — recurse generically over str leaves of the trace dict.

## Acceptance

- New unit-test file `backend/tests/test_trace_redact.py` covers each pattern (positive + negative case), including a nested-dict input and a string with multiple distinct PATs.
- A second unit test confirms `trace_store.write(...)` (or whichever function persists trace JSON) emits files with no PAT pattern present, given a fixture trace whose `output_summary` contains the canary string `ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA`.
- `cd backend && pytest tests/ --cov=app --cov-report=term-missing` passes with the 60% floor preserved.

Then run: /goal-task-commit

# History

```
2026-06-06T06:52:56Z [agent]
I'll start by reading the relevant files to understand the trace capture and write layers.

Now I have a clear picture. Let me also check the existing test structure:

I have all the context I need. Let me implement the changes.

Now wire it into `trace_store.py`:

Let me verify the edit looks correct:

Good. Now write the test file:

Now run the tests:

All 29 tests pass. The coverage failure is expected when running a single file — I need to run the full suite:

2464 tests pass, 84.89% coverage — well above the 60% floor. Now run the commit skill:

I need to set up the feature branch first.

On the feature branch. Now commit the changes:

The working tree shows clean because changes are in the main worktree, not this one. Let me check:

The source files are in the main worktree. Let me check its current branch and then commit from there:

The main worktree is in detached HEAD state, so I can check out the feature branch there:

The feature branch is locked to this worktree. I'll switch this worktree back to the cronos branch, then check out the feature branch in the main worktree to commit from there:

Main worktree is now on the feature branch. Now commit just the three relevant files:

Committed and pushed. Now finalize the task:

## Step 1 — Verify completion

All requirements met:
- `backend/app/trace_redact.py` created with `_redact_secrets()` (7 patterns) and `redact_trace_dict()` (generic recursive walker)
- `trace_store.py` wired: `save_run()` now calls `redact_trace_dict(trace.model_dump(mode="json"))` before `json.dumps`
- `backend/tests/test_trace_redact.py`: 29 tests — per-pattern positive/negative, nested dict, multiple PATs, `save_run()` canary test
- Full suite: 2464 tests, 84.89% coverage ✅

## Step 3 — Git

Already committed and pushed as `d5148f9` on `feature/prevent-pat-leaks-in-committed-trace-jso`.

## Step 4 — Write memory

MEMORY[fact]: `backend/app/trace_redact.py` added — `_redact_secrets(text)` applies 7 compiled regex patterns (ghp_, github_pat_, gho_, ghs_, ghr_, https://token@github.com, x-access-token:); `redact_trace_dict(obj)` recurses over any dict/list/str tree. `trace_store.py`'s `save_run()` calls `redact_trace_dict(trace.model_dump(mode="json"))` before `json.dumps`, so all string fields are redacted at write time. 29 new tests in `backend/tests/test_trace_redact.py`.

MEMORY[observation]: When the feature branch is checked out in the workspace worktree, the main worktree must be used for staging/committing source changes — switch the workspace worktree back to its `cronos/` branch first, then `git -C $SPACE_DIR checkout feature/...` in the main worktree.

Memory written. Now mark the task done via the API:

The API state transition is handled by the Cronos worker automatically when STATUS: DONE is emitted. Memory is written, commit is pushed.

STATUS: DONE
```
