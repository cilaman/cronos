---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-03T09:08:41Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-03-0908-arc-5-c-evolution-tagged-traces-evolve-t
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 3
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: 'Arc 5/C — Evolution: tagged traces + evolve-tools agent'
type: goal
updated_at: '2026-06-19T12:17:48Z'
waiting_question: null
---

# Brief

Tag tool invocations with `adopted_tool_id`. Weekly `evolve-tools` Cronos task per autopilot-enabled space reads per-tool telemetry, proposes revisions for low-success tools, opens a PR (Arc 4 flow). Accepting bumps `local_sha` + sets `evolved=true`, feeding back into B4 merge logic.

| # | Task | depends_on |
|---|------|-----------|
| C1 | tag tool invocations with `adopted_tool_id` | [B1] |
| C2 | per-tool telemetry rollup + API | [C1] |
| C3 | `evolve-tools` agent + scheduled task + PR flow | [C2] |
| C4 | Frontend: per-tool telemetry panel | [C2] |
| C5 | end-to-end test | [C3, C4] |

**First child (C1) depends on Goal B / Task B1 being DONE.**

# History

```
2026-06-03T15:04:47Z [agent]
All tasks complete. Completed 5, skipped 0 already-done.
```
