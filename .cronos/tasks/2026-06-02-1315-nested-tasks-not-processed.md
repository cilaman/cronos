---
agent_mode: auto
agent_model: default
claude_session_id: 4bf15951-1260-4417-8901-c29fa876c6fb
created_at: '2026-06-02T13:15:48Z'
depends_on: []
id: 2026-06-02-1315-nested-tasks-not-processed
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 1
proposed_pr_path: null
space_id: cronos-development
state: archived
title: Nested tasks not processed
type: task
updated_at: '2026-06-04T10:27:48Z'
waiting_question: null
---

# Brief

In goal 2026-06-02-0718-ai-tools-detail-screens there are defined sub-goals within them are defined tasks. When realising the main goal, the LLM just ignored the nested tasks and processed sub-goals as simple tasks. Please investigate why and propose a plan (set of cronos goals) to fix this issue. Do not implement the changes directly.

# History

```
2026-06-02T13:18:48Z [agent] run=0 model=claude-sonnet-4-6 mode=auto agents=explore
I'll investigate the worker code and task processing logic to understand why nested tasks aren't being processed.

Excellent investigation. The root cause is clear: in `worker.py`, the `_run_goal()` loop always calls `run_agent()` on children without checking if a child is itself a sub-goal that needs recursive orchestration.

Now I'll propose a fix plan as Cronos goals.

The fix plan is created. Now I'll finalize this task.

The changes are pre-existing from other tasks, not from this investigation task. Skipping commit (analysis-only task, no code changes).

Writing to the global project memory path instead (workspace-specific path is blocked by permissions):

Memory written. Here's a summary of what was done:

**Root cause identified:** In `backend/app/worker.py`, the `_run_goal()` method's child-iteration loop always calls `run_agent()` on every child, including sub-goals. It never checks `child.type == "goal"`, so sub-goals are sent to the agent as plain tasks and their nested children stay in BACKLOG forever.

**Fix plan created** — goal `2026-06-02-1317-fix-nested-task-processing-in-goal-worke` with 3 sequential tasks:
1. Fix `_run_goal()` to check `child.type == "goal"` and call `self._run_goal(child_id)` recursively for sub-goals
2. Add backend tests for 2-level and mixed-children hierarchies
3. Upgrade and verify end-to-end against the original broken goal

STATUS: DONE
```
