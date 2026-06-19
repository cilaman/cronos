---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-07T11:28:43Z'
depends_on:
- 2026-06-07-1128-sg1-backend-tasksummary-additions
feature_key: null
feature_state: null
id: 2026-06-07-1128-sg2-frontend-card-board-ux-fixes
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
title: 'SG2: Frontend Card + Board UX Fixes'
type: goal
updated_at: '2026-06-15T16:30:16Z'
waiting_question: null
---

# Brief

Apply 6 frontend UX improvements to Card.tsx and FeaturesBoard.tsx.
Depends on SG1 (new TaskSummary fields: realized_by_count, realizes_feature_key).

Files in scope:
- `frontend/src/components/Card.tsx` — issue icon, realized_by_count rendering, realizes_feature_key
- `frontend/src/components/FeaturesBoard.tsx` — remove double SortableContext, add 404 guard,
  add error toast, render createFeature.error inline
- `frontend/src/types.ts` — add new TaskSummary fields to TypeScript type

Pipeline dir: `.cronos/pipeline/feature-card-ux-polish/`

# History

```
2026-06-08T15:33:17Z [agent]
All tasks complete. Completed 6, skipped 0 already-done.
```
