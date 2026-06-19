---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-06T12:53:57Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-06-1253-update-to-features-page
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: Update to Features page
type: goal
updated_at: '2026-06-13T14:30:16Z'
waiting_question: null
---

# Brief

# Update to Features page

Umbrella goal for redesigning the Features board so it behaves like the Tasks
board. The actual work runs as a CC-v1 pipeline subgoal underneath this goal.

All development tasks resolve this root goal for their feature branch
(`feature/<root-slug>` via /goal-branch-setup). The subgoal's terminal doc phase
runs /goal-finalize, which merges the feature branch to main only after the full
pipeline — including the test phase — passes, then deletes the branch.

## Scope (see the subgoal's request.md for the full spec)
- R1: add a feature/fix via the Backlog lane "+" (replace the always-on inline form)
- R2: hide/restore lanes like the Tasks board, persisted to localStorage
- R3: clickable feature cards (open detail)
- R4: toolbar parity + "show all" reset + correct "No features" empty-state copy
- R5: per-space persisted lane layout
- All UI work uses the /frontend-design skill.

# History

```
2026-06-06T14:10:13Z [agent]
All tasks complete. Completed 1, skipped 0 already-done.
```
