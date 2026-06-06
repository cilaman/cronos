---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on:
- 2026-05-24-1839-arc-2-2-tree-treenode-build-and-render-h
id: 2026-05-24-1839-arc-2-3-treepage-route-toolbar-sidebar-l
manual_order: 3
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'arc-2/3: TreePage route + toolbar + sidebar link'
type: task
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

Host the Tree component as a peer view to the Board with its own route and toolbar.

## Changes
1. New `frontend/src/pages/TreePage.tsx` — loads tasks via same hook as Board; applies space filter; passes tasks to `<Tree>`.
2. `frontend/src/router.tsx` — add routes `/tree` and `/spaces/:spaceId/tree`.
3. New `frontend/src/components/TreeToolbar.tsx` — space filter, sort dropdown, expand-all / collapse-all actions.
4. `frontend/src/components/Sidebar.tsx` — add "Tree" entry below "Board".
5. Board gets a small "Tree view" cross-link that preserves current space filter.


Branch: `feature/arc-2-tree-view`. Test gate: invoke `test-architect` before commit. Commit prefix: `arc-2:`.

# History
