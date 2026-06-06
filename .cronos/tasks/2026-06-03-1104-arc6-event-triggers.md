---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-03T11:04:55Z'
depends_on:
- 2026-06-03-1104-arc6-cron-trigger
id: 2026-06-03-1104-arc6-event-triggers
manual_order: 0
parent_id: 2026-06-03-1104-arc-6-harnesses
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: done
title: arc6 event triggers
type: goal
updated_at: '2026-06-04T07:11:45Z'
waiting_question: null
---

# Brief

# Pipeline goal: 6.6 Event triggers

Pipeline run scaffolded by `/pipeline-scaffold`. Shared branch: `feature/arc-6-harnesses`.
Part of umbrella goal `arc-6-harnesses` (Arc 6 — Harnesses).

## Request

Add the three event Trigger kinds (`backend/app/harnesses/triggers.py`).

- **task-state-change:** emit from the worker finalise/transition path without coupling
  the worker to harnesses (publish an event the harness subsystem subscribes to).
- **webhook:** an external route mapping a payload to a run (document the auth scheme —
  Caddy `_auth` may not apply).
- **file-change:** coexist with `watch_spaces_dir` (main.py:90); reuse its events, don't
  double-watch.
- De-dup/debounce; fan out when multiple harnesses subscribe to one event.

Acceptance: moving a task to DONE fires a subscribed harness; a webhook POST starts its
run; a watched file change triggers its harness; duplicates within the debounce window
fire once.


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
2026-06-04T07:11:45Z [agent]
All tasks complete. Completed 7, skipped 0 already-done.
```
