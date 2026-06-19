---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-02T14:20:52Z'
depends_on:
- 2026-06-02-1420-frontend-types-extend-childprogressitem
- 2026-06-02-1420-ui-show-type-badge-for-goal-vs-task-chil
id: 2026-06-02-1420-ui-implement-inline-tree-expansion-for-s
manual_order: 0
parent_id: 2026-06-02-1420-inline-tree-expansion-of-subgoals-in-kan
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: backlog
title: 'UI: implement inline tree expansion for sub-goals in Card expanded panel'
type: task
updated_at: '2026-06-02T14:21:05Z'
waiting_question: null
---

# Brief

Implement the interactive tree expansion UI inside the expanded goal card panel in `Card.tsx`.

## File to edit
- `frontend/src/components/Card.tsx` (primarily lines 468-505, plus component state)

## What to build

### State
Add `expandedChildren` local state (a `Set<string>`) to track which child goal IDs are expanded:
```tsx
const [expandedChildren, setExpandedChildren] = useState<Set<string>>(new Set());
```

### Child item rendering
For each child in `childrenProgress.items`:

1. If `child.type === 'goal'` and `child.children_progress?.total > 0`:
   - Show a small expand chevron (▶/▼) button on the left
   - Clicking toggles the child in `expandedChildren`
2. Below the child row, if the child is in `expandedChildren`:
   - Render a nested indented sub-list of ITS children (from `child.children_progress.items`)
   - Each nested item is a simpler row (status badge, title, age) — no further expansion needed unless we want full recursion
   - Style: add `ml-4` or `ml-6` indentation with a subtle left border `border-l border-hairline`

### Indentation & visual hierarchy
- Level 1 (direct children): current layout
- Level 2 (grandchildren): indented by `pl-4` with `border-l border-hairline ml-3`
- Keep the expand/collapse smooth — just conditional rendering (no animation needed)

## Visual reference
The TreeNode.tsx component implements a similar pattern at the page level — use it as reference for the expand/collapse toggle pattern.

## Acceptance criteria
- Goal children in expanded panels show a clickable chevron when they have sub-children
- Clicking the chevron reveals the grandchildren list indented
- Non-goal children and childless goals show no chevron
- Collapsing works correctly
- The panel doesn't overflow the card width

# History
