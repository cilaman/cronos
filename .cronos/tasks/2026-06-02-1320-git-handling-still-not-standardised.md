---
agent_mode: auto
agent_model: opus-4-8
claude_session_id: ff42f103-5a11-4128-a03d-0f540ab5dcf6
created_at: '2026-06-02T13:20:44Z'
depends_on: []
id: 2026-06-02-1320-git-handling-still-not-standardised
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 3
proposed_pr_path: null
space_id: cronos-development
state: archived
title: Git handling still not standardised
type: task
updated_at: '2026-06-04T10:27:53Z'
waiting_question: null
---

# Brief

Create Cronos GOAL/GOALS: 
Please update skills and processes in a way, that every goal on a root level (so this does not cover sub-goals of a goal) must (if development goal, that delivers updates to GIT repository)
- create his own feature branch. 
- working trees for sub-goals or sub tasks should be based upon this feature branch
- every subtask or subgoal that delivers something to git must commit and push to this feature branch.
- when finalising this root goal, and after a testing is successfully done, this feature branch should be rebased to main and merged. 
- Upon successful merge the original feature branch can be deleted from GIT.

# History

```
2026-06-02T13:24:17Z [agent] run=0 model=claude-opus-4-8 mode=auto
I'll start by investigating the current git-handling skills to understand the gap before designing the goal.

Now let me understand the goal/task structure and the create-goal skill before designing the work.

I have the full picture. The current skills resolve the feature branch from the **immediate** `parent_id`, which breaks for nested sub-goals, and `goal-finalize` explicitly never deletes the branch. The brief wants one shared feature branch per *root* goal, plus branch deletion after merge.

Let me verify the backend is reachable and check for any existing related goal before creating one.

Backend is reachable. The skills exist (from the 2026-05-26 "Git Workflow Skills" goal) but resolve the feature branch from the *immediate* parent and never delete the branch. I'll create one goal with four tightly-scoped tasks to standardise this. Let me create it.

Goal created. Now I'll create the four child tasks with concrete edit instructions and dependencies.

All four tasks created. Let me verify the goal tree and dependency wiring.

The goal tree is correctly wired: T1 is the foundation, T2/T3 depend on it, and T4 (final integration, runs `/goal-finalize`) depends on both. The goal and tasks sit in backlog ready for the worker.

This task made no code changes in the workspace (only API calls), so there's nothing to commit. Let me record the ongoing work in memory.

Done. I created the goal **`2026-06-02-1322-standardise-git-feature-branch-lifecycle`** with four wired child tasks.

**The problem it fixes:** the three git skills (`goal-branch-setup`, `goal-task-commit`, `goal-finalize`) currently derive `feature/<slug>` from a task's *immediate* `parent_id`, so nested sub-goals each spawn their own branch instead of sharing the root goal's; and `goal-finalize` explicitly never deletes the merged branch.

**Child tasks** (each brief carries exact file paths + code snippets):
1. **Add root-goal resolution + rework goal-branch-setup** (opus) — introduces a canonical `resolve_root_goal()` helper that walks the `parent_id` chain to the topmost goal; branch = `feature/<root-goal-slug>`; sub-goals reuse it.
2. **Update goal-task-commit** → commit/push to the root feature branch (depends on 1).
3. **Update goal-finalize** (opus) → gate on the root goal and delete the branch (local + `push origin --delete`) after a green merge (depends on 1).
4. **Sync task-finalize / create-goal docs** to the new standard; the final integration task runs `/goal-finalize` (depends on 2 + 3).

The goal sits in backlog ready for the worker. This task only made API calls (no workspace code changes), and I recorded the in-flight standard in project memory.

STATUS: DONE
```
