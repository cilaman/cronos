---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on:
- 2026-05-25-0706-arc-4-1-space-autopilot-schema-yaml-roun
- 2026-05-25-0708-arc-4-4-post-done-commit-rebase-push-pr
id: 2026-05-25-0708-arc-4-5-ui-autopilot-toggle-pr-link-on-c
manual_order: 5
parent_id: 2026-05-25-0705-arc-4-autonomous-todo-autopilot
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'arc-4/5: UI — autopilot toggle + PR link on card'
type: task
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

Surface the autopilot state and PR links in the frontend.

## Changes
1. `frontend/src/types.ts` — add `Space.autopilot: "disabled"|"enabled"|"paused"` and `Task.pr_url?`, `Task.proposed_pr_path?`.
2. Space settings: 3-state segmented control for Autopilot (disabled / enabled / paused). Calls `PATCH /api/spaces/{id}` with `{autopilot: ...}`.
3. Card: "AUTO" pill when space is autopilot-enabled; GitPullRequest icon linking to `pr_url`; FileText icon for proposed PR path with copy-to-clipboard.
4. Detail: show PR row with clickable URL or copy button.


Branch: `feature/arc-4-autopilot`. Test gate: invoke `test-architect` before commit. Commit prefix: `arc-4:`.

# History
