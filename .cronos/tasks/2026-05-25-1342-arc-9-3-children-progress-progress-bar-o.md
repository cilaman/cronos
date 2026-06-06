---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on: []
id: 2026-05-25-1342-arc-9-3-children-progress-progress-bar-o
manual_order: 3
parent_id: 2026-05-25-1341-arc-9-goal-processing-ux-sync
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'arc-9/3: children_progress + progress bar on goal cards'
type: task
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

Show a progress bar and child counts on goal cards.

## Changes
1. `TaskSummary.children_progress: {done: int, total: int, waiting: int} | None` (goals only; null for tasks).
2. Compute in board endpoint by filtering tasks by `parent_id` for each goal.
3. Card render for goals: show `3 / 8` fraction + slim progress bar (accent for done, amber for waiting).
4. Detail row: show progress fraction + waiting count.


Branch: `feature/arc-9-goal-ux`. Test gate: invoke `test-architect` before commit. Commit prefix: `arc-9:`.

# History
