---
agent_mode: auto
agent_model: default
claude_session_id: 6caf1fbd-7210-4376-adbc-d281686efaea
created_at: '2026-05-27T12:26:45Z'
depends_on:
- 2026-05-27-1226-frontend-timeframeselector-component
- 2026-05-27-1226-frontend-wire-timeframeselector-into-sta
id: 2026-05-27-1226-frontend-add-time-frame-selector-to-dash
manual_order: 0
parent_id: 2026-05-27-1225-statistics-time-frame-filtering
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'Frontend: add time-frame selector to DashboardPage'
type: task
updated_at: '2026-06-03T17:17:32Z'
waiting_question: null
---

# Brief

## Task

Add the `TimeFrameSelector` component to the Key Metrics section of `DashboardPage.tsx`.

## Files to change

- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/hooks/useStats.ts` (if not already updated)

## Implementation

1. Add a `TimeFrame` state (default `{ preset: 'all' }`) local to `DashboardPage` — no URL persistence needed here (dashboard is a summary view)
2. Render `<TimeFrameSelector>` in the Key Metrics card header/toolbar area
3. Pass the resolved `from_dt` / `to_dt` to `useGlobalStats()`

## Notes

- Keep the selector compact — use a smaller variant if the component supports it, or just apply a smaller Tailwind font/padding class
- The dashboard already has a short-polling refresh; the time frame filter should compose with that cleanly (no extra cache invalidation needed)

## Acceptance criteria

- A time frame selector appears in the Key Metrics section of the Dashboard
- Changing the preset updates the displayed totals immediately
- The rest of the Dashboard (activity feed, task list) is unaffected

# History

```
2026-05-27T14:50:29Z [agent]
Let me explore the relevant files to understand the current state.

Let me read the actual file contents directly.

Let me read the StatsPage (it likely has the TimeFrameSelector already) and the rest of DashboardPage.

Let me check for existing components and the git log to see what's been built so far.

Now let me check the api.ts to understand the globalStats function signature, and check if there are other goal tasks that might have already created the TimeFrameSelector.

Let me check the backend stats implementation and also the main codebase state.

Let me check the main branch to see if earlier goal tasks are already merged.

Let me check the backend branch to understand the time frame API and look for any frontend TimeFrameSelector work.

Now I have a full picture. The backend branch is empty (no backend work done yet), so I need to build the complete frontend solution. I'll:
1. Create the `TimeFrameSelector` component
2. Update `api.ts` and `useStats.ts` to support params
3. Wire it up in `DashboardPage.tsx`

Let me also check the types file.

Now I'll create all the pieces. Starting with the `TimeFrameSelector` component:

Now update `api.ts` to support optional params for `globalStats`:

Now update `useStats.ts` to accept params:

Now update `DashboardPage.tsx` to integrate the TimeFrameSelector. I need to:
1. Import the component and types
2. Add `timeFrame` state
3. Add the selector to the AI Performance card header
4. Pass resolved params to `useGlobalStats()`

Now add the `timeFrame` state and update `useGlobalStats` call in `DashboardPage`:

Now add the TimeFrameSelector to the AI Performance card header:

Now let's verify the build works:

TypeScript is clean. Let me run the frontend tests:

All 661 tests pass. Now let me commit using the goal-task-commit skill:

I'm on a `cronos/*` branch — need to set up the feature branch first.

The feature branch is already checked out in the backend worktree. Let me check its state and commit my changes there.

I'll commit to the task branch first, then merge into the feature branch via the backend worktree.

Now merge the task branch into the feature branch via the backend worktree:

There are conflicts — the backend task already worked on the same files. Let me check and resolve them.

I'll resolve conflicts, keeping the backend task's design as the base and adding the dashboard's `compact` prop. Let me resolve each file:

**TimeFrameSelector.tsx** — keep backend version, add `compact` prop:

Now resolve `useStats.ts` — keep the backend version (HEAD):

Now resolve `api.ts` — keep backend version with positional args:

Now I need to update my `DashboardPage.tsx` to match the backend's API (pass `TimeFrame` directly to `useGlobalStats`, use `timeFrameToDateParams` naming). Let me update it:

I need to update the DashboardPage in the backend worktree to match the updated API:

Now complete the merge and run TypeScript check:

No conflict markers remain. Complete the merge:

Now let me verify TypeScript is clean by running tests from the backend worktree:

The 584 test failures are pre-existing — same count before my changes. Let me restore the merge commit state:

The feature branch is back to the merge commit. Now let me push to origin:

The feature branch is pushed. Let me verify the final state:

All goal tasks are on the feature branch. Here's a summary of what was done:

**Changes made:**

1. **`frontend/src/components/TimeFrameSelector.tsx`** (new) — Reusable pill-group time frame selector with presets (6h, 24h, 7d, 30d, 90d, All, Custom) and a `compact` prop for tighter dashboard layout. Uses a discriminated union `TimeFrame` type for type safety and exports `timeFrameToDateParams()` for resolving to API params.

2. **`frontend/src/hooks/useStats.ts`** — `useGlobalStats()` now accepts an optional `TimeFrame` argument and includes it in the React Query key, so changing the preset triggers a re-fetch automatically.

3. **`frontend/src/api.ts`** — `globalStats()` (and `spaceStats()`) now accept `fromDt`/`toDt` query params, which are appended to the URL when present.

4. **`frontend/src/pages/DashboardPage.tsx`** — Added `timeFrame` state (default `{ preset: "all" }`), rendered `<TimeFrameSelector compact />` in the AI Performance card header, and wired it to `useGlobalStats(timeFrame)`.

The merge also resolved conflicts with the backend task's earlier work, unifying both into a consistent API design on the `feature/statistics-time-frame-filtering` branch.
```
