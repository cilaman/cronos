---
agent_mode: auto
agent_model: default
claude_session_id: 20158a23-294a-4587-9c92-6da00333ffa3
created_at: '2026-06-07T15:33:09Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-07-1533-add-waiting-question-to-featureread-sche
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-07-1533-fix-features-backend-p1-bugs-f1-f2-f3
pending_messages: []
pr_url: null
priority: 1
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: Add waiting_question to FeatureRead schema (F2)
type: task
updated_at: '2026-06-15T07:30:16Z'
waiting_question: null
---

# Brief

In `backend/app/models.py`, add `waiting_question: str | None = None` to the `FeatureRead` Pydantic model.

Verify that `GET /api/features/{id}` returns the field when a feature is in WAITING state (integration test or manual curl).

# History

```
2026-06-08T06:32:18Z [agent]
Looking at the `FeatureRead` model in `models.py` to understand the current state.

The `waiting_question: str | None = None` field is already present in `FeatureRead` at line 218. This task is already complete. Let me verify the test coverage as well.

All three bugs (F1, F2, F3) have already been implemented in the main branch. The `waiting_question` field exists in `FeatureRead` (line 218), `set_feature_waiting_question()` exists in `storage.py` (line 903), and the field is properly persisted and returned. Let me run the tests to confirm everything passes.

All 2467 tests pass with 84.77% coverage. The task is already complete — `waiting_question: str | None = None` was added to `FeatureRead` in a prior commit (S2 API work), along with the full storage implementation.

## Step 1 — Verify completion

The task objective is met: `waiting_question: str | None = None` exists at `models.py:218` in `FeatureRead`, storage persists it, and 2467 tests pass at 84.77%. No code changes were needed.

## Step 3 — Handle git

This is a goal child task. Delegating to goal-task-commit.

Not on the feature branch — need to run goal-branch-setup first.

The local branch already exists. Now checking it out in this worktree.

The feature branch is locked by another worktree. Since this task made no code changes (F2 was already implemented), there's nothing to commit.

The feature branch is locked by another worktree (`2026-06-07-1533-add-409-guard-against-double-fire-in-pro`). Since this task made **no code changes** (the `waiting_question` field was already present in `FeatureRead` from prior work), there's nothing to commit. Skipping steps 4–5.

## Step 4 — Write memory

MEMORY[fact]: Bug F2 (waiting_question missing from FeatureRead) was already fixed in prior S2 API work (commit 7e9d44a). The field `waiting_question: str | None = None` exists at `backend/app/models.py:218`. When verifying P1 bug tasks, check git log for the target field before making changes.

## Step 5 — Emit STATUS: DONE

STATUS: DONE
```
