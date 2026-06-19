---
agent_mode: auto
agent_model: sonnet
claude_session_id: null
created_at: '2026-06-19T14:08:46Z'
depends_on:
- 2026-06-19-1408-architect-plugin-backend-core
feature_key: null
feature_state: null
id: 2026-06-19-1408-impl-plugin-backend-core
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-19-1408-plugin-backend-core
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: backlog
title: impl – plugin-backend-core
type: task
updated_at: '2026-06-19T14:08:46Z'
waiting_question: null
---

# Brief

CC-v1 impl phase for: Plugin Backend Core.



NOTE: Run `/goal-branch-setup` BEFORE writing any code — this is the first code-writing task in the goal tree. It must create and check out `feature/implement-plugin-management`.
Read design report: `.cronos/pipeline/plugin-management/design-report-plugin-backend-core.md`
Scope (hard boundary): backend/app/tools/plugins.py, backend/app/models.py
Agent contract: `.claude/agents/pipeline-implementor.md`

Execute iteration i1 from the design's iterations[] plan. Write all code within the scope files. Emit `.cronos/pipeline/plugin-management/impl-report-plugin-backend-core--i1.md` (class=implementation) with files_changed[], validation_command_passed: true.

Validation:
- Backend changes: `cd backend && pytest tests/ --cov=app --cov-report=term-missing -q` (must pass, ≥60% coverage floor)
- Frontend changes: `cd frontend && npm test && npm run build` (must pass)

```
GOAL_SLUG=plugin-backend-core PHASE=impl ITER=i1 AGENT=pipeline-implementor UPSTREAM_TASK_ID=$TASK_ID /pipeline-gate
```

After gate passes: `/goal-task-commit`

# History
