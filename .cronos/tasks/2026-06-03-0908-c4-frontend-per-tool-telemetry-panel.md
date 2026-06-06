---
agent_mode: auto
agent_model: default
claude_session_id: c8d2958f-8e09-4c2c-b11c-1c1e146887c0
created_at: '2026-06-03T09:08:41Z'
depends_on:
- 2026-06-03-0908-c2-per-tool-telemetry-rollup-api
id: 2026-06-03-0908-c4-frontend-per-tool-telemetry-panel
manual_order: 0
parent_id: 2026-06-03-0908-arc-5-c-evolution-tagged-traces-evolve-t
pending_messages: []
pr_url: null
priority: 3
proposed_pr_path: null
space_id: cronos-development
state: done
title: 'C4 — Frontend: per-tool telemetry panel'
type: task
updated_at: '2026-06-03T14:52:52Z'
waiting_question: null
---

# Brief

Extend the Adopted section (B5): each adopted tool card gets a `calls/success%` strip for last 30d. Click expands `frontend/src/components/AdoptedToolTelemetry.tsx`:

- Per-day calls chart (simple bar or sparkline)
- Error rate
- Last 5 runs linking to their traces

TanStack query key `["tool-telemetry", spaceId, kind, name, window]`.

## Files

- New: `frontend/src/components/AdoptedToolTelemetry.tsx`
- Modified: `frontend/src/pages/SpaceToolsPage.tsx` (add telemetry strip + expand)

## Acceptance

- Strip renders correct call count and success percentage
- Click expands detail panel
- vitest covers: empty-history state, strip renders with data, expand/collapse

---

## Standing rules

**Branch:** `feature/arc-5-tools`; create from `main` if missing. No branching from other bases; no merging to `main` (manual after arc lands).

**Test gate:** Invoke `test-architect`: "Update tests for this task; add coverage for new code paths (pytest + vitest); run full suites; report pass/fail." Commit only after green.

**Commit message:** `arc-5/<goal>/<n>: <summary>` — include task number in body.

**STATUS:** `STATUS: DONE` on success; `STATUS: BLOCKED` if tests can't be made green (describe blocker above).

# History

```
2026-06-03T14:52:52Z [agent]
Let me explore the relevant files before implementing the telemetry panel.

The Explore agent may have read from the main branch. Let me check the actual files on the feature branch.

Good, the feature branch has C2. Let me read the actual telemetry endpoint and SpaceToolsPage.

Now let me read the SpaceToolsPage and the frontend types to understand the current state.

Now let me check the types and existing hooks.

Now let me check the frontend test setup.

Now I have everything I need. Let me implement the telemetry panel. I'll start by checking the api.ts file structure.

Now I'll implement all the changes. First, let me get the actual files from the feature branch to modify them.

Good, I'm on the right branch. Now I'll implement all the changes.

Now I'll add the `ToolTelemetryResponse` type and make all the required changes:

Now add the API call:

Now add the telemetry API call after the unadoptTool entry:

Now add the hook to `useSpaces.ts`:

Now create the `AdoptedToolTelemetry.tsx` component:

Now update `SpaceToolsPage.tsx` to integrate the telemetry strip into each adopted tool card:

Now find the adopted tool row rendering to add the telemetry strip:

I need to restructure the adopted tool row to include the telemetry strip. The row needs to become a column layout:

Now let me write the vitest tests:

Now I'll create the test file:

Now let's run the frontend tests to check for errors:

The existing SpaceToolsPage tests mock `useSpaces` but don't include `useToolTelemetry`. Let me check and fix that:

I need to add `AdoptedToolTelemetry` to the existing SpaceToolsPage test mock. The cleanest fix is to stub the component:

Now fix the TypeScript issue in the AdoptedToolTelemetry test — the `as` cast is too narrow:

TypeScript is clean. Now run the tests again:

All 741 tests pass. Now let me invoke the test-architect to run the full suites:

All 750 frontend tests and 1510 backend tests pass. Now let me commit and finalize.

The branch `feature/arc-5-tools` is correct — C1/C2/C3 all committed there. Let me proceed with the commit.

**Step 1 — Verify completion**

All requirements met:
- `frontend/src/components/AdoptedToolTelemetry.tsx` created — strip + expand/collapse panel
- `frontend/src/pages/SpaceToolsPage.tsx` updated — telemetry strip in each AdoptedSection row
- `useToolTelemetry` hook with correct TanStack query key `["tool-telemetry", spaceId, kind, name, window]`
- 19 vitest tests covering all required scenarios (empty-history, strip with data, expand/collapse)
- 750 vitest + 1510 pytest green

**Step 3 — Git**

Already committed and pushed via goal-task-commit (commit `20b22cc` on `feature/arc-5-tools`).

**Step 4 — Write memory**

Writing to the workspace-specific path is blocked. I'll write to the space-root memory where future runs can find it.

Memory written and indexed. 

STATUS: DONE
```
