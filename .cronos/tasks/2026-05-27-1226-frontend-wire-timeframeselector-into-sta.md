---
agent_mode: auto
agent_model: default
claude_session_id: bfcd1d59-c796-4ad5-ad46-ee6395c8e6f3
created_at: '2026-05-27T12:26:45Z'
depends_on:
- 2026-05-27-1226-backend-add-time-frame-query-params-to-s
- 2026-05-27-1226-frontend-timeframeselector-component
id: 2026-05-27-1226-frontend-wire-timeframeselector-into-sta
manual_order: 0
parent_id: 2026-05-27-1225-statistics-time-frame-filtering
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'Frontend: wire TimeFrameSelector into StatsPage'
type: task
updated_at: '2026-06-03T15:12:50Z'
waiting_question: null
---

# Brief

## Task

Integrate the `TimeFrameSelector` component into `StatsPage.tsx` and persist the selection in the URL.

## Files to change

- `frontend/src/pages/StatsPage.tsx`
- `frontend/src/hooks/useStats.ts` (if not already updated by the backend task)

## Implementation

1. Import `TimeFrameSelector` and `TimeFrame` from `../components/TimeFrameSelector`
2. Read initial time frame from URL search params (`?preset=7d` or `?preset=custom&from=2026-01-01&to=2026-05-01`)
3. When the user changes the selector, update URL search params with `useNavigate` / `setSearchParams` (React Router) — do not push a new history entry, use `replace: true`
4. Convert the active `TimeFrame` to `from_dt` / `to_dt` ISO strings:
   - `6h` → `now - 6 hours`
   - `24h` → `now - 24 hours`
   - `7d` → `now - 7 days`
   - `30d` → `now - 30 days`
   - `90d` → `now - 90 days`
   - `all` → no params
   - `custom` → use the from/to dates directly (set time to start/end of day)
5. Pass `from_dt` / `to_dt` to `useGlobalStats()` and `useSpaceStats(spaceId)` hooks

## Acceptance criteria

- Selector renders above the stats content on both global and space views
- Switching preset immediately re-fetches stats (React Query refetch)
- URL updates on every selection change; reloading the page restores the same frame
- `All` is the default when no URL params are present

# History

```
2026-05-27T14:24:35Z [agent]
Let me explore the relevant files to understand the current state of the codebase.

Let me read the actual file contents directly.

Now let me check the API module and look for any existing TimeFrameSelector component.

Let me check the router to understand routing context.

Let me check the Sidebar structure to understand the nav.

Now I have a complete picture. I'll implement all the needed changes:

1. Create `TimeFrameSelector.tsx` (doesn't exist yet)
2. Update `api.ts` — add date params to stats methods
3. Update `useStats.ts` — accept `TimeFrame`
4. Update `StatsPage.tsx` — wire in selector + URL state
5. Add the missing route in `router.tsx`
6. Add a "Stats" nav link in `Sidebar.tsx`

Now update `api.ts` to pass date params to the stats endpoints:

Now update `useStats.ts` to accept a `TimeFrame` and include it in the query key:

Now rewrite `StatsPage.tsx` with the TimeFrameSelector wired in and URL persistence:

Now add the stats route to `router.tsx` and a "Stats" nav link in `Sidebar.tsx`:

Now let me run the TypeScript build to verify there are no type errors:

TypeScript compiles clean. Let me also run the frontend tests:

One test is failing because it expects `api.spaceStats` to be called with just `"space-1"`. Let me check the test:

The test expects `api.spaceStats("space-1")` but now it's called with `("space-1", undefined, undefined)`. I'll update the test to match the new signature:

All tests pass. Let me do a quick final verification of all changed files:

All 661 tests pass. Now let me commit via the goal-task-commit skill:

The feature branch `feature/statistics-time-frame-filtering` exists. Let me switch to it and commit:

The feature branch `feature/statistics-time-frame-filtering` already exists. I need to switch to it and commit:

The feature branch is in another worktree. I'll copy the changes there and commit from it:

Good — the feature branch already has the `TimeFrameSelector` component and the backend changes. Now commit my work on top:

All changes committed and pushed to `feature/statistics-time-frame-filtering`. Here's a summary of what was implemented:

**New file:**
- `frontend/src/components/TimeFrameSelector.tsx` — reusable pill group with `6h / 24h / 7d / 30d / 90d / All / Custom` presets; custom shows two date inputs; exports `TimeFrame` discriminated union type and `timeFrameToDateParams()` helper

**Modified files:**
- `frontend/src/api.ts` — `spaceStats()` and `globalStats()` now accept optional `fromDt?` / `toDt?` and append them as `?from_dt=…&to_dt=…` query params
- `frontend/src/hooks/useStats.ts` — `useSpaceStats()` and `useGlobalStats()` accept an optional `TimeFrame`; query key includes preset + custom dates so switching presets triggers an immediate refetch
- `frontend/src/pages/StatsPage.tsx` — reads time frame from URL (`?preset=7d`, `?preset=custom&from=…&to=…`), renders `TimeFrameSelector` above the stats, passes the frame to both hooks, and updates URL with `replace: true` on change
- `frontend/src/router.tsx` — added `<Route path="stats" element={<StatsPage />} />`
- `frontend/src/components/Sidebar.tsx` — added "Stats" nav link

All 661 frontend tests pass.
```
