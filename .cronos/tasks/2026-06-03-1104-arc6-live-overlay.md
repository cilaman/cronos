---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-03T11:04:56Z'
depends_on:
- 2026-06-03-1104-arc6-visual-editor
feature_key: null
feature_state: null
id: 2026-06-03-1104-arc6-live-overlay
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-03-1104-arc-6-harnesses
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: arc6 live overlay
type: goal
updated_at: '2026-06-19T12:17:48Z'
waiting_question: null
---

# Brief

# Pipeline goal: 6.8 Live execution overlay run history

Pipeline run scaffolded by `/pipeline-scaffold`. Shared branch: `feature/arc-6-harnesses`.
Part of umbrella goal `arc-6-harnesses` (Arc 6 — Harnesses).

## Request

Add the live-execution overlay — the differentiator — to the editor.

- **Reuse SSE, not polling/websockets.** Subscribe to the 6.4 run-level stream for
  node/edge transitions and to each Agent child's `/api/tasks/{id}/stream` (`_run_buffer`
  replay covers late joiners).
- Map run state to React Flow styling: **active node pulses, completed edges thicken,
  failed paths desaturate.** Click a node → open its child task in ConversationStream.tsx
  (child id per node from 6.4 status).
- **Run history:** list past runs (from 6.4); open a finished run to replay final states +
  traces. Empty: "No runs yet."
- New `frontend/src/components/harness/RunOverlay.tsx` + `RunHistory.tsx`; handle many
  simultaneous streams without jank.

Acceptance: trigger from the editor and watch the overlay animate per node; click a running
node → its live log; open a past run → final state; no-runs harness shows the empty state.


## Child tasks (one per CC-v1 phase)

1. scout    — pipeline-scout    (research)
2. analysis — pipeline-analyst  (analysis)
3. design   — pipeline-architect(design)
4. impl     — pipeline-implementor (implementation; may fan out per iteration)
5. test     — tester            (test)
6. review   — pipeline-reviewer (review; may loop on verdict=needs_fix)
7. doc      — pipeline-doc-sync (doc; commit-only — no merge to main)

Each phase task ends by invoking `/pipeline-gate` which closes the gate from
the artifact's YAML header — no prose parsing. The doc task commits via
`/goal-task-commit` (not /goal-finalize); the final merge happens in the Arc 6
integration task.

# History

```
2026-06-04T09:07:14Z [agent]
Paused: Child 'pipeline-reviewer: 6.8 Live execution overlay run history' ended in waiting state. Completed 5, skipped 0 already-done.
```

```
2026-06-04T09:24:48Z [agent]
Paused: Child 'pipeline-reviewer: 6.8 Live execution overlay run history' is in active state and needs attention. Completed 0, skipped 5 already-done.
```

```
2026-06-04T09:37:46Z [agent]
All tasks complete. Completed 1, skipped 6 already-done.
```
