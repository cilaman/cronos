---
agent_mode: plan
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on: []
id: 2026-05-25-0844-arc-3-saved-kanban-views
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: Arc 3 — Saved Kanban Views
type: goal
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

All 4 tasks ship to one shared feature branch `feature/arc-3-saved-views`. Each task's last step is to invoke the `test-architect` subagent to update the test suite.

**Hard prerequisite:** Arc 1 must be merged to `main` before this arc starts.

## Child Tasks
1. arc-3/1 — View model — schema + space.yml round-trip
2. arc-3/2 — API — views CRUD endpoints + ?view filter on board (depends on task 1)
3. arc-3/3 — ViewPicker — switch views from the Board toolbar (depends on task 2)
4. arc-3/4 — ViewEditor — manage views modal (depends on task 3)

# History
