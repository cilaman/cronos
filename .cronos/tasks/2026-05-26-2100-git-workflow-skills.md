---
agent_mode: plan
agent_model: default
claude_session_id: null
created_at: '2026-05-26T21:00:00Z'
depends_on: []
id: 2026-05-26-2100-git-workflow-skills
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: Git Workflow Skills — Feature Branch Lifecycle for Goals
type: goal
updated_at: '2026-06-02T21:33:35Z'
waiting_question: null
---

# Brief

Introduce three skills that implement a consistent git feature-branch lifecycle for Cronos goals. All code-modifying tasks within a goal will work on a shared `feature/GOAL-SLUG` branch. The branch is created when the goal first becomes active, tasks commit to it as they complete, and it is merged to `main` only after the full goal passes testing.

## Motivation

Without this, each task's changes live only on a temporary `cronos/TASK-ID` branch that is never merged. Bugs span multiple tasks, and there is no clear integration point. The feature-branch model gives goals a coherent, reviewable history that merges cleanly to main.

## Child Tasks

1. **g1** — Create `goal-branch-setup` skill  
   First step of every goal's first developing task: creates `feature/GOAL-SLUG` from main and checks it out.

2. **g2** — Create `goal-task-commit` skill  
   Last step of each task in a goal: stages, commits, and pushes changes to the feature branch after tests pass.

3. **g3** — Create `goal-finalize` skill  
   Last step when a goal completes: runs the full test suite, rebases the feature branch onto main, merges, and pushes.

## How to wire these into a goal

When authoring a goal whose child tasks modify code, add to each child task's brief:

```
First action: invoke /goal-branch-setup  
Last action (after tests pass): invoke /goal-task-commit
```

Add to the **final** child task's brief (or to a dedicated integration task):

```
Final action: invoke /goal-finalize
```

# History

```
2026-05-26T21:15:37Z [agent]
All tasks complete. Completed 0, skipped 3 already-done.
```
