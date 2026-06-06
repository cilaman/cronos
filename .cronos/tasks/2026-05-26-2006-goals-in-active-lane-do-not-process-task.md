---
agent_mode: auto
agent_model: default
claude_session_id: 624dfb09-5e5b-411a-9fe8-7ee9e63b3062
created_at: '2026-05-26T20:06:24Z'
depends_on: []
id: 2026-05-26-2006-goals-in-active-lane-do-not-process-task
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 3
proposed_pr_path: null
space_id: cronos-development
state: archived
title: Goals in active lane do not process tasks
type: task
updated_at: '2026-06-02T20:33:35Z'
waiting_question: null
---

# Brief

I have active goal tgat has finished tasks. But after finish of one task it does not continue with the next. Investigate and check what was changed, because it already worked

# History

```
2026-05-26T20:16:16Z [agent] run=0 model=claude-sonnet-4-6 mode=auto
Let me look at the recent commits and relevant code to investigate this issue.

Let me look at the worker and storage code to understand how tasks are processed in goals.

Let me look at goal_sync and worker_pool to understand the automation mechanism.

Let me look at the recent `859578d` commit in detail and the `start_task` / autopilot code.

Let me look at the `start_task` API and the storage layer.

Let me check the app startup and any task recovery logic.

Let me look at the `finalize_run` and `board` methods in storage.py.

Let me look at the arc-9 propagate commit and the full task flow.

Let me check the git log for goal_sync.py and look at the storage finalize_run logic.

Let me look at the arc-9 auto-resume commit to understand what changed.

I found the bug. Let me confirm my understanding by tracing the flow.

The bug is in `goal_sync.py`. Here's the scenario:

1. Goal G is WAITING (paused). Children: T1 (DONE), T2 (WAITING).
2. User replies to T2 → T2 transitions WAITING→ACTIVE → enqueued as standalone.
3. `propagate_to_parent(T2)` fires: T2=ACTIVE, G=WAITING → **G transitions to ACTIVE** (shown in active lane), but **NOT enqueued**.
4. Worker runs T2 standalone → T2 finishes DONE.
5. `_finalize(T2)` → `propagate_to_parent(T2)`: T2=DONE, G=**ACTIVE** → **neither branch fires** (only fires when G=WAITING) → G is never re-enqueued.

Goal stays ACTIVE in the lane forever, with no worker processing it. The fix: extend the DONE/ARCHIVED branch to also handle `parent_state == ACTIVE`, and skip the state transition (already active), but still enqueue if not currently running.

Now let me verify the fix looks correct:

Good. Now let me look at the existing goal_sync tests and add a test for the new case.

I need to update the test file: `test_idempotent_already_active` needs updating (old behavior was no-op when parent ACTIVE, new behavior is to enqueue), and I need to add a test for the new "worker currently running" guard.

First, update `_RecordingPool` to add `get()` (needed by the new code path):

Now update the `test_idempotent_already_active` test (which tested the old no-op behavior) to reflect the new enqueue behavior, and add the "running guard" test:

Now run the tests to confirm everything passes:

All 12 tests pass. Let me run the broader relevant tests to confirm nothing is broken:

299 tests pass. The fix is complete.

**Root cause:** `goal_sync.propagate_to_parent` only re-enqueued the goal when `parent_state == WAITING`. But there's a two-step sequence where a goal ends up ACTIVE without being in the worker queue:

1. User replies to a WAITING child → child becomes ACTIVE → `propagate_to_parent` transitions goal WAITING→ACTIVE (lane sync, no enqueue)
2. Child finishes DONE → `propagate_to_parent` fires again, but now `parent_state == ACTIVE` → old code skipped entirely → goal stuck ACTIVE with nobody processing it

**Fix:** Extended the DONE/ARCHIVED branch in `goal_sync.propagate_to_parent` to also handle `parent_state == ACTIVE`. When parent is already ACTIVE, skip the redundant state transition but still enqueue the goal — unless `worker.current() == goal_id`, which means `_run_goal` is already orchestrating it internally (in which case re-enqueueing is unnecessary and would cause a double run).

STATUS: DONE
```

```
2026-05-26T20:17:23Z [user]
Commit to main, propagate also to feature branch, push and upgrade
```

```
2026-05-26T20:19:19Z [agent] run=1 model=claude-sonnet-4-6 mode=auto
The test file is correct. Now let me commit to main via its worktree, then apply to the task branch.

Good. The main worktree is at the first location, task branch at the second. Let me pull main and then commit there.

Main is up to date. Now copy the changed files and commit to main:

Now apply to the task branch worktree:

Both branches have the commit. Now push both and upgrade:

Both branches pushed. Now upgrade:

STATUS: DONE
```
