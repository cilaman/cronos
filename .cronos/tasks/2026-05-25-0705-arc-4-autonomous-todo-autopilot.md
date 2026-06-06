---
agent_mode: plan
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on: []
id: 2026-05-25-0705-arc-4-autonomous-todo-autopilot
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: Arc 4 — Autonomous TODO Autopilot
type: goal
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

When a space's worker queue drains, autopilot picks the next eligible backlog task and runs it. After every task that hits DONE in an autopilot-enabled space, Cronos commits, rebases on the base branch, pushes, and opens a PR.

## Child Tasks
1. arc-4/1 — Space.autopilot schema + yaml round-trip
2. arc-4/2 — git_ops helpers (commit, rebase, push, gh-pr)
3. arc-4/3 — Autopilot pickup module + worker idle hook (depends on 1)
4. arc-4/4 — Post-DONE commit, rebase, push, PR flow (depends on 2 & 3)
5. arc-4/5 — UI autopilot toggle + PR link on card (depends on 1 & 4)

# History
