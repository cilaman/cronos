---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-03T11:04:55Z'
depends_on:
- 2026-06-03-1104-arc6-control-flow
id: 2026-06-03-1104-arc6-run-lifecycle
manual_order: 0
parent_id: 2026-06-03-1104-arc-6-harnesses
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: done
title: arc6 run lifecycle
type: goal
updated_at: '2026-06-04T04:56:48Z'
waiting_question: null
---

# Brief

# Pipeline goal: 6.4 Run lifecycle status trigger API SSE

Pipeline run scaffolded by `/pipeline-scaffold`. Shared branch: `feature/arc-6-harnesses`.
Part of umbrella goal `arc-6-harnesses` (Arc 6 — Harnesses).

## Request

Expose the runtime over HTTP and round out lifecycle in `backend/app/api/harnesses.py`.

- `POST .../harnesses/<name>/run` — manual trigger, returns `run_id`.
- `GET  .../harnesses/<name>/runs` — run-history list.
- `GET  .../harness-runs/<run_id>` — status: per-node state, chosen edges, child ids,
  timings (snapshot; avoid N+1 trace reads).
- `POST .../harness-runs/<run_id>/cancel` — stop the current child (`stop_current` /
  `_current_cancel`), abort the interpreter, mark the run failed atomically. `DELETE` a
  harness with active runs handled cleanly.
- **Run-level SSE** `GET .../harness-runs/<run_id>/stream` emitting node/edge transitions,
  built on `subscribe`/`sse_events`/`_run_buffer` replay in worker.py (late joiners get
  the backlog).

Acceptance: POST /run executes; GET status reflects live per-node state; cancel stops a
mid-flight run; SSE replays prior transitions to a late subscriber.


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
2026-06-03T22:31:37Z [agent]
Paused: Child 'pipeline-reviewer: 6.4 Run lifecycle status trigger API SSE' ended in waiting state. Completed 5, skipped 0 already-done.
```

```
2026-06-04T04:49:23Z [agent]
All tasks complete. Completed 1, skipped 6 already-done.
```

```
2026-06-04T04:56:48Z [agent]
All tasks complete. Completed 0, skipped 7 already-done.
```
