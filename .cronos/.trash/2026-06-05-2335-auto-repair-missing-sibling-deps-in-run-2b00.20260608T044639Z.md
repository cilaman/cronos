---
agent_mode: auto
agent_model: sonnet
claude_session_id: null
created_at: '2026-06-05T23:35:07Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-05-2335-auto-repair-missing-sibling-deps-in-run-2b00
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-05-2335-auto-repair-missing-sibling-deps-in-run
pending_messages: []
pr_url: null
priority: 1
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: backlog
title: auto-repair missing sibling deps in _run_goal
type: task
updated_at: '2026-06-05T23:35:07Z'
waiting_question: null
---

# Brief

# Implement auto-repair for missing sibling deps in `_run_goal`

## Background

`backend/app/worker.py` `_run_goal` (line ~1295) calls:

```python
await self.store.transition(child_id, TaskState.ACTIVE, allowed=USER_TRANSITIONS)
```

If the child has `depends_on` pointing at a non-sibling task (grandchild of the
current goal) that isn't done yet, `store.transition` raises:

```
InvalidTransition("Cannot start task: unmet dependencies: <dep_id>")
```

The current handler (lines ~1297-1300) immediately sets `fail_reason` and breaks,
putting the **entire parent goal** into waiting state.

## Required change — `backend/app/worker.py`

In the `InvalidTransition` handler inside `_run_goal`, when the error message
starts with `"Cannot start task: unmet dependencies:"`:

1. Parse the unmet dep IDs from the error message.
2. For each unmet dep ID, look up that task via `self.store.get(dep_id)`.
3. If the dep task's `parent_id` is **different from the current `goal_id`**
   (i.e., it's a non-sibling dep), find the sibling: the dep's ancestor whose
   `parent_id == goal_id`. Walk the parent chain until you reach a task whose
   `parent_id == goal_id` — that is the sibling to add.
4. Call `await self.store.set_depends_on(child_id, child.depends_on + [sibling_id])`
   to add the missing sibling dep.
5. Log a warning:
   `log.warning("Auto-repaired missing sibling dep: %s → %s (was referencing non-sibling %s)", child_id, sibling_id, dep_id)`
6. Re-run `_topo_children(goal_id, self.store)` to get the updated order.
7. **Restart the `_run_goal` loop** from the beginning (with the new order) so
   the repaired child is correctly sequenced after its sibling.

**Important:** cap auto-repair at 1 attempt per `_run_goal` invocation (use a
`_repaired` boolean flag) to prevent infinite loops if the dep chain can't be
resolved.

## Scope files

- `backend/app/worker.py` (the `_run_goal` method only)
- `backend/app/storage.py` — check if `set_depends_on` already exists; if not,
  add it (similar to the existing `PATCH /depends_on` endpoint logic in
  `api/tasks.py:set_task_depends_on`).

## Acceptance

- A goal with two subgoals where SG-B's scout depends on SG-A's doc (but SG-B
  has no sibling dep on SG-A) auto-repairs and runs SG-A before SG-B.
- The warning log line is emitted.
- No regression on goals that already have correct sibling deps.
- `pytest tests/ -k "goal or worker or depend" --tb=short` passes.

# History
