---
agent_mode: plan
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on: []
id: 2026-05-25-1341-arc-9-goal-processing-ux-sync
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: Arc 9 — Goal Processing UX & Sync
type: goal
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

Fix goal/child state desync, add live processing feedback, make goals first-class on the board, and add dependency graph visualization. Six tasks shipping on `feature/arc-9-goal-ux`.

## Child Tasks
1. arc-9/1 — Propagate child state to parent goal + auto-resume
2. arc-9/2 — Live processing pulse on currently-running card
3. arc-9/3 — children_progress + progress bar on goal cards
4. arc-9/4 — Collapsible goal card with inline children list (depends on arc-9/3)
5. arc-9/5 — Dependency DAG visualization in goal detail
6. arc-9/6 — Route goal-level messages to active child or next-up (depends on arc-9/1)

# History
