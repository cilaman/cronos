---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on:
- 2026-05-24-1925-arc-3-3-viewpicker-switch-views-from-the
id: 2026-05-24-1925-arc-3-4-vieweditor-manage-views-modal
manual_order: 4
parent_id: 2026-05-25-0844-arc-3-saved-kanban-views
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'arc-3/4: ViewEditor — manage views modal'
type: task
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

Let the user manage views via a modal supporting full CRUD.

## Changes
1. New `frontend/src/components/ViewEditor.tsx` — modal with left pane (list with Edit/Duplicate/Delete/Set default actions) and right pane (editor form: name, lanes checkboxes, type filter checkboxes, default toggle). "+ New view" button.
2. Wire all four Task 2 endpoints with TanStack Query mutations. Invalidate `["views", spaceId]` and `["tasks", spaceId]`. Surface API errors inline (not toast).
3. Duplicate: `name + " (copy)"`, `default: false`. Confirm dialog on Delete; auto-select new default. Keyboard: Cmd+S saves; Esc confirms if unsaved changes.
4. Wire the `Manage views...` handler from arc-3/3 to open this modal.


Branch: `feature/arc-3-saved-views`. Test gate: invoke `test-architect` before commit. Commit prefix: `arc-3:`. Hard prerequisite: Arc 1 merged to main first.

# History
