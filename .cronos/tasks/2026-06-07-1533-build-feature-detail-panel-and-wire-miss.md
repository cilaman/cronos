---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-07T15:33:48Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-07-1533-build-feature-detail-panel-and-wire-miss
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 1
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: Build Feature Detail panel and wire missing API endpoints
type: goal
updated_at: '2026-06-15T13:30:16Z'
waiting_question: null
---

# Brief

Feature cards on the FeaturesBoard are not clickable — `onOpen` and `onClick` are both no-ops. Six backend endpoints exist with no corresponding frontend API methods, hooks, or UI. This goal builds the missing feature detail experience.

## What's missing (from audit CG-1 through CG-6)

**Backend endpoints with no frontend client:**
- `GET /api/features/{id}` — returns FeatureRead with `realizing_items[]`
- `PATCH /api/features/{id}` — edit title/brief
- `POST /api/features/{id}/process` — enqueue decomposition agent
- `PATCH /api/features/{id}/realize` — link/unlink a task to a feature

**Missing API client methods in `frontend/src/api.ts`:**
- `getFeature(taskId)` → `FeatureRead`
- `patchFeature(taskId, {title?, brief?})` → `FeatureRead`
- `processFeature(taskId)` → `Task`
- `setRealize(taskId, featureId | null)` → `Task`

**Missing React Query hooks in `frontend/src/hooks/useFeatures.ts`:**
- `useFeature(taskId)` — single feature fetch
- `usePatchFeature()` — edit mutation
- `useProcessFeature()` — process mutation
- `useSetRealize()` — realize/unrealize mutation

**Missing UI:**
- Feature cards not clickable (CG-1)
- No detail panel to view brief, realizing items, waiting_question
- No Process button to trigger decomposition
- No way to link tasks to features

## Scope
Files: `frontend/src/api.ts`, `frontend/src/hooks/useFeatures.ts`, `frontend/src/components/FeaturesBoard.tsx`, plus a new `frontend/src/components/FeatureDetailPanel.tsx` (or `FeatureDetailDrawer.tsx`).

The detail panel should follow the same pattern as task detail in `BoardPage.tsx` / `ConversationStream` — a slide-in drawer from the right side that shows:
- Feature title (editable inline)
- Brief (editable, markdown-rendered)
- Feature key badge (FEAT-NNN)
- Feature state + Task state
- Process button (→ POST /process, appears when state is backlog)
- Waiting question (when state is WAITING)
- Realizing items list (task titles + state badges, linked to task detail)

# History

```
2026-06-08T12:38:41Z [agent]
All tasks complete. Completed 4, skipped 0 already-done.
```
