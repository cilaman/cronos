---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on: []
id: 2026-05-25-1342-arc-9-2-live-processing-pulse-on-current
manual_order: 2
parent_id: 2026-05-25-1341-arc-9-goal-processing-ux-sync
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'arc-9/2: Live processing pulse on currently-running card'
type: task
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

Show a live animated pulse on the card of any currently-running task.

## Changes
1. `WorkerPool.running_ids(space_id) -> set[str]` returns `_current_id` + `_current_goal_id`.
2. `GET /api/board`: add `is_running: bool` to `TaskSummary` (computed from pool).
3. New space-level SSE: `GET /api/spaces/{space_id}/stream` filtering for `run_start`/`run_end` events.
4. Frontend: new `useRunning.ts` hook maintaining set of running task IDs via SSE.
5. Visual: animated pulse ring top-right on running card; dot in lane header when any task in that lane is running.


Branch: `feature/arc-9-goal-ux`. Test gate: invoke `test-architect` before commit. Commit prefix: `arc-9:`.

# History
