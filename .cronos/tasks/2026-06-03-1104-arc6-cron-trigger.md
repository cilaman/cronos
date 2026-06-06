---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-03T11:04:55Z'
depends_on:
- 2026-06-03-1104-arc6-run-lifecycle
id: 2026-06-03-1104-arc6-cron-trigger
manual_order: 0
parent_id: 2026-06-03-1104-arc-6-harnesses
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: done
title: arc6 cron trigger
type: goal
updated_at: '2026-06-04T05:59:03Z'
waiting_question: null
---

# Brief

# Pipeline goal: 6.5 Cron trigger

Pipeline run scaffolded by `/pipeline-scaffold`. Shared branch: `feature/arc-6-harnesses`.
Part of umbrella goal `arc-6-harnesses` (Arc 6 — Harnesses).

## Request

Add a cron scheduler: one `asyncio.create_task(cron_loop, …)` in main.py `lifespan`
alongside the existing `watcher`/`archiver`/`memory_pruner` loops.

- Re-read the canonical harness list each tick (no per-harness timers; no
  double-registration on `watch_spaces_dir` reload). A `cron` Trigger carries its
  expression in `data`.
- **Overlap guard:** skip a tick if the harness already has an `active` run (a set check;
  single-process asyncio, no lock).
- Parse cron expr + timezone correctly. Missed ticks across restart are not back-filled —
  document this.

Acceptance: a cron Trigger fires at the scheduled time (shortened interval in tests);
a tick during an active run is skipped.


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
2026-06-04T05:59:03Z [agent]
All tasks complete. Completed 7, skipped 0 already-done.
```
