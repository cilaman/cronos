---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on:
- 2026-05-25-0706-arc-4-2-git-ops-commit-rebase-push-gh-pr
- 2026-05-25-0707-arc-4-3-autopilot-pickup-module-worker-i
id: 2026-05-25-0708-arc-4-4-post-done-commit-rebase-push-pr
manual_order: 4
parent_id: 2026-05-25-0705-arc-4-autonomous-todo-autopilot
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'arc-4/4: Post-DONE — commit, rebase, push, PR (or PROPOSED_PR.md)'
type: task
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

Implement the post-DONE flow: commit, rebase, push, and create PR.

## Changes
1. New `backend/app/autopilot_pr.py` with `run_post_done_flow(task, space, store) -> PostDoneResult`.
2. Flow: `commit_all` → `rebase_onto` (with conflict handling) → `push_branch` → decide: GitHub PR (`gh_pr_create`) or write `PROPOSED_PR.md` to worktree if no GitHub remote.
3. Persist PR ref on Task model: `pr_url` (GitHub URL) or `proposed_pr_path` (local path).
4. Wire into `_finalize` in `worker.py` — only runs when autopilot is enabled and task reached DONE.


Branch: `feature/arc-4-autopilot`. Test gate: invoke `test-architect` before commit. Commit prefix: `arc-4:`.

# History
