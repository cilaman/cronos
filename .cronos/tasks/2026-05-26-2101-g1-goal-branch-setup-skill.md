---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T21:01:00Z'
depends_on: []
id: 2026-05-26-2101-g1-goal-branch-setup-skill
manual_order: 1
parent_id: 2026-05-26-2100-git-workflow-skills
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'g1: Create goal-branch-setup skill'
type: task
updated_at: '2026-06-02T21:33:35Z'
waiting_question: null
---

# Brief

Create the `goal-branch-setup` skill at `.claude/skills/goal-branch-setup/SKILL.md`.

This skill is invoked as the **first action** in the first developing task of a goal. It:
1. Reads `parent_id` from the current task's frontmatter to find the goal ID.
2. Derives the feature branch name: `feature/GOAL-SLUG` (strip the `YYYY-MM-DD-HHMM-` prefix from the goal ID).
3. Creates the branch from `main` on origin if it doesn't exist, or fetches it if it does.
4. Checks out the feature branch in the current worktree so all subsequent commits land there.

# History

Implemented as part of task `2026-05-26-2051-create-git-goal`. Skill file written to `.claude/skills/goal-branch-setup/SKILL.md`.
