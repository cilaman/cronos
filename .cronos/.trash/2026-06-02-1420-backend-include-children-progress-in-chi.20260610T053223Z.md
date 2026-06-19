---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-02T14:20:51Z'
depends_on: []
id: 2026-06-02-1420-backend-include-children-progress-in-chi
manual_order: 0
parent_id: 2026-06-02-1420-inline-tree-expansion-of-subgoals-in-kan
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: backlog
title: 'Backend: include children_progress in ChildProgressItem for goal children'
type: task
updated_at: '2026-06-02T14:20:51Z'
waiting_question: null
---

# Brief

Extend the backend serialization of `children_progress.items` so that goal-type children also include their own `children_progress` data (or at minimum `has_children: bool` and counts).

## Why
The frontend needs to know if a child goal has its own children before it can render an expand button. Without this, the card has no data to show when a child goal is expanded.

## Options
**Option A** (simpler): Add `has_children: bool` and `children_done: int`, `children_total: int` to each ChildProgressItem. The frontend shows the expand chevron and count, but clicking triggers a separate API fetch (lazy load).

**Option B** (preferred, no extra round-trip): Recursively include `children_progress: { done, total, waiting, items[] }` in each ChildProgressItem, but only for immediate grandchildren (depth 2 total). Deeper nesting is cut off and the user sees a "view in tree" link.

Choose option B if the performance impact is acceptable (measure: count grandchildren in a typical board). Otherwise implement Option A.

## Acceptance criteria
- API response includes `children_progress` for goal-type children in `children_progress.items`
- Non-goal children do not include `children_progress` (keep response lean)
- No measurable increase in API latency for typical boards (< 50 tasks)

# History
