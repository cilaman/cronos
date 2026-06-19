---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-02T14:19:38Z'
depends_on:
- 2026-06-02-1419-implement-status-pill-badge-replacing-st
id: 2026-06-02-1419-improve-expanded-child-item-layout-and-r
manual_order: 0
parent_id: 2026-06-02-1419-readable-child-items-in-expanded-goal-ca
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: backlog
title: Improve expanded child item layout and readability
type: task
updated_at: '2026-06-02T14:21:05Z'
waiting_question: null
---

# Brief

Increase text size and spacing for child items rendered inside expanded goal cards.

## File to edit
- `frontend/src/components/Card.tsx` lines 468-505

## Current rendering (simplified)
```tsx
<button className="flex w-full items-center gap-1.5 rounded px-1 py-1 text-left ...">
  <span className="h-1.5 w-1.5 shrink-0 rounded-full" />  {/* status dot */}
  <span className="flex-1 truncate text-xs text-ink-muted">{child.title}</span>
  <span className="font-mono text-[9px] text-ink-faint">{age}</span>
  <span className="inline-flex ... text-[9px]">{priority}</span>
</button>
```

## What to change
1. Title: change `text-xs text-ink-muted` → `text-sm text-ink` for improved legibility
2. Row padding: change `py-1` → `py-1.5` for breathing room
3. Gap: change `gap-1.5` → `gap-2`
4. Status dot: replace with StatusBadge pill (coordinate with status badge task)
5. Age: keep `text-[9px]` but ensure it has shrink-0
6. Consider adding a hairline separator `border-b border-hairline last:border-0` between rows

## Acceptance criteria
- Child titles are readable without straining
- Items are clearly separated visually
- Priority and status are scannable at a glance

# History
