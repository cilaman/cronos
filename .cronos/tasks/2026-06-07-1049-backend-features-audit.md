---
agent_mode: auto
agent_model: opus
claude_session_id: null
created_at: '2026-06-07T10:49:05Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-07-1049-backend-features-audit
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-07-1049-features-fixes-deep-qa-review
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: backlog
title: Backend Features Audit
type: task
updated_at: '2026-06-07T10:49:05Z'
waiting_question: null
---

# Brief

Audit the backend implementation of the Features & Fixes feature in Cronos for
correctness, completeness, and error handling quality.

## Files to audit

Read each file fully before starting the audit:

1. `backend/app/feature_state.py` — state machine transitions
2. `backend/app/api/features.py` — 8 REST endpoints
3. `backend/app/storage.py` — search for all methods containing "feature" in the name
4. `backend/app/feature_sync.py` — propagate_to_feature() worker hook
5. `backend/app/feature_hooks.py` — mirror_feature_to_github(), enqueue_feature_decomposition()
6. `backend/app/models.py` — FeatureState, FeatureRead, FeatureBoard, CreateFeatureBody, PatchFeatureBody, PatchFeatureStateBody, PatchRealizeBody, TaskSummary (feature fields)
7. `backend/app/worker.py` — _run_feature_decompose() (search for this function)

## Specific issues to verify

Check each of these known potential issues:

A. **Missing storage method**: `feature_sync.py` calls `store.set_feature_waiting_question(feature_id, waiting_q)`.
   Grep for `set_feature_waiting_question` in `backend/app/storage.py`. Does this method exist?
   If missing, this is a CRITICAL bug causing AttributeError when features transition to WAITING.

B. **DELETE endpoint**: `api/features.py` DELETE handler — does it return 501 Not Implemented?
   Is there a plan for soft-delete or archive? Is the frontend handling the 501 gracefully?

C. **process_feature endpoint**: POST /api/features/{id}/process — does it guard against
   double-processing (already PROCESSING or PLANNED state)? What happens if decomposition fails?

D. **validate_realizes()**: Does it prevent circular realize references? Can a feature realize itself?
   Can a task realize a task (not a feature/fix)?

E. **GitHub mirror (feature_hooks.py)**: Is the mirror purely fire-and-forget? What happens if
   the space has no GitHub remote configured? Does it fail silently or log clearly?

F. **feature_sync propagation**: In propagate_to_feature(), what happens if `realizing_items()`
   returns an empty list when a feature is PLANNED? Does done-propagation handle edge cases
   (e.g., no realizing items → feature stays PLANNED forever)?

G. **Space isolation**: Do feature_key counters (FEAT-NNN, FIX-NNN) properly isolate per space?
   What happens if two concurrent POSTs race on _next_feature_key?

H. **State machine completeness**: Review FEATURE_USER_TRANSITIONS and FEATURE_WORKER_TRANSITIONS.
   Are there states a feature can get stuck in with no valid transition? E.g., can a feature in
   "processing" transition back to "backlog" via user action?

I. **Error responses**: Do the API endpoints return proper 404 when feature not found?
   Do they return 422 with useful messages on bad input?

J. **Serialization**: Does FeatureRead include all fields a frontend detail panel would need?
   (realizing_items, feature_key, issue_number, issue_url, proposed_issue_path, waiting_question)

## Output format

Write your findings to `/data/spaces/cronos-development/.cronos/qa/features-backend-audit.md`.
Create the directory if it doesn't exist (use Bash: `mkdir -p /data/spaces/cronos-development/.cronos/qa`).

Structure the file as:

```markdown
# Features Backend Audit

## Critical Issues (P0 — breaks production)
...

## High Priority Issues (P1 — feature incomplete)
...

## Medium Priority Issues (P2 — quality/reliability)
...

## Low Priority / Future Work (P3)
...

## What Works Well
...

## Summary Table
| Issue | Severity | File:Line | Recommendation |
|-------|----------|-----------|----------------|
```

After writing the file, verify it exists with Bash.

## Acceptance

- All 10 specific issues (A–J) are verified (confirmed OK or flagged as issue)
- Findings file written to `/data/spaces/cronos-development/.cronos/qa/features-backend-audit.md`
- Each finding cites exact file paths and line numbers

Then run /task-finalize

# History
