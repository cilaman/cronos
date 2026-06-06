---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-27T07:09:09Z'
depends_on: []
id: 2026-05-27-0709-menu-and-pages-update
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 3
proposed_pr_path: null
space_id: cronos-development
state: waiting
title: Menu and pages update
type: task
updated_at: '2026-05-27T07:14:39Z'
waiting_question: Stopped by user.
---

# Brief

I need to create a goal, that will update the structure of the menu and pages it shows:
- Dashboard - merge it with stats page in a reasonable way
- Board - rename to Kanban
- Tree - this page does not make sense, tree view should be a component, not a page
- Archived - use Tree view component to show the Archived tasks and goals
- AI Tools - Leave as is
- Stats - remove as a separate page
- Tests - also merge to dashboard and remove as a separate page
- Memory - rename to Memory Browser

The goal should have a finalising task, that will be responsible for overall tests and merging from goals feature branch to main and pushing it.

# History

```
2026-05-27T07:14:39Z [agent] run=0 model=claude-sonnet-4-6 mode=auto agents=explore
I'll explore the current frontend structure to understand the existing pages and navigation before creating the goal.

Good, I have a clear picture of the structure. Now I'll set up the goal and tasks.

I'll create all the tasks for this goal now.

All 8 tasks are created. Now I'll start executing them — beginning with the feature branch setup.

Parent is null — this is the goal-level workspace. I'll create the feature branch manually and proceed with implementation.

Feature branch created and checked out. Now marking task 1 complete and moving to task 2.

Now I'll read the relevant files to implement the rename.

Now let me read all the page files I'll need to modify.

Let me quickly check the Tree and Detail component interfaces before writing the TreeView component.

(stopped by user)
```
