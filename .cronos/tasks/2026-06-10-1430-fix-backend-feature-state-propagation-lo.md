---
agent_mode: auto
agent_model: sonnet
claude_session_id: 91a2be23-c3d0-4358-88ca-1d69e4a7b381
created_at: '2026-06-10T14:30:48Z'
depends_on:
- 2026-06-10-1430-setup-feature-branch-for-fix-state-diver
feature_key: null
feature_state: null
id: 2026-06-10-1430-fix-backend-feature-state-propagation-lo
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-10-1430-implement-feature-fix-state-divergency
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: Fix backend feature_state propagation logic
type: task
updated_at: '2026-06-17T16:30:17Z'
waiting_question: null
---

# Brief

Fix the feature_state propagation logic in `backend/app/feature_sync.py` so that
`feature_state` correctly reflects the combined state of all realizing tasks/goals.

## Current problem

The feature_state is divergent from the actual state of realizing tasks/goals. The
propagation logic either doesn't run at all or uses incorrect state mapping.

## Required state mapping

Given all realizing items' `state` values, the derived `feature_state` must be:

| Condition | feature_state |
|-----------|---------------|
| No realizing items | BACKLOG (no change / initial) |
| All items in `backlog` | PLANNED |
| Any item is `active` | PROCESSING |
| Any item is `waiting` AND none are `active` | WAITING |
| All items are `done` or `archived` | DONE |

## Scope

- Primary file: `backend/app/feature_sync.py`
- Check `propagate_to_feature()` function — update the state derivation logic
- Ensure the function is called from the worker when task states change
- Check `backend/app/worker.py` for any hooks/callbacks that invoke feature_sync

## Steps

1. Read `backend/app/feature_sync.py` — understand the current propagation function
2. Read `backend/app/worker.py` — find where task state-change callbacks fire
3. Implement the correct state mapping logic in `propagate_to_feature()`
4. Verify the function is wired to fire on task/goal state changes

## Acceptance

- `propagate_to_feature()` correctly maps realizing item states to feature_state
- The function is called when a realizing task/goal changes state
- Use the `goal-branch-setup` branch if first task; otherwise commit via `goal-task-commit`

# History

```
2026-06-10T15:49:11Z [agent]
I'll start by reading the relevant files to understand the current propagation logic.

Let me read more of worker.py to find the relevant state-change callbacks and feature_sync calls.

Let me check the context around where `propagate_to_feature` is called in worker.py and also look at the `feature_state` model.

Let me check the store's `realizing_items` method and the `transition_feature` method to understand the available operations.

Let me check the TaskSummary model to understand its structure.

Now I have enough context. Let me check the existing tests for `feature_sync` to understand what test coverage looks like.

Let me also check the done-detection and waiting/resume tests to understand the full impact.

Let me check the git branches to understand if the feature branch is already set up.

The feature branch `feature/implement-feature-fix-state-divergency` already exists (T1 ran). Now I'll implement the changes to `feature_state.py` and `feature_sync.py`, then update the affected tests.

Let me start with the implementation:

Now I'll make both changes. First, expand `FEATURE_WORKER_TRANSITIONS`, then rewrite `propagate_to_feature`:

Now rewrite the `propagate_to_feature` function in `feature_sync.py`:

Now I need to handle the GitHub issue closing on DONE transition. Let me add it after the WAITING section and also clean up the unused imports:

I need to add the GitHub issue closing for DONE transitions and clean up unused imports:

Now add the gh_issue_close behavior for DONE transitions and update the docstring:

Now add the gh_issue_close for DONE transitions at the end of the function:

Now let me run the existing tests to see exactly which ones fail:

Let me see all failures:

Now I'll update the tests that test the old (incorrect) behavior. Let me start with the done-detection tests:

Now update `test_slug_derivation_strips_date_prefix` to test a meaningful scenario:

Now clean up unused imports in the done-detection test file (since we removed git_ops usage in some tests):

Now update the waiting/resume tests:

Now update `test_active_resume_concurrent_race_is_swallowed` docstring since ACTIVE now → PROCESSING not PLANNED:

Now update the integration test:

Now update the resolution test:

Now let's run the targeted tests to verify all pass:

All 33 targeted tests pass. Now let's run the full test suite to verify the 60% coverage floor:

Three tests failed. Let me check what they expect:

Let me check those three failing tests:

Now I'll fix all three remaining failures:

Now fix the lifecycle test (line 245):

Now fix `test_branch_present_feature_stays_planned`:

Now run the full test suite again:

All 2535 tests pass with 84.96% coverage (above the 60% floor). Now let me commit these changes via `goal-task-commit`:

The feature branch is checked out in the setup worktree. I'll copy changed files there and commit:

My edits are in the main space directory, not the workspace. I need to copy from there:

Now let me commit and push:

Committed and pushed. Now let me finalize the task:

## Step 1 — Verify completion

All requirements met:
- `propagate_to_feature()` now derives `feature_state` from all realizing items using the correct mapping (DONE/ARCHIVED → DONE, ACTIVE → PROCESSING, WAITING → WAITING, all BACKLOG → PLANNED)
- `FEATURE_WORKER_TRANSITIONS` expanded with all necessary transitions (BACKLOG→*, PLANNED→PROCESSING, WAITING→PROCESSING/DONE, PROCESSING→DONE)
- Function was already wired in `worker.py:1100` and `api/tasks.py:538` — no wiring changes needed
- 2535 tests pass, 84.96% coverage
- Committed to `feature/implement-feature-fix-state-divergency` and pushed

## Step 3 — git (already done via goal-task-commit)

Commit `6dc6619` pushed to origin.

## Step 4 — Write memory

Now update MEMORY.md:

Memory written. 

## Step 5 — Emit STATUS: DONE

The task is complete:
- `propagate_to_feature()` rewired to look at ALL realizing items and derive `feature_state` using the correct mapping from the brief
- `FEATURE_WORKER_TRANSITIONS` expanded from 5 to 13 pairs covering all reachable transitions  
- 8 test files updated to match correct behavior
- 2535 tests pass at 84.96% coverage
- Committed as `6dc6619` on `feature/implement-feature-fix-state-divergency` and pushed

STATUS: DONE
```
