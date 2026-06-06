---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on:
- 2026-05-25-0706-arc-4-1-space-autopilot-schema-yaml-roun
id: 2026-05-25-0707-arc-4-3-autopilot-pickup-module-worker-i
manual_order: 3
parent_id: 2026-05-25-0705-arc-4-autonomous-todo-autopilot
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'arc-4/3: Autopilot pickup — module + worker idle hook'
type: task
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

Implement the autopilot pickup logic and wire it to the worker's idle hook.

## Changes
1. New `backend/app/autopilot.py` with `eligible_backlog(space_id, store) -> list[Task]`, `rank(tasks) -> Task | None`, `pickup_next(space_id, store) -> Task | None`, `start_picked(task, store, pool)`.
2. Wire idle hook into `Worker.__init__` and `_run_one` finally block.
3. Wire pool in `start_for_space` with closure that calls `pickup_next` after each task finishes when autopilot is enabled.


Branch: `feature/arc-4-autopilot`. Test gate: invoke `test-architect` before commit. Commit prefix: `arc-4:`.

# History
