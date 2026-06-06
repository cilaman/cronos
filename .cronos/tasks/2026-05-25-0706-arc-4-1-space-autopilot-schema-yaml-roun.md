---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on: []
id: 2026-05-25-0706-arc-4-1-space-autopilot-schema-yaml-roun
manual_order: 1
parent_id: 2026-05-25-0705-arc-4-autonomous-todo-autopilot
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'arc-4/1: Space.autopilot — schema + yaml round-trip'
type: task
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

Add `autopilot: Literal["disabled","enabled","paused"] = "disabled"` to the `Space` model.

## Changes
1. `backend/app/models.py` — add `autopilot` field with default `"disabled"`.
2. `backend/app/space_storage.py` — extend `parse_space_yaml` and `dump_space` to handle `autopilot`.
3. Add `SpaceStore.set_autopilot(space_id, mode)` with atomic tmpfile + os.replace.
4. Extend `PATCH /api/spaces/{id}` to accept `autopilot`.

## Acceptance
- Space without `autopilot:` in `space.yml` defaults to `"disabled"`. Setting to `"enabled"` via API persists. Back-compat with existing space files.


Branch: `feature/arc-4-autopilot`. Test gate: invoke `test-architect` before commit. Commit prefix: `arc-4:`.

# History
