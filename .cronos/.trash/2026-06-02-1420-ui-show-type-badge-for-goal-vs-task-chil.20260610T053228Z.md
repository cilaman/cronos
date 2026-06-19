---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-02T14:20:09Z'
depends_on:
- 2026-06-02-1420-frontend-add-type-to-childprogressitem-i
id: 2026-06-02-1420-ui-show-type-badge-for-goal-vs-task-chil
manual_order: 0
parent_id: 2026-06-02-1419-distinguish-subtasks-from-subgoals-in-ex
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: backlog
title: 'UI: show type badge for goal vs task children in expanded panel'
type: task
updated_at: '2026-06-02T14:21:05Z'
waiting_question: null
---

# Brief

Once `ChildProgressItem.type` is available, render a visual distinction between goal and task children in the expanded goal card.

## File to edit
- `frontend/src/components/Card.tsx` lines 468-505 (the expanded children panel)

## What to implement
For each child item, when `child.type === "goal"`:
- Show a small "goal" badge (reuse `TYPE_BADGE_STYLES.goal` which is already defined at line 91: violet color)
- OR show a distinct icon (e.g., a small diamond or target icon)
- Consider: indent or visually group goal children differently to make hierarchy scannable

For `child.type === "task"`: no badge needed (tasks are the default).

## Design suggestion
Add the type badge between status badge and title, or after the title as a trailing tag. Follow the existing badge pattern:
```tsx
{child.type === 'goal' && (
  <span className={cn('inline-flex items-center rounded border px-1 py-px font-mono text-[9px] font-semibold uppercase tracking-wide', TYPE_BADGE_STYLES.goal)}>
    goal
  </span>
)}
```

## Acceptance criteria
- Expanded goal cards show "goal" badge on sub-goal children
- Task children have no extra badge (clean default look)
- Light and dark themes both render correctly

# History
