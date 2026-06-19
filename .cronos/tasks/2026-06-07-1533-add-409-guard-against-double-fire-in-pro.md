---
agent_mode: auto
agent_model: default
claude_session_id: 688a08d1-31ec-4042-999d-7028965e6cfb
created_at: '2026-06-07T15:33:09Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-07-1533-add-409-guard-against-double-fire-in-pro
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
title: Add 409 guard against double-fire in process_feature (F3)
type: task
updated_at: '2026-06-15T06:30:16Z'
waiting_question: null
---

# Brief

In `backend/app/api/features.py`, in the `process_feature` endpoint, add an early guard:

```python
if task.feature_state == FeatureState.PROCESSING:
    raise HTTPException(status_code=409, detail="Feature is already being processed")
```

Add a test that verifies a second POST to `/api/features/{id}/process` returns 409 when the feature is already in PROCESSING state.

# History

```
2026-06-08T06:28:51Z [agent]
I'll look at the relevant files to understand the current code structure before making changes.

The guard is already in the code at line 351-352. Now let me check if the test for this behavior exists.

The implementation already has the 409 guard at lines 351-352. The test file also has tests for the 409 case. Let me run the tests to verify they pass, and check if a more targeted test for the early guard specifically is needed.

All 15 tests pass. The guard is already implemented and the tests cover the 409 case. Let me run the full test suite to verify everything is green and coverage is maintained.

2466 tests pass with 84.77% coverage. Let me check the git log to understand if this work was already done or if these are from a prior task.

The guard and tests were already implemented in commit `7e9d44a` as part of the Features & Fixes S2 work. Let me verify the specific test that covers the exact early-guard behavior exists and passes correctly.

The implementation and tests are already in place from the S2 work. However, the existing tests for the 409 case still set up `transition_feature` with an `InvalidTransition` side effect — they don't explicitly verify the early guard fires (i.e., `transition_feature` is never called). Let me add a targeted test that proves the guard fires before reaching `transition_feature`.

Now I'll add a test that specifically validates the early-guard pattern: that `transition_feature` is never called when the feature is already `PROCESSING`.

All 16 tests pass (including the new one). The coverage failure is only because we ran the file in isolation. Let me do a final full-suite confirmation.

2467 tests pass (one more than before), 84.77% coverage. Now let me finalize the task.

This is a goal child task. Delegating to goal-task-commit.

Not on the feature branch. Running `/goal-branch-setup` to check it out.

Now on the feature branch. Staging and committing changes.

Let me check what branch the main worktree is on, since the workspace and main worktree are separate.

The edits were made in the main worktree (`/data/spaces/cronos-development`), not the workspace. I need to copy the F3-relevant files to the workspace worktree and commit from here.

Committed and pushed to `feature/fix-features-backend-p1-bugs-f1-f2-f3`. Now writing memory and emitting STATUS.

MEMORY[fact]: F3 fix (409 guard in `process_feature`) was already implemented in `backend/app/api/features.py` lines 351-352 as part of S2 work. Added one new targeted test `test_process_feature_early_guard_skips_transition_when_already_processing` to `backend/tests/api/test_features_process.py` that explicitly proves the early guard fires by verifying `transition_feature.call_count == 0` when feature is already PROCESSING.

MEMORY[observation]: The features.py guard and tests were both already present in the main worktree (`/data/spaces/cronos-development`) as uncommitted working-directory changes from prior sibling task work. The workspace worktree had no changes. Correct flow: copy relevant files from main worktree → workspace worktree → commit from workspace.

STATUS: DONE
```
