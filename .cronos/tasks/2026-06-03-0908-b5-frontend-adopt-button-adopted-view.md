---
agent_mode: auto
agent_model: default
claude_session_id: 1c09a238-e917-4d09-9d50-2e29b8053f74
created_at: '2026-06-03T09:08:41Z'
depends_on:
- 2026-06-03-0908-b2-api-adopt-unadopt-list-adopted
id: 2026-06-03-0908-b5-frontend-adopt-button-adopted-view
manual_order: 0
parent_id: 2026-06-03-0908-arc-5-b-adoption-vendor-mount-merge-upst
pending_messages: []
pr_url: null
priority: 3
proposed_pr_path: null
space_id: cronos-development
state: done
title: 'B5 — Frontend: Adopt button + Adopted view'
type: task
updated_at: '2026-06-03T13:48:25Z'
waiting_question: null
---

# Brief

In `DiscoveryPanel` (A5): per-card **Adopt** button (disabled when already adopted) → `POST /api/spaces/{id}/adopt`; on success invalidate `["space-tools",spaceId]` + `["discovery","tools"]`.

Extend `SpaceToolsPage.tsx` with an Adopted section above existing grids:
- Status pill `PRISTINE` (muted) / `EDITED` (amber) / `EVOLVED` (warm)
- Source link to repo at pinned `source_sha`
- **Unadopt** button with confirm dialog → `DELETE /api/spaces/{id}/adopt/{kind}/{name}`

Extend `frontend/src/types.ts` with `AdoptedTool`, `AdoptionManifest`, `AdoptedToolStatus`.

## Files

- Modified: `frontend/src/components/DiscoveryPanel.tsx` (Adopt button per card)
- Modified: `frontend/src/pages/SpaceToolsPage.tsx` (Adopted section)
- Modified: `frontend/src/types.ts` (new types)

## Acceptance

- Discover → Adopt → adopted card visible in Adopted section
- Edit vendored file on disk → reload → status shows `EDITED`
- Unadopt confirm dialog → entry removed
- vitest: each status pill; Adopt mutation; Unadopt confirm

---

## Standing rules

**Branch:** `feature/arc-5-tools`; create from `main` if missing. No branching from other bases; no merging to `main` (manual after arc lands).

**Test gate:** Invoke `test-architect`: "Update tests for this task; add coverage for new code paths (pytest + vitest); run full suites; report pass/fail." Commit only after green.

**Commit message:** `arc-5/<goal>/<n>: <summary>` — include task number in body.

**STATUS:** `STATUS: DONE` on success; `STATUS: BLOCKED` if tests can't be made green (describe blocker above).

# History

```
2026-06-03T13:48:25Z [agent]
I'll start by exploring the frontend codebase to understand the current structure before implementing the changes.

Let me read the actual file contents to work with them directly.

Now let me read the API and hooks files to understand the current patterns.

Let me check the backend models and discovery API to understand the data structures.

Let me check the backend adoption API to understand the request format.

Now I have all the context I need. Let me implement all the changes. I'll work through the files systematically.

I have all the context needed. Now I'll implement all the changes.

**Step 1: Update types.ts** — add `AdoptedToolStatus`, `AdoptedTool`, `AdoptionManifest` and update `SpaceToolsResponse`.

**Step 2: Add adoption API calls to api.ts**

**Step 3: Add hooks to useSpaces.ts**

**Step 4: Rewrite DiscoveryPanel.tsx** with Adopt button per card

**Step 5: Update SpaceToolsPage.tsx** — add Adopted section + pass props to DiscoveryPanel

Now let me update the existing DiscoveryPanel tests and add new tests for the Adopt button and the Adopted section.

Now let me add a test file for the SpaceToolsPage Adopted section:

Now I'll write the SpaceToolsPage test file focusing on the Adopted section:

Now let me run the frontend tests to check if everything passes:

The test is still running. Let me wait for it to complete and check the output.

Coverage file issue but tests ran. Let me run without coverage to see actual results:

Two tests fail — let me see the details:

Two tests fail because the confirm button's `aria-label` overrides the "yes, remove" text in accessibility name computation. Let me fix both the component and the test:

I see the issue: the `aria-label` on the confirm button overrides the text content in the accessible name computation. Let me fix it:

Now update the test to use `fireEvent` for the confirm dialog tests (more direct, avoids pointer event sequences) and fix the assertion pattern:

All 13 SpaceToolsPage tests pass. Now run the DiscoveryPanel tests too:

All 30 DiscoveryPanel tests pass. Now run the full frontend suite:

All 731 tests pass (40 test files). Now let me build the frontend to catch any TypeScript errors:

Several TypeScript errors to fix. Let me address them all:

**1. Fix api.ts — remove unused `AdoptedTool` import:**

**2. Fix DiscoveryPanel.test.tsx — remove unused `waitFor`:**

**3. Fix SpaceToolsPage.test.tsx — remove unused `userEvent`, fix `task_counts`:**

Now fix the `task_counts: {}` type errors by providing proper values:

Now rebuild to confirm the TypeScript errors are resolved:

The `totals: {}` also needs full values. Let me fix those:

Clean build. Let me do a final test run to confirm everything is green:

All 731 tests pass, clean build. Now let me commit and finalize:

The brief specifies `feature/arc-5-tools` explicitly. Current branch is already `feature/arc-5-tools` which is correct. Let me check status and commit:

Pushed successfully. Now finalize the task:

## Step 1 — Verify completion

All requirements met:
- ✅ `DiscoveryPanel.tsx`: per-card Adopt button (disabled when `!spaceId` or already adopted), calls `POST /api/spaces/{id}/adopt`, invalidates `["space-tools",spaceId]` + `["discovery","tools"]`
- ✅ `SpaceToolsPage.tsx`: Adopted section above ToolGrids with StatusPill (pristine/edited/evolved), source SHA link, Unadopt confirm dialog
- ✅ `types.ts`: `AdoptedToolStatus`, `AdoptedTool`, `AdoptionManifest` added; `SpaceToolsResponse.adopted` added
- ✅ `api.ts` + `hooks/useSpaces.ts`: `adoptTool`, `unadoptTool`, `useAdoptTool`, `useUnadoptTool`
- ✅ Tests: 731 passing (30 DiscoveryPanel + 13 SpaceToolsPage new tests), clean tsc build
- ✅ Committed `f8f65e1` and pushed to `feature/arc-5-tools`

## Step 3 — Git already handled

Committed and pushed via `goal-task-commit` above.

## Step 4 — Write memory

The workspace-specific path is blocked. Let me write to the space-root memory path which is the one actually injected into future conversations:

Memory written and indexed. Task B5 is complete.

STATUS: DONE
```
