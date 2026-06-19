---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-02T13:22:43Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-02-1322-standardise-git-feature-branch-lifecycle
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: Standardise git feature-branch lifecycle for root goals
type: goal
updated_at: '2026-06-19T12:17:48Z'
waiting_question: null
---

# Brief

Standardise the git feature-branch lifecycle so it is driven by the **root-level goal**, not the immediate parent goal.

## Problem

The three git skills (`goal-branch-setup`, `goal-task-commit`, `goal-finalize`) currently resolve the feature branch from a task's **immediate** `parent_id`. For a nested goal (a sub-goal under a root goal) this is wrong: each sub-goal creates its own `feature/<sub-goal-slug>` branch instead of all descendants sharing the root goal's branch. Also `goal-finalize` explicitly never deletes the merged branch.

## Target standard (from the request)

Every **root-level** goal (NOT sub-goals) that is a *development* goal delivering to a git repository must:
1. Create its own feature branch `feature/<root-goal-slug>`.
2. Have all sub-goals / sub-tasks base their working trees on this root feature branch (no per-sub-goal branches).
3. Have every subtask/subgoal that delivers to git commit and push to this root feature branch.
4. On finalisation of the **root** goal, after the test suite passes, rebase the feature branch onto `main` and merge it.
5. After a successful merge+push, delete the feature branch locally AND on origin.

## Key primitive

A "resolve root goal" helper that walks the `parent_id` chain (via `GET http://backend:8000/api/tasks/{id}`) up to the topmost goal. The root goal slug = root goal id with the `YYYY-MM-DD-HHMM-` prefix stripped. All three skills must use this instead of reading `parent_id` directly.

## Child tasks

1. Add root-goal resolution + rework goal-branch-setup
2. Update goal-task-commit to target the root feature branch
3. Update goal-finalize: gate on root goal + delete branch after merge
4. Sync task-finalize / create-goal docs to the new standard

All edits are to skill markdown under `.claude/skills/`. No backend/frontend code changes are expected, so the per-task git handling is documentation-only (commit the skill files).

# History

```
2026-06-02T14:17:19Z [agent]
All tasks complete. Completed 4, skipped 0 already-done.
```
