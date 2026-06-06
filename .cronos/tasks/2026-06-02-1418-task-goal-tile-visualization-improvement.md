---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-02T14:18:52Z'
depends_on: []
id: 2026-06-02-1418-task-goal-tile-visualization-improvement
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: done
title: Task / Goal tile visualization improvements
type: goal
updated_at: '2026-06-02T15:18:59Z'
waiting_question: null
---

# Brief

Improve the visual design of goal and task tiles in the kanban board to address several usability problems:

1. **Status indicators are too small** – the 1.5px status dot is hard to read and green (active) vs blue (done) are hard to distinguish at that size.
2. **Child items are hard to read** – tasks shown inside an expanded goal card use tiny text and minimal spacing.
3. **No visual distinction between subtasks and subgoals** – the expanded child list mixes tasks and goals without differentiating them visually.
4. **No inline tree expansion for nested goals** – when a goal has sub-goals as children, those sub-goals cannot be further expanded inline; the hierarchy is flat.

This goal tracks all sub-goals and tasks needed to deliver these improvements in `frontend/src/components/Card.tsx` and related files.

# History

```
2026-06-02T15:18:59Z [agent]
All tasks complete. Completed 4, skipped 0 already-done.
```
