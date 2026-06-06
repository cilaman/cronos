---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on:
- 2026-05-25-1342-arc-9-1-propagate-child-state-to-parent
id: 2026-05-25-1343-arc-9-6-route-goal-level-messages-to-act
manual_order: 6
parent_id: 2026-05-25-1341-arc-9-goal-processing-ux-sync
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'arc-9/6: Route goal-level messages to active child or next-up'
type: task
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

When a user replies to a goal, route the message to the currently active child or the next-up backlog child.

## Changes
1. Reply endpoint: when `task.type=="goal"`: if child running → forward reply to child; else any BACKLOG child → append to `goal.pending_messages`; else → standard reply (history only).
2. Response includes `routed_to: {task_id, title} | null`.
3. Ensure `pending_messages: list[str]` round-trips correctly via frontmatter.
4. Worker drains `pending_messages` into `goal_context` on `_run_goal` start.
5. Frontend: compose hint showing target child; toast on send confirming routing.


Branch: `feature/arc-9-goal-ux`. Test gate: invoke `test-architect` before commit. Commit prefix: `arc-9:`.

# History
