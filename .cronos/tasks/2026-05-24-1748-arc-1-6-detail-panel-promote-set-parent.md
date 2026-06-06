---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on:
- 2026-05-24-1747-arc-1-5-card-ui-type-badge-parent-ref-bl
id: 2026-05-24-1748-arc-1-6-detail-panel-promote-set-parent
manual_order: 6
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'arc-1/6: Detail panel — promote, set parent, set dependencies'
type: task
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

Surface the three new mutations from Task 4 in the Detail modal.

## Changes
1. `frontend/src/components/Detail.tsx` — add:
   - **Promote to Goal** button (only when `type !== "goal"`). Calls `POST /api/tasks/{id}/promote`.
   - **Parent picker** — typeahead dropdown (excluding self and descendants). Calls `PATCH /api/tasks/{id}/parent`. Cycle error surfaces inline.
   - **Dependency picker** — multi-select typeahead. Calls `PATCH /api/tasks/{id}/depends_on`. Cycle error surfaces inline.
2. Wire all three to TanStack Query mutations that invalidate `["tasks"]`.
3. Add a "Children" section for goals listing child tasks with click-through.

## Acceptance
- Promoting makes the GOAL badge appear without reload. Setting parent is persisted. Cycle-creating choice shows inline error. No mutation occurs.

## Standing rules
Branch: `feature/arc-1-hierarchy` from `main`. Do NOT merge to `main` — that's manual after the arc lands.
Test gate before commit: invoke the `test-architect` subagent. Only commit after green.
Commit message: `arc-1: <summary>`. STATUS: DONE on success, STATUS: BLOCKED if tests fail.

# History
