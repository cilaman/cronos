---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-07T11:27:59Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-07-1127-feature-detail-view
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
title: Feature Detail View
type: goal
updated_at: '2026-06-15T12:30:16Z'
waiting_question: null
---

# Brief

The Features board has no detail view — every feature card click is a no-op. This goal
builds the feature detail panel and wires all existing backend endpoints to the frontend for the
first time.

## Background

The backend already implements all required endpoints:
- `GET /api/features/{id}` — returns `FeatureRead` with `realizing_items`
- `PATCH /api/features/{id}` — edit title / brief
- `POST /api/features/{id}/process` — enqueue decomposition
- `PATCH /api/features/{featureId}/realize` — link/unlink a task

None of these are wired to the frontend. Feature cards pass `onOpen={() => {}}` (dead no-op).

## Sub-goals

1. **API Client + Hooks** — Add 4 missing API methods to `api.ts` and 4 React Query hooks to
   `useFeatures.ts`
2. **FeatureDetail Panel + Board Wiring** — Build the right-rail detail component (mirroring
   `Detail.tsx` for tasks), wire `FeaturesBoard` onOpen, fix `Board.tsx` shared-backlog deep-link

Pipeline artifacts: `.cronos/pipeline/feature-detail-view/`

# History

```
2026-06-08T11:17:20Z [agent]
Paused: Sub-goal 'SG2: FeatureDetail Panel + Board Wiring' ended in waiting state. Completed 2, skipped 0 already-done.
```

```
2026-06-08T11:26:46Z [agent]
Waiting for in-flight child task to complete. Completed 0, skipped 2 already-done.
```

```
2026-06-08T12:01:26Z [agent]
Waiting for in-flight child task to complete. Completed 0, skipped 2 already-done.
```

```
2026-06-08T12:07:22Z [agent]
All tasks complete. Completed 0, skipped 3 already-done.
```
