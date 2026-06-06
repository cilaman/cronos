---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on: []
id: 2026-05-26-1238-investigate-waiting-tasks
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: Investigate waiting tasks
type: task
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

Investigate why tasks were ending in WAITING state unexpectedly.

## Root cause
The `_upgrade_instructions()` function instructed agents to write `**STATUS: DONE**` with markdown bold markers, but the worker regex only matched plain `STATUS: DONE`.

## Fix applied
Updated `parse_status` regex in `backend/app/agent.py` to recognize both `STATUS: DONE` and `**STATUS: DONE**`. Fixed upgrade instructions to no longer use bold. Added tests. Upgraded the app.

# History
