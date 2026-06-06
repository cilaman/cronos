---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on:
- 2026-05-24-1744-arc-1-2-cycle-detection-for-parent-id-an
id: 2026-05-24-1745-arc-1-3-block-backlog-active-when-depend
manual_order: 3
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'arc-1/3: Block backlog→active when deps unmet'
type: task
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

Extend the state-transition logic so a task cannot move from `backlog` to `active` while any `depends_on` task is not `done` or `archived`.

## Changes
1. `backend/app/storage.py` — add `dependencies_satisfied(task) -> bool`. The `backlog → active` transition calls this gate and raises a clear error if unsatisfied.
2. Add `unmet_dependencies: list[str]` to the API response shape for a Task (computed at serialization time).
3. Goals cannot transition to `done` while any child task is still open.

## Acceptance
- `POST /api/tasks/{id}/start` returns 409 with a clear message when any dependency is incomplete. Succeeds the moment the last blocker moves to `done`.
- `unmet_dependencies` appears on the task DTO and is empty when nothing blocks.

## Standing rules
Branch: `feature/arc-1-hierarchy` from `main`. Do NOT merge to `main` — that's manual after the arc lands.
Test gate before commit: invoke the `test-architect` subagent. Only commit after green.
Commit message: `arc-1: <summary>`. STATUS: DONE on success, STATUS: BLOCKED if tests fail.

# History
