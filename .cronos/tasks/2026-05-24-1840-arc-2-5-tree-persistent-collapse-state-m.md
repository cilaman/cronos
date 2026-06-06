---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on:
- 2026-05-24-1840-arc-2-4-tree-drag-and-drop-reparent-and
id: 2026-05-24-1840-arc-2-5-tree-persistent-collapse-state-m
manual_order: 5
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'arc-2/5: Tree — persistent collapse state, mobile polish, keyboard nav'
type: task
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

Persist expand/collapse per space, polish for phone widths, add keyboard navigation and full ARIA support.

## Changes
1. **Persistence:** localStorage key `cronos:tree:expanded:<space_id>` → `string[]` of expanded node ids. Read on mount; write on toggle (debounced 200ms).
2. **Mobile polish:** Verify ≥6 cards on 375×667 viewport. Indent shrinks from `1.25rem` to `0.9rem` below `sm` breakpoint. Chevron tap target ≥40×40.
3. **Keyboard navigation:** `↑/↓` prev/next visible, `←` collapse/go parent, `→` expand/go first child, `Enter` open Detail.
4. **ARIA:** `role="tree"` on container, `role="treeitem"` on each node, `aria-expanded`, `aria-level`.


Branch: `feature/arc-2-tree-view`. Test gate: invoke `test-architect` before commit. Commit prefix: `arc-2:`.

# History
