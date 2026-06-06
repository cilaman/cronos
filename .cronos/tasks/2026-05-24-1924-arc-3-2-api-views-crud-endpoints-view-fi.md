---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on:
- 2026-05-24-1924-arc-3-1-view-model-schema-space-yml-roun
id: 2026-05-24-1924-arc-3-2-api-views-crud-endpoints-view-fi
manual_order: 2
parent_id: 2026-05-25-0844-arc-3-saved-kanban-views
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'arc-3/2: API — views CRUD endpoints + ?view filter on board'
type: task
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

Expose CRUD for views and let the Board endpoint apply a chosen view server-side.

## Changes
1. New `backend/app/api/views.py` with endpoints: `GET /api/spaces/{id}/views`, `POST` (auto-slugs id from name), `PATCH /api/spaces/{id}/views/{view_id}` (setting default clears others), `DELETE` (refuses to delete last view; reassigns default if needed).
2. Extend `GET /api/tasks` to accept `?view=<view_id>` or `?view=default` — applies lane filter and type_filter to the Board.
3. All mutations write back atomically. Register router in `main.py`.

## Acceptance
- Creating a view via POST persists in `space.yml`. Setting one view default via PATCH clears others atomically. DELETE on last view returns 409. `GET /api/tasks?view=focus` where `focus.lanes=[active,waiting]` returns backlog and done lanes empty.


Branch: `feature/arc-3-saved-views`. Test gate: invoke `test-architect` before commit. Commit prefix: `arc-3:`. Hard prerequisite: Arc 1 merged to main first.

# History
