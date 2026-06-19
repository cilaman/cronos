---
agent_mode: auto
agent_model: opus
claude_session_id: null
created_at: '2026-06-07T10:49:05Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-07-1049-frontend-ux-wiring-audit
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-07-1049-features-fixes-deep-qa-review
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: backlog
title: Frontend UX & Wiring Audit
type: task
updated_at: '2026-06-07T10:49:05Z'
waiting_question: null
---

# Brief

Audit the frontend implementation of the Features & Fixes feature in Cronos for
UX quality, API wiring completeness, and consistency with established patterns.

## Reference patterns (read these first to understand Cronos conventions)

1. `frontend/src/components/Board.tsx` — existing Tasks board (Kanban lanes, card clicks, drag-drop)
2. `frontend/src/pages/BoardPage.tsx` — Tasks board page with detail panel
3. `frontend/src/hooks/useTasks.ts` — Tasks query/mutation hooks pattern
4. `frontend/src/api.ts` (lines 1–400 and 402–end) — full API client including feature methods

## Files to audit

5. `frontend/src/pages/FeaturesPage.tsx` — full page
6. `frontend/src/components/FeaturesBoard.tsx` — Kanban board component
7. `frontend/src/hooks/useFeatures.ts` — React Query hooks
8. `frontend/src/types.ts` — FeatureState type, FEATURE_LANES, canFeatureTransition

## Specific issues to verify

A. **Card click handler**: In `FeaturesBoard.tsx`, does clicking a card open a detail view?
   Search for `onOpen` or `onClick` on card components. If onOpen={() => {}} (no-op), this
   means users cannot view or edit feature details. Compare with Board.tsx pattern.

B. **Missing API calls**: Check `frontend/src/api.ts`. Does it expose:
   - `getFeature(featureId)` → GET /api/features/{id}
   - `patchFeature(featureId, {title?, description?})` → PATCH /api/features/{id}
   - `setRealize(itemId, featureId)` → PATCH /api/features/{featureId}/realize
   - `processFeature(featureId)` → POST /api/features/{id}/process
   If any are missing, the corresponding backend functionality is entirely inaccessible from the UI.

C. **Missing hooks**: Does `useFeatures.ts` expose:
   - `useFeature(featureId)` (single feature detail with realizing_items)
   - `usePatchFeature()` mutation
   - `useProcessFeature()` mutation
   - `useSetRealize()` mutation

D. **Feature detail panel**: Does a FeatureDetail modal/drawer/panel component exist anywhere?
   Search for it in `frontend/src/components/` and `frontend/src/pages/`. Compare with how
   the Tasks board shows task detail (TaskDetailPanel or similar).

E. **Feature card badges**: Do feature cards display:
   - `feature_key` (FEAT-001, FIX-007) as a badge — compare with how `type` is shown on task cards
   - `issue_number` / `issue_url` as a GitHub link
   - Count of `realizing_items` (e.g., "3 goals")
   - `waiting_question` when in WAITING state

F. **Process button**: Is there a UI button/action to trigger POST /api/features/{id}/process
   (which kicks off automated decomposition into a realizing goal)?

G. **Realize link UI**: Is there any UI to link a task/goal to a feature via the realize relationship?
   How does a user set `task.realizes = featureId`?

H. **Shared Backlog consistency**: In `Board.tsx`, does the Features Backlog section match the
   visual style of the FeaturesBoard backlog lane? Are the same card components used?

I. **Space selector**: Does FeaturesPage use the same space selector pattern as other pages?
   Compare with HarnessListPage or HarnessRunsPage for consistency.

J. **Error states**: Does FeaturesBoard handle loading, empty, and error states? Compare with
   BoardPage.tsx error/loading patterns. Is there a meaningful empty state for the backlog?

K. **Drag-and-drop UX**: Compare the dnd-kit usage in FeaturesBoard with Board.tsx. Are
   the drag handles, visual feedback, and transition guards implemented consistently?

L. **Route registration**: Check `frontend/src/router.tsx` and `frontend/src/App.tsx`.
   Is the Features route in the sidebar nav? Is the nav item active state handled correctly?

## Output format

Write your findings to `/data/spaces/cronos-development/.cronos/qa/features-frontend-audit.md`.
Create the directory if it doesn't exist (use Bash: `mkdir -p /data/spaces/cronos-development/.cronos/qa`).

Structure the file as:

```markdown
# Features Frontend UX & Wiring Audit

## Critical Gaps (functionality completely missing)
...

## UX Divergencies (inconsistent with Cronos patterns)
...

## Missing Polish / Nice-to-Have
...

## What Works Well
...

## Summary Table
| Issue | Severity | File:Line | Recommendation |
|-------|----------|-----------|----------------|
```

After writing the file, verify it exists with Bash.

## Acceptance

- All 12 specific issues (A–L) are verified and documented
- Findings file written to `/data/spaces/cronos-development/.cronos/qa/features-frontend-audit.md`
- Each finding includes comparison to the equivalent Tasks board pattern where applicable
- UX divergencies are characterized as either "intentional difference" or "unintended inconsistency"

Then run /task-finalize

# History
