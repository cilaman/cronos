---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-07T11:27:59Z'
depends_on:
- 2026-06-07-1127-sg1-api-client-hooks-for-feature-detail
feature_key: null
feature_state: null
id: 2026-06-07-1127-sg2-featuredetail-panel-board-wiring
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
title: 'SG2: FeatureDetail Panel + Board Wiring'
type: goal
updated_at: '2026-06-15T12:30:16Z'
waiting_question: null
---

# Brief

Build the FeatureDetail right-rail panel and wire it into the Features board
and shared Task board backlog.

Files in scope:
- `frontend/src/components/FeatureDetail.tsx` — new component to create
- `frontend/src/components/FeaturesBoard.tsx:207,220` — wire onOpen
- `frontend/src/pages/FeaturesPage.tsx` — mount FeatureDetail when URL has ?feature=<id>
- `frontend/src/components/Board.tsx:304-313` — fix shared-backlog deep-link to ?feature=<id>

The panel should mirror `Detail.tsx` in structure and support:
- Feature brief display + edit (title, brief)
- Feature state + feature_key badge
- waiting_question amber box (if present)
- "Process" button (calls processFeature, disabled if already PROCESSING)
- Realizing goals section: list realizing_items (from getFeature), with link/unlink affordance

This sub-goal depends on SG1 (API client + hooks) being complete.

Pipeline dir: `.cronos/pipeline/feature-detail-view/`

# History

```
2026-06-08T11:17:20Z [agent]
Paused: Child 'review – feature-detail-panel' ended in waiting state. Completed 4, skipped 0 already-done.
```

```
2026-06-08T12:07:22Z [agent]
All tasks complete. Completed 1, skipped 5 already-done.
```
