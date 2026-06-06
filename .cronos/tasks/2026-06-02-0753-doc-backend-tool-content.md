---
agent_mode: auto
agent_model: haiku
claude_session_id: null
created_at: '2026-06-02T07:53:22Z'
depends_on:
- 2026-06-02-0753-review-backend-tool-content
id: 2026-06-02-0753-doc-backend-tool-content
manual_order: 0
parent_id: 2026-06-02-0718-backend-tool-content-endpoint
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: backlog
title: doc – backend-tool-content
type: task
updated_at: '2026-06-02T07:53:22Z'
waiting_question: null
---

# Brief

CC-v1 doc phase for sub-goal: backend tool-content endpoint (GET /api/spaces/{space_id}/tool-content).

## Scout context

Read the shared scout report at `.cronos/pipeline/ai-tools-detail-screens/scout-report-ai-tools-detail-screens.md` before starting.

## Scope

Primary files: backend/app/api/tools.py, backend/app/models.py

## Phase instructions

Follow the CC-v1 doc agent contract (`.claude/agents/pipeline-doc-sync.md`).
Artifact path: `.cronos/pipeline/ai-tools-detail-screens/doc-report-backend-tool-content.md`

Then run the pipeline gate:
```
/pipeline-gate
```

# History
