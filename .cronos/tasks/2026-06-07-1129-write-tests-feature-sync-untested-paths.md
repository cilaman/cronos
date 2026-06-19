---
agent_mode: auto
agent_model: sonnet
claude_session_id: 4226addf-4c45-4a46-9803-96dece32fede
created_at: '2026-06-07T11:29:31Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-07-1129-write-tests-feature-sync-untested-paths
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-07-1129-feature-module-test-coverage-gaps
pending_messages: []
pr_url: null
priority: 3
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: 'Write tests: feature_sync untested paths (P1-A, P1-D, P1-E, P2-F, P2-G)'
type: task
updated_at: '2026-06-16T06:30:16Z'
waiting_question: null
---

# Brief

Write missing tests for `backend/app/feature_sync.py` untested paths.

Coverage target: lines 51, 100-110, 130-132, 205-210, 244, 249-250

## Tests to write

**P1-A — set_feature_waiting_question AttributeError recovery**
File: `tests/test_feature_sync_waiting_resume.py` (add to existing file)

Test scenario: Create a goal with `waiting_question = "Which provider?"`, call
`propagate_to_feature(goal.id, store, pool=None)`, assert feature IS in WAITING state
(transition succeeds), and assert feature's `waiting_question` IS populated now that the storage
method exists (after the F1 backend fix). Name: `test_waiting_question_propagated_to_feature`.

Note: If the backend bug fix (Task 1a in goal 2026-06-07-1127-fix-features-backend-critical-bugs)
has not yet landed, document the *current broken behavior* with `pytest.mark.xfail` so the test
becomes a regression guard when the fix ships.

**P1-D — propagate_to_feature with non-existent item_id**
File: `tests/test_feature_sync_resolution.py` (add test)

Test: call `propagate_to_feature("nonexistent-id", store, pool=None)` and assert no exception
is raised and no task state is mutated. Lines hit: 51, 244.

**P1-E — _find_root cycle guard (50-hop)**
File: `tests/test_feature_sync_resolution.py` (add test)

Test: construct a mock store that returns a parent_id chain longer than 50 hops. Assert
`_find_root` returns `None` and logs a warning. Lines hit: 249-250.
Pattern: use a dict-backed store mock with tasks chained parent_id → parent_id.

**P2-F — ACTIVE-resume PLANNED concurrent race**
File: `tests/test_feature_sync_waiting_resume.py` (add test)

Test: feature is in PLANNED state (already resumed), a second propagate_to_feature fires
WAITING → PLANNED transition which hits InvalidTransition. Assert this is silently swallowed
(no exception raised, feature stays PLANNED). Lines hit: 130-132.

**P2-G — done-detection DONE concurrent race**
File: `tests/test_feature_sync_done_detection.py` (add test)

Test: feature is already in DONE state, done-detection fires again (all items terminal, no
active branch). Second `transition_feature(..., DONE)` raises InvalidTransition. Assert it's
silently swallowed. Lines hit: 205-210.

## Acceptance

- `cd backend && pytest tests/test_feature_sync_waiting_resume.py tests/test_feature_sync_resolution.py tests/test_feature_sync_done_detection.py -v` all pass
- Coverage on feature_sync.py improves to ≥93% (`pytest --cov=app/feature_sync --cov-report=term-missing`)
- All existing tests still pass: `cd backend && pytest tests/ -x -q`

After tests pass, run /goal-branch-setup (first task in this goal).
Then run /goal-task-commit

# History

```
2026-06-09T05:41:28Z [agent]
I'll start by reading the existing test files and the source to understand the patterns, then write the missing tests.

Now let me read the existing test files:

Now let me check if `set_feature_waiting_question` exists in storage.py and understand the store API:

Let me check the `finalize_run` method and how to set `waiting_question` on a task:

Good. Now I have all the context. Let me write the 5 tests across the 3 files.

Now I have everything I need. Let me add the tests to all three files:

Now add P1-D and P1-E to the resolution test file:

Now add P2-G to the done-detection test file:

Now I need to add the `InvalidTransition` import to the done-detection test file:

Now let's run the specific tests to verify they pass:

All 27 tests pass. Let me check the coverage specifically for `feature_sync.py`:

Excellent! 96% coverage on `feature_sync.py`, exceeding the ≥93% target. Now let me verify all existing tests still pass:

All 2506 tests pass. Now let me run the goal-branch-setup skill as instructed in the brief:

The main worktree has uncommitted changes from another goal. Let me check the workspace worktree state:

Branch is set up. Now run the goal-task-commit skill:

On the right branch. Now run tests to confirm:

The workspace worktree has its own `backend` directory. Let me check if the test changes are there:

The changes are in the main worktree, not the workspace. I need to copy them over per the memory note about worktrees:

Pushed successfully. Now finalize the task:

## Step 1 — Verify completion

All task objectives met:
- P1-A: `test_waiting_question_propagated_to_feature` added — verifies `waiting_question` propagates to feature after F1 fix
- P1-D: `test_propagate_nonexistent_item_is_noop` added — hits line 51 + 244
- P1-E: `test_find_root_cycle_guard_returns_none` added — hits lines 249-250 via `_find_root`
- P2-F: `test_active_resume_concurrent_race_is_swallowed` added — hits lines 130-132
- P2-G: `test_done_detection_concurrent_race_is_swallowed` added — hits lines 205-210

27 tests pass, 96% coverage on `feature_sync.py` (target ≥93%), 2506 total tests pass.

## Step 3 — Handle git

Goal-task-commit already ran — changes committed and pushed to `feature/feature-module-test-coverage-gaps`.

## Step 4 — Write memory

Memory written. 

**Summary:** 5 new tests added covering all target lines in `feature_sync.py`. Coverage rose from 86% to 96% (target was ≥93%). All 2506 existing tests continue to pass. Changes committed to `feature/feature-module-test-coverage-gaps` and pushed.

STATUS: DONE
```
