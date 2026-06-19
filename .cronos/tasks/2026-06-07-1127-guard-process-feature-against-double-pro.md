---
agent_mode: auto
agent_model: sonnet
claude_session_id: 6144ea40-3c1a-4bd0-a9b3-c4fb20dc9209
created_at: '2026-06-07T11:27:14Z'
depends_on:
- 2026-06-07-1127-add-set-feature-waiting-question-expose
feature_key: null
feature_state: null
id: 2026-06-07-1127-guard-process-feature-against-double-pro
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-07-1127-fix-features-backend-critical-bugs
pending_messages: []
pr_url: null
priority: 1
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: Guard process_feature against double-processing (409)
type: task
updated_at: '2026-06-15T05:30:16Z'
waiting_question: null
---

# Brief

## Context

**F3** — `process_feature` in `backend/app/api/features.py:330-368` does not guard against calling
when the feature is already PROCESSING. `transition_feature` silently no-ops at `storage.py:861-862`
(same-state early return), then the endpoint unconditionally fires mirror + enqueue, potentially
double-creating realizing items if the prior decomposition is still mid-flight.

Observable bug: POST `/api/features/{id}/process` on an already-PROCESSING feature returns 200,
fires a second GitHub mirror call, and enqueues a second decomposition agent.

## Changes required

**`backend/app/api/features.py`** — In the `process_feature` handler, add an early-exit guard
immediately after the initial `store.get(feature_id)` and type-guard checks, before calling
`transition_feature`:

```python
if task.feature_state == FeatureState.PROCESSING:
    raise HTTPException(status_code=409, detail="Feature is already being processed")
```

Add a brief comment on the PLANNED case: re-processing a PLANNED feature (which may already have
realizing items) is allowed — the user explicitly requested re-decomposition. No additional guard
needed there, but document it.

## Acceptance

- POST `/api/features/{id}/process` on an already-PROCESSING feature returns HTTP 409
- Existing tests still pass: `cd backend && pytest tests/ -x -q`
- No second enqueue observable for already-PROCESSING features

After tests pass, run /goal-task-commit

# History

```
2026-06-08T04:55:58Z [agent]
I'll read the `process_feature` handler to understand the current code before making the change.

Now I'll add the early-exit guard right after the type check, before `transition_feature` is called.

Let me read more context to uniquely identify the right block.

Let me search for other occurrences of this pattern in the file.

I can see the two occurrences. I'll use more unique context around the `process_feature` one — specifically including the `transition_feature` call.

Now let me run the tests to verify everything still passes.

All 2466 tests pass with 84.82% coverage. Now I'll run `/goal-task-commit`.

The feature branch already exists. I'll check it out and then stage/commit the changes.

The branch is checked out in another worktree. I'll copy the changed file there and commit via the main worktree using `git -C`.

Both commits are on the feature branch correctly. Now let me push.

Pushed successfully. Now I'll finalize the task.

## Step 1 — Verify completion

The task required adding a 409 guard in `process_feature` when the feature is already PROCESSING. Done:
- Guard added at `backend/app/api/features.py:357-360` before `transition_feature` is called
- 2466 tests pass
- Committed (`026c8a6`) and pushed to `feature/fix-features-backend-critical-bugs`

## Step 3 — Handle git

Already completed via `/goal-task-commit` above — changes pushed to the feature branch.

## Step 4 — Write memory

Memory written. Task is complete.

STATUS: DONE
```
