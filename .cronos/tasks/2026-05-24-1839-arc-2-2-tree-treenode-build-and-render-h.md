---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on:
- 2026-05-24-1838-arc-2-1-card-ui-tight-density-variant-fo
id: 2026-05-24-1839-arc-2-2-tree-treenode-build-and-render-h
manual_order: 2
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'arc-2/2: Tree + TreeNode — build and render hierarchy'
type: task
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

Build a recursive tree from the flat task list. Render with expand/collapse on goals. Reuse `Card density="tight"` from Task 1.

## Changes
1. New `frontend/src/components/Tree.tsx` — props: `tasks: Task[]`, `spaceId?`, `onOpenTask?`. Helper `buildTree(tasks): TreeNode[]`. Sort children: `manual_order ASC, priority DESC, created_at ASC`.
2. New `frontend/src/components/TreeNode.tsx` — props: `node`, `depth`, `expanded`, `onToggle`. Left edge: chevron when has children; indent by `1.25rem × depth`. Renders `<Card density="tight">`. Clicking opens Detail modal.
3. Expand/collapse state in `Tree` (Set<task_id>). Initial state: collapsed except path to currently-open task.
4. Orphans (parent_id pointing at missing task) treated as roots with gray-dot annotation.


Branch: `feature/arc-2-tree-view`. Test gate: invoke `test-architect` before commit. Commit prefix: `arc-2:`.

# History
