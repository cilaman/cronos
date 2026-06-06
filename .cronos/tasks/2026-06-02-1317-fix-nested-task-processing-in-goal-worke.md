---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-02T13:17:46Z'
depends_on: []
id: 2026-06-02-1317-fix-nested-task-processing-in-goal-worke
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: done
title: Fix nested task processing in goal worker
type: goal
updated_at: '2026-06-02T13:51:17Z'
waiting_question: null
---

# Brief

## Problem

When a Cronos goal has sub-goals as direct children, and those sub-goals have their own child tasks, the worker ignores the nested tasks. The sub-goals are sent to `run_agent()` as if they were plain tasks — the agent gets a 'task' with no brief, and the nested tasks remain in BACKLOG forever.

## Root Cause (Confirmed)

In `backend/app/worker.py`, `_run_goal()` iterates over direct children and **unconditionally calls `run_agent()` on each one**, regardless of whether the child is a regular task or a sub-goal.

```python
# Current (broken) — always calls run_agent, even for sub-goals
child_result = await run_agent(child, ...)
```

A sub-goal should instead be handled by recursively calling `_run_goal(child_id)`, which will then orchestrate its own children (the nested tasks).

## Solution

1. In the child-iteration loop of `_run_goal()`, check `child.type == "goal"` before calling `run_agent()`.
2. If the child is a sub-goal, call `await self._run_goal(child_id, user_message=None)` recursively.
3. Add backend tests covering the 2-level (goal → sub-goal → task) and 3-level hierarchy cases.
4. Upgrade the running instance to verify the fix end-to-end.

## Child tasks

1. Fix `_run_goal()` to recurse into sub-goals
2. Add backend tests for nested goal execution
3. Upgrade and verify the fix

# History

```
2026-06-02T13:51:17Z [agent]
All tasks complete. Completed 3, skipped 0 already-done.
```
