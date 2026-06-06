---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on:
- 2026-05-24-1839-arc-2-3-treepage-route-toolbar-sidebar-l
id: 2026-05-24-1840-arc-2-4-tree-drag-and-drop-reparent-and
manual_order: 4
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'arc-2/4: Tree drag-and-drop — reparent and reorder siblings'
type: task
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

Enable dragging a tree node onto another (becomes child) or between nodes at same depth (becomes sibling). Uses `@dnd-kit`.

## Changes
1. `Tree.tsx` wraps children in `DndContext`.
2. `TreeNode.tsx` declares two drop zones: on-card (reparent via `PATCH /api/tasks/{id}/parent`) and between-cards (reorder via `PUT /api/tasks/reorder`).
3. Cycle errors from API show as a transient toast and tree reverts optimistic move.
4. Touch support: long-press 200ms to start drag. Cards in `active` state are not draggable (show "running" tooltip).


Branch: `feature/arc-2-tree-view`. Test gate: invoke `test-architect` before commit. Commit prefix: `arc-2:`.

# History
