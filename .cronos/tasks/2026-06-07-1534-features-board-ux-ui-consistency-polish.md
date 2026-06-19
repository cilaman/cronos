---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-07T15:34:22Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-07-1534-features-board-ux-ui-consistency-polish
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: Features board UX/UI consistency polish
type: goal
updated_at: '2026-06-15T13:30:16Z'
waiting_question: null
---

# Brief

The Features board has several UX divergencies compared to the Tasks board and harness editor. This goal fixes the most impactful inconsistencies identified in the frontend audit.

## Issues to fix

**UX-1 — Issue link icon is wrong**
Feature cards show a generic `IconFileText` for both GitHub issues AND proposed-issue markdown files. There's no way to tell them apart. GitHub issues should use a distinctive GitHub/issue icon and render as `#123` (the issue number).

**UX-2 / UX-3 — realized_by shows raw UUIDs; no realizing_items count**
The Tasks board shows goal progress as "done/total" badge. The Features board shows `realized_by` as raw UUID strings and has no count of linked tasks. Should display "3 goals" or "2 tasks linked" with a count badge on the card.

**UX-11 — State-change drag has no visual feedback**
Dragging a feature to a new lane calls `transitionFeatureState` but there is no loading indicator, no success toast, and no error toast. 409 (illegal transition) failures are silently swallowed; the card resets on next poll. Should show a brief toast on success and an error toast on 409.

**UX-5 — Within-lane drag has no affordance**
Features cannot be reordered within a lane (ordering is not supported), but the drag handles appear anyway. Either remove drag handles for within-lane moves or add a visual indicator that reordering is not available.

**NP-1 — FeatureComposer swallows 400 "space not linked"**
When the space has no linked git_repo_url, `createFeature` returns 400. The FeatureComposer silently catches this and shows nothing. Should show an inline error: "This space must be linked to a git repository to track features."

## Files in scope
- `frontend/src/components/FeaturesBoard.tsx`
- `frontend/src/components/Card.tsx` (shared card — check before editing; may affect Tasks board)
- `frontend/src/hooks/useFeatures.ts`
- `frontend/src/api.ts` (transitionFeatureState error handling)

# History

```
2026-06-08T13:07:15Z [agent]
All tasks complete. Completed 3, skipped 0 already-done.
```
