---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-02T14:20:09Z'
depends_on:
- 2026-06-02-1420-backend-include-type-field-in-children-p
id: 2026-06-02-1420-frontend-add-type-to-childprogressitem-i
manual_order: 0
parent_id: 2026-06-02-1419-distinguish-subtasks-from-subgoals-in-ex
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: backlog
title: 'Frontend: add type to ChildProgressItem interface'
type: task
updated_at: '2026-06-02T14:21:05Z'
waiting_question: null
---

# Brief

Update the TypeScript `ChildProgressItem` interface to include the `type` field exposed by the backend.

## File to edit
- `frontend/src/types.ts` lines 29-35

## Change
```ts
export interface ChildProgressItem {
  id: string;
  title: string;
  state: TaskState;
  priority: number;
  updated_at: string;
  type?: TaskType;  // add this
}
```

## Depends on
Backend task: "Backend: include type field in children_progress items"

## Acceptance criteria
- TypeScript compiles without errors
- `child.type` is accessible where ChildProgressItem is used (Card.tsx)

# History
