---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-10T14:28:59Z'
depends_on: []
feature_key: FIX-002
feature_state: planned
id: 2026-06-10-1428-feature-fix-state-divergency
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 3
proposed_issue_path: /data/spaces/cronos-development/.cronos/issues/2026-06-10-1428-feature-fix-state-divergency.md
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: backlog
title: Feature / fix state divergency
type: fix
updated_at: '2026-06-10T14:30:55Z'
waiting_question: null
---

# Brief

Feature / Fix state is divergent from Tasks, that realise the feature / fix.

States:
- Backlog - feature created 
- Processing 
-- Tasks and Goals for the Feature or fix are being created OR
-- Tasks and Goals are in Active state
- Planned - Tasks and Goals are created and in Backlog
- Waiting - Tasks and Goals are in Waiting state
- Done - Tasks and Goals for the Feature or fix are either DONE or Archived

The order of the Feature lanes should be
- Backlog, Planned, Processing, Waiting, Done

# History
