---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-02T14:20:09Z'
depends_on: []
id: 2026-06-02-1420-backend-include-type-field-in-children-p
manual_order: 0
parent_id: 2026-06-02-1419-distinguish-subtasks-from-subgoals-in-ex
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: backlog
title: 'Backend: include type field in children_progress items'
type: task
updated_at: '2026-06-02T14:20:09Z'
waiting_question: null
---

# Brief

The backend serializes children_progress for goal tasks but omits the `type` field from each item. Add it so the frontend can distinguish tasks from goals.

## How to find it
Search the backend for `children_progress` serialization. Look in the storage layer (likely `storage.py` or similar) where the `TaskSummary` response is built. The `ChildProgressItem` dict built for `children_progress.items` should include `"type": child_task.type`.

## What to change
In the backend serialization of `children_progress.items`, add the child's `type` field ("task", "goal", or "issue") to each item dict.

## Acceptance criteria
- GET /api/tasks returns `children_progress.items[*].type` for goals that have children
- The field is present for all child types (task, goal, issue)

# History
