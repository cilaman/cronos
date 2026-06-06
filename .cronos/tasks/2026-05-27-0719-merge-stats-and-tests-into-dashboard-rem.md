---
agent_mode: auto
agent_model: default
claude_session_id: 66d856ec-77bf-4969-acfb-1a71723c9849
created_at: '2026-05-27T07:19:07Z'
depends_on:
- 2026-05-27-0718-rename-board-kanban-and-memory-memory-br
id: 2026-05-27-0719-merge-stats-and-tests-into-dashboard-rem
manual_order: 0
parent_id: 2026-05-27-0715-menu-changes-goal
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: Merge Stats and Tests into Dashboard; remove as separate pages
type: task
updated_at: '2026-06-03T10:12:03Z'
waiting_question: null
---

# Brief

Integrate Stats and Test Reports content into the Dashboard page, then remove them as separate nav entries.

The goal is a unified Dashboard that serves as the command centre: overview tiles, spaces, activity, AI performance stats, and latest test health -- all in one place.

## What to do

### 1. Extend DashboardPage (frontend/src/pages/DashboardPage.tsx)

Add two collapsible sections below the existing activity feed:

**AI Stats section** -- a compact version of StatsPage GlobalView:
- Row of tiles: Total runs, Total tokens, Est. cost, Total time
- Tool usage bar chart (top 5 tools)
- Exit reason badges
- Space filter dropdown to scope stats (same as StatsPage)
- The full per-task stats table can be omitted from Dashboard (too detailed for overview)

**Test Reports section** -- latest report per selected space:
- Space filter dropdown
- SummaryBar (passed/failed/errors/skipped/coverage tiles) from most recent report
- Trend strip (last 10 runs)
- No suite detail expanded by default (keep it compact)

You can reuse/import helper components from StatsPage and TestReportsPage (StatTile, ToolBar, ExitReasonBadge, SummaryBar, TrendStrip, etc.) -- extract them into the same file or a shared file as needed.

### 2. Update Sidebar (frontend/src/components/Sidebar.tsx)
- Remove the "Stats" nav entry (route /stats)
- Remove the "Tests" nav entry (route /tests)

### 3. Update Router (frontend/src/router.tsx)
- Remove /stats and /tests routes (or add redirects to / if you prefer)
- Remove imports of StatsPage and TestReportsPage

### 4. StatsPage.tsx and TestReportsPage.tsx
- These files can be left in place but are no longer linked from anywhere.
  Alternatively, delete them if it feels cleaner -- your call.

## Checks
- Run frontend tests: cd frontend && npm test
- Run backend tests: cd backend && pytest tests/ --cov=app --cov-report=term-missing
- Fix any failures.

Finish with /goal-task-commit.

# History

```
2026-05-27T09:11:40Z [agent]
I'll start by exploring the relevant frontend files to understand the current structure.

Now let me read the actual file contents to work with the precise code.

Now let me read the sidebar and router files.

Now I have everything I need. Let me implement all the changes: extend DashboardPage, update Sidebar, and update the router.

Now update the Sidebar to remove Stats and Tests nav entries:

Now update the router to remove the /stats and /tests routes:

Now let me check if `TestReportSummary` is exported from `../types`:

Good. Now let's run the frontend tests:

The `useRoutePreview` error seems pre-existing. Let me check which specific test file is failing:

The `DetailPRSection.test.tsx` failure is pre-existing (`useRoutePreview` not in the mock). Let me fix it:

I need to add `useRoutePreview` to the mock. Let me check its signature:

Now run the tests again to verify everything passes:

All 36 test files and 661 tests pass. Now let's run the backend tests:

All 968 backend tests pass with 81.5% coverage (well above the 60% floor). Now commit via the skill:

The feature branch `feature/menu-changes-goal` exists. Let me check it out and commit:

The feature branch is checked out in the main worktree. I'll commit on the current branch and push to the feature branch directly:

I need to rebase my commit on top of the other tasks' commits on the feature branch:

Good, rebase succeeded. Let me pop the stash and verify tests still pass:

All tests pass. Now push to the feature branch:

All done. The commit is on `feature/menu-changes-goal` at `1772355`.

**Summary of changes:**

- **`DashboardPage.tsx`** — Added two collapsible sections: "AI Performance" (global stats tiles, top-5 tool bar chart, exit reason badges via `useGlobalStats`) and "Test Health" (space filter, `SummaryBar`, `TrendStrip` via `useTestReports`). Both start collapsed.
- **`Sidebar.tsx`** — Removed the Stats and Tests nav entries.
- **`router.tsx`** — Removed `/stats`, `/tests`, `/spaces/:spaceId/stats`, `/spaces/:spaceId/tests` routes and their imports.
- **`DetailPRSection.test.tsx`** — Fixed pre-existing test failure by adding missing `useRoutePreview` to the mock.

All 36 frontend test files (661 tests) and 968 backend tests pass.
```
