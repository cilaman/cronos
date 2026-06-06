---
agent_mode: auto
agent_model: default
claude_session_id: 29bf2b2b-6303-468f-be49-77abb747a248
created_at: '2026-05-27T12:26:45Z'
depends_on: []
id: 2026-05-27-1226-backend-add-time-frame-query-params-to-s
manual_order: 0
parent_id: 2026-05-27-1225-statistics-time-frame-filtering
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'Backend: add time-frame query params to stats endpoints'
type: task
updated_at: '2026-06-03T14:12:49Z'
waiting_question: null
---

# Brief

## Task

Add optional `from_dt` and `to_dt` ISO-datetime query parameters to all three stats endpoints so callers can limit aggregation to a time window.

## Files to change

- `backend/app/api/stats.py` — add `from_dt: datetime | None = None` and `to_dt: datetime | None = None` Query params to all three route functions
- `backend/app/stats.py` — update `compute_task_stats()` (or equivalent) to accept and apply the filter: keep only `RunStats` where `started_at` falls within `[from_dt, to_dt]`; skip tasks whose filtered run list is empty
- `frontend/src/hooks/useStats.ts` — update the three hooks to accept an optional `{ from?: string; to?: string }` param and append it to the query string
- `frontend/src/api.ts` — propagate the same params through the fetch calls

## Behaviour

- `from_dt` / `to_dt` are both optional and independent; specify one without the other is fine
- Comparison is inclusive on both ends
- Omitting both parameters returns the same results as before (no behaviour change for existing callers)
- If `from_dt > to_dt` return HTTP 422 with a clear error message
- Filter on `started_at` of each `RunStats` record (not `ended_at`)

## Acceptance criteria

- `GET /api/stats?from_dt=2026-01-01T00:00:00Z` returns only runs from that date onward
- `GET /api/spaces/cronos-development/stats?to_dt=2026-05-01T00:00:00Z` returns only older runs
- `GET /api/stats` (no params) returns identical results to before
- If `from_dt > to_dt` the API returns 422
- No test changes needed here (covered by the dedicated test task)

# History

```
2026-05-27T13:38:20Z [agent]
I'll start by exploring the relevant files to understand the current codebase structure.

Now I have a clear picture of what needs to be changed. Let me implement all the changes:

Now I have everything I need. Let me implement all four changes:

Now update the API routes:

Now update `frontend/src/api.ts`:

Now update `frontend/src/hooks/useStats.ts`:

Now let me run the backend tests to verify the changes don't break anything:

FastAPI doesn't allow `default` inside `Annotated` Query. I need to remove the `default=None` from the type aliases and keep it only in the function signatures:

All 968 tests pass with 81% coverage. Let me also do a quick TypeScript type check on the frontend:

No TypeScript errors. Now let me commit the changes:

I'm on a `cronos/*` branch. I need to set up the feature branch first.

On the feature branch. Now committing:

The working tree in the worktree is clean because my edits are in the main repo at `/data/spaces/cronos-development`. Let me check:

The edited files live in the main worktree (`/data/spaces/cronos-development`), but I need to commit them on the feature branch. I'll stage them from the main worktree by temporarily switching it:

The files are staged in the main worktree which is on `main` — but the feature branch is checked out in the task worktree, so I can't checkout the feature branch in the main worktree (git doesn't allow two worktrees on the same branch). I'll use stash to transfer the changes:

The changes are now applied in the task worktree on the feature branch. Let me commit and push:

Committed and pushed to `feature/statistics-time-frame-filtering`. Also cleaning up the stash that was left in the main worktree:

All done. Here's a summary of what was implemented:

**Backend (`backend/app/stats.py`)**
- Added `_to_utc()` helper to normalize naive/aware datetimes for safe comparison
- Added `filter_task_stats()` that filters a `TaskStats`'s runs by `[from_dt, to_dt]` on `started_at`, returning `None` when no runs remain

**Backend (`backend/app/api/stats.py`)**
- Added `from_dt` / `to_dt` as optional `Query` params to all three routes
- Added `_validate_range()` that raises HTTP 422 when `from_dt > to_dt`
- Applied filtering in each route; tasks with zero in-window runs are excluded from space/global results

**Frontend (`frontend/src/api.ts`)**
- All three stats fetch functions now accept an optional `{ from?: string; to?: string }` and append them as `from_dt`/`to_dt` query params when provided

**Frontend (`frontend/src/hooks/useStats.ts`)**
- All three hooks accept an optional `TimeFrame` param; it's included in the React Query cache key so changes trigger a re-fetch

968 tests pass, TypeScript has no errors, and the commit is on `feature/statistics-time-frame-filtering`.
```
