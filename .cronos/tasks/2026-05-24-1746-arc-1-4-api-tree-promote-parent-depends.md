---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on:
- 2026-05-24-1745-arc-1-3-block-backlog-active-when-depend
id: 2026-05-24-1746-arc-1-4-api-tree-promote-parent-depends
manual_order: 4
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'arc-1/4: API — /tree, /promote, /parent, /depends_on endpoints'
type: task
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

Expose the new hierarchy mutations and reads. All cycle-creating mutations call the validators from Task 2.

## Changes
1. `backend/app/api/tasks.py` — add:
   - `GET /api/tasks/{id}/tree` — returns the task and full subtree of descendants.
   - `POST /api/tasks/{id}/promote` — flips `type` to `goal`. Idempotent (no-op if already a goal).
   - `PATCH /api/tasks/{id}/parent` — body `{parent_id: str|null}` — calls `validate_parent`. 409 on cycle.
   - `PATCH /api/tasks/{id}/depends_on` — body `{depends_on: str[]}` — calls `validate_depends_on`. 409 on cycle.
2. Extend per-task DTO to include `type`, `parent_id`, `depends_on`, `unmet_dependencies`.
3. All new/extended endpoints write back atomically (tmpfile + os.replace).

## Acceptance
- Round-trip via API: promote task → set parent on two tasks → GET /tree returns goal + both children.
- Cycle-creating `depends_on` returns 409 with a descriptive message.
- Removing a parent (`parent_id: null`) works and persists.

## Standing rules
Branch: `feature/arc-1-hierarchy` from `main`. Do NOT merge to `main` — that's manual after the arc lands.
Test gate before commit: invoke the `test-architect` subagent. Only commit after green.
Commit message: `arc-1: <summary>`. STATUS: DONE on success, STATUS: BLOCKED if tests fail.

# History
