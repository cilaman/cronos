---
agent_mode: auto
agent_model: default
claude_session_id: 6472021f-27a7-40c4-89ba-679937552e39
created_at: '2026-06-07T15:33:48Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-07-1533-wire-feature-cards-to-open-featuredetail
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-07-1533-build-feature-detail-panel-and-wire-miss
pending_messages: []
pr_url: null
priority: 1
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: Wire feature cards to open FeatureDetailPanel on click
type: task
updated_at: '2026-06-15T13:30:16Z'
waiting_question: null
---

# Brief

In `frontend/src/components/FeaturesBoard.tsx`:

1. Add `selectedFeatureId: string | null` state
2. Pass `onOpen={(id) => setSelectedFeatureId(id)}` to the card/lane components so clicking a feature card sets the selected ID
3. Render `<FeatureDetailPanel featureId={selectedFeatureId} onClose={() => setSelectedFeatureId(null)} />` when selectedFeatureId is non-null
4. The panel should appear as an overlay/drawer over the board (not navigate away)

In `frontend/src/pages/FeaturesPage.tsx`, also support opening the panel via URL query param `?feature={id}` so deep-linking works (UX-7 fix).

Ensure the existing drag-and-drop still works — `onClick` on the card should not fire when the drag gesture is detected.

# History

```
2026-06-08T12:38:40Z [agent]
I'll start by reading the relevant files to understand the current state.

Now let me read the FeatureDetail component and Lane component to understand the existing patterns.

Let me read the Card component to understand the drag/click behavior.

Let me check the test files to see the current test state.

The implementation looks complete in the code. Let me run the tests to verify everything passes.

All 20 tests pass. Let me run the broader test suite to confirm no regressions.

All 1175 frontend tests pass. The implementation is already complete and working:

- `FeaturesBoard.tsx` manages `openFeatureId` via `useSearchParams` (`?feature={id}`)
- `Lane` receives `onOpen={setOpenFeatureId}` and fires it on card click
- `<FeatureDetail>` renders as a modal overlay when `openFeatureId` is non-null
- Deep-linking via `?feature={id}` URL param works in both `ScopedFeaturesPage` and `GlobalFeaturesPage`
- Drag-and-drop is unaffected — the drag handle uses a separate `span` with dnd-kit `listeners` and stops click propagation

Now finalizing the task.

## Step 1 — Verify completion

All task requirements are met:
- `FeaturesBoard.tsx` has `openFeatureId` via `useSearchParams` (URL param `?feature={id}`)
- `Lane` receives `onOpen={setOpenFeatureId}` and fires it on card click
- `<FeatureDetail>` renders as modal overlay when `openFeatureId` is non-null
- Deep-linking via `?feature={id}` supported in both `ScopedFeaturesPage` and `GlobalFeaturesPage`
- Drag-and-drop unaffected — drag handle uses separate `span` with dnd-kit `listeners`
- All 20 FeaturesBoard tests pass; full suite 1175/1175 green

This is a goal child task — delegating git to `/goal-task-commit`.

Not on the feature branch yet — running `/goal-branch-setup` to check it out.

The feature branch is already checked out in another worktree. Since this task made no code changes (implementation was already complete), I'll use the no-changes path and skip commit/push.

No changes to commit — the implementation was already in place when this task ran. Skipping commit and push.

## Step 4 — Write memory

## Step 1 — Compute the memory path

## Step 2 — Write the memory file

## Step 3 — Update MEMORY.md

## Step 4 — Verify

Memory written successfully. Returning to task-finalize.

STATUS: DONE
```
