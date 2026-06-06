---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-27T12:25:47Z'
depends_on: []
id: 2026-05-27-1225-statistics-time-frame-filtering
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'Statistics: Time Frame Filtering'
type: goal
updated_at: '2026-06-03T17:17:32Z'
waiting_question: null
---

# Brief

## Goal

Add time-frame filtering to the Statistics page and Dashboard so users can explore metrics across different time windows.

## Background

Currently all stats endpoints return the full run history with no date filtering. `RunStats` records already carry `started_at` / `ended_at` timestamps, so the data is there — we just need to expose it.

## Proposed UX

**Quick presets** (single-click, shown as a pill/toggle group):
- Last 6 h | Last 24 h | Last 7 d | Last 30 d | Last 90 d | **All time** (default)

**Custom range** (calendar date pickers):
- Activates when the user picks "Custom"
- Shows a compact from/to date input (date-only is fine; time not required)

**Persistence**: selected frame stored in the URL query string so bookmarks and sharing work.

## Scope

1. **Backend** — optional `from_dt` / `to_dt` ISO-datetime query params on all three stats endpoints; runs outside the window are excluded before aggregation; tasks with zero in-window runs are omitted from space/global results.
2. **Frontend: `TimeFrameSelector` component** — reusable pill group + optional custom date pickers.
3. **Frontend: StatsPage** — integrate selector, pass params to `useStats` hooks, URL state.
4. **Frontend: DashboardPage** — add the same selector to the Key Metrics section.
5. **Backend tests** — pytest coverage for the new query params.

## Acceptance criteria

- Selecting a preset immediately re-fetches stats scoped to that window.
- Custom range: both inputs required; from must be ≤ to.
- URL reflects the active frame; reloading the page restores it.
- `All time` (no params) returns results identical to the current behaviour.
- Backend tests cover: no filter (unchanged), preset windows, custom range, edge case of empty window.

# History

```
2026-05-27T13:38:20Z [agent]
Paused: Child 'Backend: add time-frame query params to stats endpoints' ended in waiting state. Completed 0, skipped 0 already-done.
```

```
2026-05-27T14:01:35Z [agent]
Paused: Child 'Backend tests: stats time-frame filtering' ended in waiting state. Completed 1, skipped 1 already-done.
```

```
2026-05-27T14:24:35Z [agent]
Paused: Child 'Frontend: wire TimeFrameSelector into StatsPage' ended in waiting state. Completed 0, skipped 3 already-done.
```

```
2026-05-27T14:50:29Z [agent]
Paused: Child 'Frontend: add time-frame selector to DashboardPage' ended in waiting state. Completed 0, skipped 4 already-done.
```

```
2026-05-27T16:42:46Z [agent]
All tasks complete. Completed 0, skipped 5 already-done.
```
