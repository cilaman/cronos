---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T21:02:00Z'
depends_on: []
id: 2026-05-26-2102-g2-goal-task-commit-skill
manual_order: 2
parent_id: 2026-05-26-2100-git-workflow-skills
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'g2: Create goal-task-commit skill'
type: task
updated_at: '2026-06-02T21:33:35Z'
waiting_question: null
---

# Brief

Create the `goal-task-commit` skill at `.claude/skills/goal-task-commit/SKILL.md`.

This skill is invoked as the **last action** in each developing task of a goal, after tests pass. It:
1. Verifies the worktree is on the goal's feature branch (exits with guidance if not).
2. Runs `test-architect` to confirm the test suite is green.
3. Stages all changes and creates a commit referencing the task title and ID.
4. Pushes to `origin/feature/GOAL-SLUG`, injecting `CRONOS_GIT_TOKEN` credentials when the remote is HTTPS.

# History

Implemented as part of task `2026-05-26-2051-create-git-goal`. Skill file written to `.claude/skills/goal-task-commit/SKILL.md`.
