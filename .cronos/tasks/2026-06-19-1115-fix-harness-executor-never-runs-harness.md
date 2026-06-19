---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-19T11:15:38Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-19-1115-fix-harness-executor-never-runs-harness
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: done
title: 'Fix: harness executor never runs (harness_store=None in WorkerPool)'
type: goal
updated_at: '2026-06-19T11:56:19Z'
waiting_question: null
---

# Brief

## Problem

`WorkerPool.start_for_space()` creates `Worker(...)` without passing `harness_store`, so every worker's `self.harness_store` is `None`. This causes `_run_initial_harness_run()` (worker.py ~line 791) to unconditionally return `False`, and all harness-run tasks fall through to the normal `run_agent` path instead of the harness executor. Consequences:

1. The harness executor never runs — harness DAG logic, child-task spawning, node sequencing all skipped.
2. `run_index.update_run_status()` is never called — the run index entry stays `status="running"` / `finished_at=null` indefinitely.
3. The cron overlap guard (`has_active_run()`) sees every past run as still "running" → permanently blocks future cron-triggered runs.

## Root cause (single line)

`backend/app/worker_pool.py` — `start_for_space()`, line ~61:
```python
worker = Worker(
    self._task_store,
    space_store=self._space_store,
    ...
    # harness_store is NOT passed here → worker.harness_store = None
)
```

## Fix tasks

1. **Fix WorkerPool** — pass `harness_store` when creating Worker in `start_for_space()`; store it as `self._harness_store` on WorkerPool (injected by main.py).
2. **Fix trigger node handling** — the executor logs a `WARNING` for NodeType.trigger ("unknown node type"); add an explicit `elif node.type == NodeType.trigger` branch that silently skips (no warning) and enqueues successors.
3. **Add regression tests** — verify that (a) harness executor runs correctly end-to-end, (b) `update_run_status` is called on completion, (c) cron overlap guard unblocks after run finishes.

# History

```
2026-06-19T11:56:19Z [agent]
All tasks complete. Completed 4, skipped 0 already-done.
```
