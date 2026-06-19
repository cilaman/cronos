---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-07T15:33:09Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-07-1533-fix-features-backend-p1-bugs-f1-f2-f3
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 1
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: Fix Features backend P1 bugs (F1, F2, F3)
type: goal
updated_at: '2026-06-15T07:30:16Z'
waiting_question: null
---

# Brief

Fix three P1 correctness bugs uncovered in the Features & Fixes backend audit.

## Bug F1 — `set_feature_waiting_question()` undefined
**File:** `backend/app/storage.py` + `backend/app/api/features.py`
`features.py:patch_feature_state()` calls `self.store.set_feature_waiting_question(task_id, question)` which does not exist on TaskStore. The call is wrapped in `except AttributeError: pass` so the error is silently swallowed. Result: users moving a feature to WAITING state never see the blocking question; the card shows WAITING with no context.
**Fix:** Implement `TaskStore.set_feature_waiting_question(task_id: str, question: str)` in `storage.py` (store value in the task row's `waiting_question` column). Remove the silent AttributeError catch from `features.py`.

## Bug F2 — `waiting_question` missing from FeatureRead schema
**File:** `backend/app/models.py`
The `FeatureRead` Pydantic model does not include a `waiting_question` field. Backend stores the value but the frontend can never retrieve it because `GET /api/features/{id}` omits it from the response.
**Fix:** Add `waiting_question: str | None = None` to `FeatureRead`.

## Bug F3 — `process_feature` allows double-fire
**File:** `backend/app/api/features.py`
`POST /api/features/{id}/process` calls `transition_feature(PROCESSING)` which silently no-ops when the feature is already PROCESSING (same-state transition returns without error). A second call enqueues a second decomposition agent — the goal tree can double-create.
**Fix:** Add an explicit state check at the start of `process_feature`: if `task.feature_state == FeatureState.PROCESSING`, raise HTTPException(409, "already processing").

## Acceptance criteria
- `set_feature_waiting_question()` exists on TaskStore and persists the value
- `GET /api/features/{id}` returns `waiting_question` for WAITING-state features
- Second `POST /api/features/{id}/process` returns 409 instead of enqueuing a duplicate agent
- All existing backend tests still pass (`pytest tests/ --cov=app --cov-fail-under=60`)

# History

```
2026-06-08T06:41:05Z [agent]
All tasks complete. Completed 3, skipped 0 already-done.
```
