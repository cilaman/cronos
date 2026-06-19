---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-10T05:55:00Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-10-0555-implement-overflowing-lanes
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: 2026-06-10-0544-overflowing-lanes
space_id: cronos-development
state: archived
title: 'Implement: Overflowing lanes'
type: goal
updated_at: '2026-06-17T08:30:17Z'
waiting_question: null
---

# Brief

Fix the overflowing lanes bug on the Features page: when features accumulate in a lane the cards overflow past the lane's bottom border instead of the lane scrolling.

## Root cause analysis

The height chain is broken in three places:

1. **FeaturesPage** renders `<FeaturesBoard>` without a `min-h-0 flex-1 overflow-hidden` wrapper. BoardPage (Tasks board) wraps `<Board>` with `<div className="min-h-0 flex-1">` which bounds the board to remaining viewport height after the toolbar. FeaturesPage has no such wrapper, so the grid's `h-full` resolves to 100% of the full page container height rather than the remaining space.

2. **FeaturesBoard** wraps each `<Lane>` in an extra `<div className="flex min-h-0 flex-col">`. This wrapper is the direct grid child (not Lane itself). In Board.tsx, Lane is a direct grid child, so CSS Grid's `align-items: stretch` stretches Lane to fill the row height. In FeaturesBoard, the wrapper stretches but Lane (inside wrapper without `flex-1`) stays content-sized — so `overflow-y-auto` on the lane content div never gets a bounded height and never scrolls.

3. **Grid rows** default to `auto`, which means rows expand to fit their tallest content. Adding `grid-rows-[minmax(0,1fr)]` constrains the single implicit row to fill the available grid height, ensuring lanes are bounded.

## Fix

1. In `FeaturesPage` (both ScopedFeaturesPage and GlobalFeaturesPage), wrap `<FeaturesBoard>` in `<div className="min-h-0 flex-1 overflow-hidden">`.
2. In `FeaturesBoard`, change the lane wrapper div from `flex min-h-0 flex-col` to `contents` (CSS display: contents) so Lane becomes the direct grid child — matching Board.tsx's structure.
3. In `FeaturesBoard`, add `grid-rows-[minmax(0,1fr)]` and `overflow-hidden` to the grid container div.

## Files

- `frontend/src/pages/FeaturesPage.tsx` — add wrapper around FeaturesBoard
- `frontend/src/components/FeaturesBoard.tsx` — fix grid and lane wrapper

# History

```
2026-06-10T08:11:45Z [agent]
All tasks complete. Completed 1, skipped 0 already-done.
```
