---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-07T11:27:59Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-07-1127-sg1-api-client-hooks-for-feature-detail
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-07-1127-feature-detail-view
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: 'SG1: API Client + Hooks for Feature Detail'
type: goal
updated_at: '2026-06-15T10:30:16Z'
waiting_question: null
---

# Brief

Add the 4 missing API client methods and 4 React Query hooks needed by the Feature
Detail panel.

Files in scope:
- `frontend/src/api.ts` — add getFeature, patchFeature, processFeature, setRealize
- `frontend/src/hooks/useFeatures.ts` — add useFeature, usePatchFeature, useProcessFeature, useSetRealize

Pipeline dir: `.cronos/pipeline/feature-detail-view/`

# History

```
2026-06-08T10:17:04Z [agent]
All tasks complete. Completed 6, skipped 0 already-done.
```
