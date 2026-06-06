---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on:
- 2026-05-24-1924-arc-3-2-api-views-crud-endpoints-view-fi
id: 2026-05-24-1925-arc-3-3-viewpicker-switch-views-from-the
manual_order: 3
parent_id: 2026-05-25-0844-arc-3-saved-kanban-views
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'arc-3/3: ViewPicker — switch views from the Board toolbar'
type: task
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

Surface views in the Board toolbar as a dropdown pill. Selecting a view updates the URL; the Board re-fetches.

## Changes
1. New `frontend/src/components/ViewPicker.tsx` — lists views for current space; checkmark on current view; ★ on default; `Manage views...` entry at bottom (stubs modal open handler for Task 4).
2. `BoardToolbar.tsx` — slot ViewPicker to the left of space filter.
3. `Board.tsx` — read `view` from URL search params (default: `"default"`); pass to tasks query; hide lanes not in the view.
4. URL state: switching view calls `navigate(?view=<id>&space=<current>)`. All-spaces board does not show the picker.

## Acceptance
- Opening `/spaces/<id>/board` shows ViewPicker preloaded with default view. Selecting a view updates URL and Board reflows. Reloading restores view. All-spaces Board does not show picker.


Branch: `feature/arc-3-saved-views`. Test gate: invoke `test-architect` before commit. Commit prefix: `arc-3:`. Hard prerequisite: Arc 1 merged to main first.

# History
