---
agent_mode: auto
agent_model: default
claude_session_id: 1db186bc-fa16-4b74-8e6f-2c1c9c775511
created_at: '2026-06-10T05:14:16Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-10-0514-cascade-delete
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 3
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: cascade delete
type: task
updated_at: '2026-06-17T05:30:17Z'
waiting_question: null
---

# Brief

If I delete a goal, then all of its subgoals and subtasks should be deleted as well.

# History

```
2026-06-10T05:21:43Z [agent] run=0 model=claude-sonnet-4-6 mode=auto agents=explore
I'll start by exploring the codebase to understand how task/goal deletion currently works.

Good. Now let me read the exact sections I need to modify.

Now let me read the API delete endpoint:

Let me check the existing tests for deletion to understand what's there:

Let me read the existing delete tests to understand the test patterns:

Now I have everything I need. Let me implement the cascade delete:

Now update the API endpoint to cascade worktree and trace cleanup:

Now let me add tests. First, let me read the end of the storage test file to find where to add:

Now I'll add cascade delete tests right after the existing delete tests:

Now add API-level cascade tests in `test_api_tasks.py`:

Now let's run the tests to verify everything works:

All 6 new tests pass. Now let's run the full test suite to check for regressions:

2531 tests pass, coverage at 84.97% (well above the 60% floor). No regressions.

Now let me finalize the task:

## Step 4 — Write memory

MEMORY[fact]: Cascade delete implemented in `backend/app/storage.py` `TaskStore.delete()` — now calls `self.subtree(task_id)` before any mutation to collect all descendants, then trashes each; returns `list[str]` of deleted IDs. API endpoint `backend/app/api/tasks.py` `delete_task()` now iterates the subtree for worktree and trace cleanup. 6 new tests added (4 storage, 2 API). Commit b15ef3f on main.

STATUS: DONE
```
