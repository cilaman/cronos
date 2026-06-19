---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-10T14:30:48Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-10-1430-implement-feature-fix-state-divergency
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: 2026-06-10-1428-feature-fix-state-divergency
space_id: cronos-development
state: archived
title: 'Implement: Feature / fix state divergency'
type: goal
updated_at: '2026-06-17T16:30:17Z'
waiting_question: null
---

# Brief

Implements fix: Feature / fix state divergency

## Context

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

## Implementation plan

This fix addresses two separate problems:

1. **Backend state propagation** (`backend/app/feature_sync.py`): The `propagate_to_feature`
   function must correctly derive `feature_state` from the combined state of all realizing
   items (tasks/goals). The correct mapping is:
   - BACKLOG: no realizing items yet
   - PLANNED: realizing items exist and all are in `backlog` state
   - PROCESSING: any realizing item is `active` (or items are still being created)
   - WAITING: any realizing item is `waiting` (and none are `active`)
   - DONE: all realizing items are `done` or `archived`

2. **Frontend lane order** (`frontend/src/pages/FeaturesBoard.tsx` or equivalent):
   The FeaturesBoard lanes must render in the order:
   Backlog → Planned → Processing → Waiting → Done

Child tasks:
- T1: Set up feature branch (goal-branch-setup)
- T2: Fix backend feature_state propagation logic
- T3: Fix FeaturesBoard lane order in the frontend
- T4: Write backend tests for feature_state transitions

## Acceptance

- All child tasks complete.
- feature_state correctly reflects the state of realizing tasks/goals.
- FeaturesBoard lanes appear in correct order: Backlog, Planned, Processing, Waiting, Done.
- Backend tests pass (60% coverage floor).

# History

```
2026-06-10T16:01:28Z [agent]
All tasks complete. Completed 4, skipped 0 already-done.
```
