---
agent_mode: auto
agent_model: sonnet
claude_session_id: 6e0efcbf-6223-4274-a0ae-d1b5ef7c471e
created_at: '2026-06-19T11:15:38Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-19-1115-fix-workerpool-missing-harness-store-exe
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-19-1115-fix-harness-executor-never-runs-harness
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: done
title: Fix WorkerPool missing harness_store + executor trigger-node warning
type: task
updated_at: '2026-06-19T11:30:18Z'
waiting_question: null
---

# Brief

## Changes required

### 1. `backend/app/worker_pool.py`

**Add `harness_store` field and inject it when creating Workers.**

In `WorkerPool.__init__`, add:
```python
self._harness_store: "HarnessStore | None" = None
```

Add a public setter/method or accept it in `__init__`. The cleanest approach is to add an optional `harness_store` parameter to `WorkerPool.__init__` and store it as `self._harness_store`.

Then in `start_for_space()`, pass it when constructing the Worker:
```python
worker = Worker(
    self._task_store,
    space_store=self._space_store,
    stats_store=self._stats_store,
    trace_store=self._trace_store,
    memory_store=self._memory_store,
    on_idle=_on_idle,
    pool=self,
    harness_store=self._harness_store,   # ← ADD THIS
)
```

In `backend/app/main.py`, pass the harness_store when constructing WorkerPool. Find the line where `WorkerPool(...)` is constructed and add `harness_store=harness_store`. Check the current WorkerPool constructor signature — if it doesn't accept `harness_store` yet, add that parameter first.

### 2. `backend/app/harnesses/executor.py`

In the BFS dispatch block (around line 583), the `else` branch logs a WARNING for unknown node types. The trigger node (`NodeType.trigger`) hits this branch every time. Add an explicit passthrough before the catch-all:

```python
elif node.type == NodeType.trigger:
    # Trigger nodes are entry points only — the executor treats them as
    # immediate pass-through; no agent is run, successors are enqueued.
    now = _utcnow_iso()
    state.nodes_executed[node_id] = NodeState(
        status="done",
        ended_at=now,
    )
    self._publish_event(run_goal_id, {
        "type": "node_transition",
        "node_id": node_id,
        "from_status": "pending",
        "to_status": "done",
        "timestamp": now,
    })
    _maybe_save(state, run_state_path)
    self._enqueue_successors(
        node_id, successors, state, in_degree, in_queue, ready_queue
    )
```

This eliminates the spurious `WARNING: Node X has unknown type 'trigger'` log line.

## Acceptance

- `WorkerPool` accepts `harness_store` in its constructor and stores it.
- `Worker` created by `start_for_space()` has `harness_store` set (not None).
- `executor.py` no longer logs a WARNING for trigger nodes.
- No existing tests broken.

## Git workflow

Start with `/goal-branch-setup` then end with `/goal-task-commit`.

# History

```
2026-06-19T11:30:18Z [agent]
I'll start by reading the relevant files to understand the current state before making changes.

Branch is set up. Now let me read the relevant files to understand what changes are needed.

Now let me look at the executor.py BFS dispatch block.

Now I can see what needs to be changed. Let me also look at how trigger nodes are handled at the start of the BFS to understand the full picture:

Good. Now I have a complete picture. Let me make both changes:

**Change 1**: Update `worker_pool.py` to accept and pass `harness_store`
**Change 2**: Update `executor.py` to handle trigger nodes explicitly

Now update `main.py` to pass `harness_store` to `WorkerPool`:

Now fix the trigger node handling in `executor.py`. Let me add the explicit `elif node.type == NodeType.trigger` branch before the catch-all `else`:

Now let me verify the Worker constructor accepts `harness_store` (it should, but let me confirm):

`Worker` already accepts `harness_store`. Now run the tests to verify nothing is broken:

All 2608 tests pass with 85% coverage. Now let me commit the changes with the goal-task-commit skill.

The workspace worktree shows no changes because I edited files in the main space directory. Let me check the main worktree:

The changes are in the main worktree (on `main`). I need to copy the files to this workspace worktree and commit from here.

Committed and pushed. Now finalizing the task.

## Step 1 — Verify completion

All requirements met:
- `WorkerPool.__init__` now accepts `harness_store` parameter and stores it as `self._harness_store`
- `start_for_space()` passes `harness_store=self._harness_store` when constructing `Worker`
- `main.py` passes `harness_store=harness_store` to `WorkerPool`
- `executor.py` has an explicit `elif node.type == NodeType.trigger` branch (no more WARNING)
- 2608 tests pass, 85% coverage

## Step 3 — Handle git

Already completed via `/goal-task-commit` — commit `fde5aec` pushed to `feature/fix-harness-executor-never-runs-harness`.

## Step 4 — Write memory

MEMORY[fact]: WorkerPool in `backend/app/worker_pool.py` now accepts `harness_store: HarnessStore | None = None` in `__init__` and passes it through to `Worker` in `start_for_space()`; `main.py` at line ~400 passes `harness_store=harness_store` to the WorkerPool constructor — this was the root cause of the harness executor never running (worker.harness_store was always None).

MEMORY[fact]: `backend/app/harnesses/executor.py` BFS dispatch block now has an explicit `elif node.type == NodeType.trigger` branch (before the catch-all `else`) that marks trigger nodes as "done" and enqueues successors without logging a WARNING — trigger nodes are entry points only, no agent is run.

STATUS: DONE
```
