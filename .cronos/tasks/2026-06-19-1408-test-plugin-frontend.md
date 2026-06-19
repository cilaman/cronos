---
agent_mode: auto
agent_model: sonnet
claude_session_id: null
created_at: '2026-06-19T14:08:46Z'
depends_on:
- 2026-06-19-1408-impl-plugin-frontend
feature_key: null
feature_state: null
id: 2026-06-19-1408-test-plugin-frontend
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-19-1408-plugin-frontend
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: backlog
title: test – plugin-frontend
type: task
updated_at: '2026-06-19T14:08:46Z'
waiting_question: null
---

# Brief

CC-v1 test phase for: Plugin Frontend.

Read impl report: `.cronos/pipeline/plugin-management/impl-report-plugin-frontend--i1.md`
Scope: frontend/src/types.ts, frontend/src/api.ts, frontend/src/hooks/usePlugins.ts, frontend/src/components/PluginsPanel.tsx, frontend/src/pages/SpaceToolsPage.tsx, frontend/src/components/harness/VariableInspector.tsx
Agent contract: `.claude/agents/tester.md`

Run backend pytest (`cd backend && pytest tests/ --cov=app --cov-report=term-missing`) and/or frontend vitest (`cd frontend && npm test`) as applicable for the changed files. Emit `.cronos/pipeline/plugin-management/test-report-plugin-frontend.md` (class=test) with pass/fail counts and coverage.

```
GOAL_SLUG=plugin-frontend PHASE=test AGENT=tester UPSTREAM_TASK_ID=$TASK_ID /pipeline-gate
```

# History
