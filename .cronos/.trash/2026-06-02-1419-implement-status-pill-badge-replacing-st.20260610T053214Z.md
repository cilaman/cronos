---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-02T14:19:18Z'
depends_on: []
id: 2026-06-02-1419-implement-status-pill-badge-replacing-st
manual_order: 0
parent_id: 2026-06-02-1419-prominent-status-indicators
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: backlog
title: Implement status pill badge replacing status dot
type: task
updated_at: '2026-06-02T14:19:18Z'
waiting_question: null
---

# Brief

Replace the tiny 1.5px status dot in Card.tsx with a readable pill badge.

## Files to edit
- `frontend/src/components/Card.tsx`

## Current implementation
`STATE_DOT_STYLES` (line 95) defines dot colors. Dots appear at:
- **Tight density mode** (lines 196-199): `<span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", STATE_DOT_STYLES[task.state])} />`
- **Expanded children list** (lines 484-487): same pattern for each child

## What to implement
Create a `StatusBadge` component (or just inline styles) that renders a pill with:
- Short label: "Active", "Waiting", "Done", "Backlog", "Archived"
- Color-coded: emerald for active, amber for waiting, sky for done, ink-faint for backlog
- Size: roughly `text-[9px] px-1 py-px` (same as other badges in the file) but with filled background
- Pattern: follow the existing badge pattern used for priority (PRIORITY_STYLES) but for state

## Color palette to follow (keep dark mode variants)
```
active:   bg-emerald-100 text-emerald-700 border-emerald-200 dark:bg-emerald-400/15 dark:text-emerald-400 dark:border-emerald-400/30
waiting:  bg-amber-100   text-amber-700   border-amber-200   dark:bg-amber-400/15   dark:text-amber-400   dark:border-amber-400/30
done:     bg-sky-100     text-sky-700     border-sky-200     dark:bg-sky-400/15     dark:text-sky-400     dark:border-sky-400/30
backlog:  bg-surface-2   text-ink-faint   border-hairline
archived: bg-surface-2   text-ink-faint/60 border-hairline opacity-60
```

## Acceptance criteria
- Status is legible at a glance in tight mode
- Status badge appears in the expanded children list for each child
- Both light and dark themes render correctly

# History
