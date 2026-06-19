---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-07T11:28:43Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-07-1128-sg1-backend-tasksummary-additions
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-07-1128-feature-card-ux-polish
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: 'SG1: Backend TaskSummary Additions'
type: goal
updated_at: '2026-06-15T15:30:16Z'
waiting_question: null
---

# Brief

Add `realized_by_count` and `realizes_feature_key` to the `TaskSummary` backend schema
and populate them in the list/board endpoints.

Files in scope:
- `backend/app/models.py` — add fields to TaskSummary
- `backend/app/storage.py` — populate the new fields in the summary-building code
- `backend/tests/` — update or add tests for the new fields

Pipeline dir: `.cronos/pipeline/feature-card-ux-polish/`

# History

```
2026-06-08T14:44:49Z [agent]
All tasks complete. Completed 6, skipped 0 already-done.
```
