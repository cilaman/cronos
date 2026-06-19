---
agent_mode: auto
agent_model: default
claude_session_id: f29e5a29-c44c-4ed4-9505-c32ca47edfd8
created_at: '2026-06-02T14:19:47Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-02-1419-distinguish-subtasks-from-subgoals-in-ex
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-02-1418-task-goal-tile-visualization-improvement
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: Distinguish subtasks from subgoals in expanded card view
type: goal
updated_at: '2026-06-19T12:17:48Z'
waiting_question: null
---

# Brief

When a goal card is expanded, the child list currently shows all children identically with no visual distinction between tasks (leaf work) and sub-goals (nested goals that themselves contain children). Users cannot tell which children are goals vs tasks.

## Root cause
The `ChildProgressItem` interface in `types.ts` (line 29-35) does not include a `type` field:
```ts
export interface ChildProgressItem {
  id: string;
  title: string;
  state: TaskState;
  priority: number;
  updated_at: string;
  // type is MISSING
}
```

This requires both a backend change (include type in the serialized children_progress) and a frontend change (render goals differently from tasks).

## Deliverables
1. **Backend**: include `type` in `children_progress.items` serialization
2. **Frontend types**: add `type?: TaskType` to `ChildProgressItem`
3. **UI**: show a visual indicator distinguishing goal children from task children

# History

```
2026-06-02T14:42:54Z [agent]
Let me explore the relevant files to understand the current implementation.

Now let me read the actual files to make precise edits.

Now let me check what model `TaskSummary` fields are available in backend and the Task model:

Let me check Card.tsx imports and visual patterns before making changes:

Now I have everything I need. Let me make all four changes:

**1. Backend: add `type` to `ChildItem`**

Now let me check if `Literal` is already imported in models.py:

Good, `Literal` is already imported. **2. Backend: include `type` in `_enrich_progress()`**

**3. Frontend: add `type` to `ChildProgressItem`**

**4. Frontend: add goal indicator in Card.tsx child rendering**

Now let me verify the changes look correct by reading the relevant sections:

The changes look correct. Let me run the tests to verify nothing is broken:

All 1318 backend tests pass with 82.17% coverage. The frontend build also succeeded. Now let me finalize the task:

This is a goal child task. Delegating to goal-task-commit:

Not on the feature branch yet. Running goal-branch-setup first:

On the feature branch. Now commit the changes:

The commit landed on `main` instead of the feature branch — `git -C "$SPACE_DIR"` targeted the main worktree. Let me check the current worktree branch:

The commit went to `main` instead of the feature branch. I need to fix this — cherry-pick to feature branch and reset main:

Good, commit is on the feature branch. Now reset main back:

Now push the feature branch to origin:

Feature branch pushed with the correct commit. Now writing memory and finalizing:

MEMORY[fact]: Added `type` field to `ChildItem` backend model (`backend/app/models.py`) and `ChildProgressItem` frontend interface (`frontend/src/types.ts`). Updated `_enrich_progress()` in `backend/app/api/tasks.py` to pass `type=c.type` when building child items. Added a "goal" badge in `frontend/src/components/Card.tsx` child rendering (lines 489-493) that appears when `child.type === "goal"` — uses `border-accent/40 bg-accent/10 text-accent/80` styling to distinguish goal children from task children.

MEMORY[observation]: When using `git -C "$SPACE_DIR"` in the goal-task-commit skill, the command targets the **main worktree** (at `/data/spaces/cronos-development`), not the current task worktree. This caused a commit to land on `main` instead of the feature branch. The fix: commit using plain `git` (no `-C` flag) when already checked out to the feature branch in the task worktree — or verify `git branch --show-current` resolves to the feature branch before running `git -C`.

STATUS: DONE
```
