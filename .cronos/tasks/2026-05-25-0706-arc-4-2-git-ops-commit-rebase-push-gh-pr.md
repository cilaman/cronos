---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on: []
id: 2026-05-25-0706-arc-4-2-git-ops-commit-rebase-push-gh-pr
manual_order: 2
parent_id: 2026-05-25-0705-arc-4-autonomous-todo-autopilot
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'arc-4/2: git_ops — commit, rebase, push, gh-pr helpers'
type: task
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

Add Git and GitHub helper functions to `backend/app/git_ops.py`.

## Functions to add
- `has_changes(worktree) -> bool`
- `commit_all(worktree, message) -> str | None`
- `fetch_origin(space_dir)`
- `detect_default_branch(space_dir, hint=None) -> str`
- `RebaseResult` dataclass and `rebase_onto(worktree, onto) -> RebaseResult`
- `push_branch(worktree, branch, *, force_with_lease=False)`
- `detect_github_remote(space_dir) -> str | None`
- `gh_pr_create(worktree, *, title, body, base, head) -> str | None`

All functions must handle errors gracefully and use the existing async subprocess pattern.


Branch: `feature/arc-4-autopilot`. Test gate: invoke `test-architect` before commit. Commit prefix: `arc-4:`.

# History
