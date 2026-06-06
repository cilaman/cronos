---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-02T14:20:51Z'
depends_on:
- 2026-06-02-1420-backend-include-children-progress-in-chi
id: 2026-06-02-1420-frontend-types-extend-childprogressitem
manual_order: 0
parent_id: 2026-06-02-1420-inline-tree-expansion-of-subgoals-in-kan
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: backlog
title: 'Frontend types: extend ChildProgressItem with nested children_progress'
type: task
updated_at: '2026-06-02T14:21:05Z'
waiting_question: null
---

# Brief

Update the `ChildProgressItem` TypeScript interface to support recursive nesting for tree expansion.

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
  type?: TaskType;  // from earlier task
  children_progress?: {    // NEW — only present for goal-type children
    done: number;
    total: number;
    waiting: number;
    items?: ChildProgressItem[];  // recursive — same type
  } | null;
}
```

The recursive `ChildProgressItem[]` type is correct because the structure mirrors the parent `TaskSummary.children_progress`.

## Acceptance criteria
- TypeScript compiles without errors (no circular type issues — TypeScript handles recursive interfaces fine)
- `child.children_progress?.items` is accessible in Card.tsx

# History
