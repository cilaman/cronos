---
agent_mode: auto
agent_model: default
claude_session_id: fd0fc02e-0910-44ab-add1-766c817c74ad
created_at: '2026-06-07T15:33:09Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-07-1533-implement-taskstore-set-feature-waiting
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
title: Implement TaskStore.set_feature_waiting_question + remove silent catch (F1)
type: task
updated_at: '2026-06-15T07:30:16Z'
waiting_question: null
---

# Brief

Add `set_feature_waiting_question(task_id, question)` to `TaskStore` in `backend/app/storage.py`.

It should update the task row's `waiting_question` column (same column the Tasks API uses for `waiting_question`). Use the same atomic update pattern as other single-field setters in TaskStore.

Then in `backend/app/api/features.py`, in the `patch_feature_state` endpoint (around the WAITING branch), remove the `try/except AttributeError: pass` wrapper around the `set_feature_waiting_question` call so errors surface instead of being swallowed.

Write/extend tests to verify the value is persisted and retrievable.

# History

```
2026-06-08T06:41:05Z [agent]
I'll read the relevant files to understand the current code structure before making changes.

Interesting — the method already exists at line 903. Let me check the current features.py code more carefully.

Let me read the full features.py to understand the current state of all bugs.

Let me check the models and existing tests to understand the full picture.

Let me check the existing tests for `set_feature_waiting_question` and the features API.

Let me check the git log to understand the order of changes.

Let me look at existing feature tests to understand the test patterns used.

Let me check the `transition_feature` method to understand if it clears `waiting_question`.

Let me read the audit report to understand the original buggy code structure.

Let me check feature_sync.py for the actual call site.

Let me verify there are no existing tests for `set_feature_waiting_question` specifically.

Let me check the conftest for test setup and how `task_store` is set up.

Now I have a complete picture. The implementation exists but tests are missing. Let me write the tests.

Now I have everything I need. I'll create the test file for `set_feature_waiting_question`.

Now let me run the tests to verify they all pass.

All 11 tests pass. Now let me run the full test suite to verify nothing is broken.

2478 tests passed, 84.88% coverage (above the 60% floor). Now let me finalize the task.

## Step 1 — Verify completion

All requirements met:
- `set_feature_waiting_question` exists and persists the value ✓
- `GET /api/features/{id}` returns `waiting_question` via FeatureRead ✓  
- Tests written and all 2478 pass, 84.88% coverage ✓

## Step 3 — Handle git

Goal child task — delegating to goal-task-commit.

Not on the feature branch — need to run goal-branch-setup first.

The branch is used by another worktree. Let me check the situation and use the worktree approach.

The feature branch is in another worktree. I'll copy the test file there and commit.

Committed and pushed to `feature/fix-features-backend-p1-bugs-f1-f2-f3`. Now back to task-finalize Step 4.

## Step 4 — Write memory

Memory written. Now emitting STATUS.

STATUS: DONE
```
