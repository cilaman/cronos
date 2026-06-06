---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on: []
id: 2026-05-24-1924-arc-3-1-view-model-schema-space-yml-roun
manual_order: 1
parent_id: 2026-05-25-0844-arc-3-saved-kanban-views
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'arc-3/1: View model — schema + space.yml round-trip'
type: task
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

Define the `View` model and add a `views` list to space metadata. Round-trip through `space.yml`.

## Changes
1. `backend/app/models.py` — add `View` with fields: `id`, `name`, `lanes: list[TaskState]`, `type_filter: list[TaskType] | None = None`, `default: bool = False`, `created_at`, `updated_at`. Add `views: list[View]` to Space.
2. `backend/app/space_storage.py` — extend parser/serializer to handle `views`.
3. Auto-seed on first read: if `views` is empty, inject and persist a default "All lanes" view with all four states.
4. Constraints: `id` is slug max 32 chars unique per space; `lanes` non-empty; at most one `default=true` per space.

## Acceptance
- Space without `views:` in `space.yml` returns auto-seeded "All lanes" default view.
- Two views with `default: true` loads with only one marked default.
- Invalid lanes list or duplicate `id` fails with clear message.
- Round-trip with three custom views byte-equal.


Branch: `feature/arc-3-saved-views`. Test gate: invoke `test-architect` before commit. Commit prefix: `arc-3:`. Hard prerequisite: Arc 1 merged to main first.

# History
