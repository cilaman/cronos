---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on:
- 2026-05-25-1342-arc-9-3-children-progress-progress-bar-o
id: 2026-05-25-1343-arc-9-4-collapsible-goal-card-with-inlin
manual_order: 4
parent_id: 2026-05-25-1341-arc-9-goal-processing-ux-sync
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'arc-9/4: Collapsible goal card with inline children list on board'
type: task
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

Allow goal cards on the board to expand inline to show their child tasks.

## Changes
1. `Card.tsx`: chevron `▸ N children` that toggles expand state.
2. Expanded view: vertical mini-list of children with state dot, title, age, priority chip. Each child opens in Detail on click.
3. Persist expanded state per-space via `cronos:board:goal-expanded:{spaceId}` in localStorage.
4. Toolbar: "Hide expanded goal's children from lanes" switch — when on, children nested under an expanded goal are hidden from their own lane column.


Branch: `feature/arc-9-goal-ux`. Test gate: invoke `test-architect` before commit. Commit prefix: `arc-9:`.

# History
