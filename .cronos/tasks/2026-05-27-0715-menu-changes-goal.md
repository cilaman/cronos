---
agent_mode: auto
agent_model: default
claude_session_id: c57f685d-f43c-4bd4-8606-b6e24b242b6b
created_at: '2026-05-27T07:15:53Z'
depends_on: []
id: 2026-05-27-0715-menu-changes-goal
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 3
proposed_pr_path: null
space_id: cronos-development
state: archived
title: Menu changes goal
type: goal
updated_at: '2026-06-03T10:12:03Z'
waiting_question: null
---

# Brief

Create a Cronos goal with its subtasks, that will update the structure of the menu and pages it shows:

Dashboard - merge it with stats page in a reasonable way
Board - rename to Kanban
Tree - this page does not make sense, tree view should be a component, not a page
Archived - use Tree view component to show the Archived tasks and goals
AI Tools - Leave as is
Stats - remove as a separate page
Tests - also merge to dashboard and remove as a separate page
Memory - rename to Memory Browser
The goal should have a finalising task, that will be responsible for overall tests and merging from goals feature branch to main and pushing it.

# History

```
2026-05-27T07:20:01Z [agent] run=0 model=claude-sonnet-4-6 mode=auto agents=explore
I'll explore the current menu/navigation structure and then create the goal with subtasks.

Now I'll load the task management tools and create the goal with subtasks.

Let me read the key pages to understand their content before creating the tasks.

Let me also check the TreePage to understand how it works.

Now I have everything I need to create a well-structured goal. Let me create the Cronos goal using the API.

Let me check the Cronos API to understand how to create goals and tasks programmatically.

Now I'll check the running Cronos API and find the right space to create the goal in.

This workspace IS the goal task. Let me find the goal task details and create subtasks under it.

Now I'll update the goal type and create all subtasks. Let me first patch the goal type to "goal", then create all subtasks.

Good. Now I'll create all 5 subtasks:

All 5 subtasks created. Let me verify the full structure looks right:

All 5 subtasks are created and in the backlog. Let me verify the dependency chain is correct:

The goal is fully structured. Here's what was created:

**Goal:** `Menu changes goal` (type updated to `goal`)

**5 subtasks with correct dependency chain:**

```
T1: Rename Board → Kanban and Memory → Memory Browser   [no deps — runs first, sets up feature branch]
     ↓
T2: Merge Stats and Tests into Dashboard; remove pages  [depends on T1]
T3: Extract TreeView component; remove /tree from nav   [depends on T1]
     ↓
T4: Update ArchivedPage to use TreeView component       [depends on T3]
     ↓
T5: Finalize: full test suite and merge to main         [depends on T1, T2, T4]
```

**Execution flow:**
1. **T1** runs first — sets up the `feature/menu-changes-goal` branch, renames Board→Kanban and Memory→Memory Browser
2. **T2 and T3** can run in parallel — both depend only on T1
3. **T4** runs after T3 — uses the extracted TreeView component in ArchivedPage
4. **T5** runs last — runs `goal-finalize` to test, merge, and push to main

STATUS: DONE
```

```
2026-05-27T08:06:19Z [agent]
Paused: Child 'Rename Board → Kanban and Memory → Memory Browser' ended in waiting state. Completed 0, skipped 0 already-done.
```

```
2026-05-27T08:47:08Z [agent]
Paused: Child 'Extract TreeView component; remove /tree from main nav' ended in waiting state. Completed 0, skipped 1 already-done.
```

```
2026-05-27T09:11:40Z [agent]
Paused: Child 'Merge Stats and Tests into Dashboard; remove as separate pages' ended in waiting state. Completed 0, skipped 2 already-done.
```

```
2026-05-27T09:26:26Z [agent]
Paused: Child 'Update ArchivedPage to use TreeView component' ended in waiting state. Completed 0, skipped 3 already-done.
```

```
2026-05-27T09:31:03Z [agent]
Paused: Child 'Finalize: full test suite and merge feature branch to main' ended in waiting state. Completed 0, skipped 4 already-done.
```

```
2026-05-27T09:57:16Z [agent]
All tasks complete. Completed 0, skipped 5 already-done.
```
