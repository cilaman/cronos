---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-03T11:04:55Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-03-1104-arc6-harness-model
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
title: arc6 harness model
type: goal
updated_at: '2026-06-19T12:17:48Z'
waiting_question: null
---

# Brief

# Pipeline goal: 6.1 Harness model YAML persistence CRUD API

Pipeline run scaffolded by `/pipeline-scaffold`. Shared branch: `feature/arc-6-harnesses`.
Part of umbrella goal `arc-6-harnesses` (Arc 6 — Harnesses).

## Request

Build the harness data layer. New package `backend/app/harnesses/` (`model.py`, `store.py`)
with a Pydantic model + YAML round-trip.

- `HarnessNode`: `id`, `type` (`agent|trigger|decision|wait|aggregator`), `position {x,y}`,
  `ports` (named in/out socket ids), `data: dict` (type-specific config — e.g. an agent
  node's `agent_ref` + `prompt_template` + `variable_bindings`), `label`. Include
  position/ports/data from the start so frontend subgoals extend additively, never revise.
- `HarnessEdge`: `id`, `source` (node+port), `target` (node+port), optional `condition` label.
  `Harness`: `name`, `description`, `nodes[]`, `edges[]`, `variables: dict`, `version`.
- Persist at `{space}/.cronos/harnesses/<name>.yml` (source of truth); atomic write
  (tmpfile + `os.replace`) per space_storage.py. Path-safe filename; name uniqueness.
- Validator: graph is a DAG (no cycles), edges reference existing nodes/ports, only
  allowed types. **Adapt** (do not reuse verbatim) the cycle logic in storage.py
  (`_dep_cycle_path` / `validate_depends_on`) to node/edge structures.
- CRUD `backend/app/api/harnesses.py` wired into main.py, following DI+auth in
  api/tasks.py: `GET/POST/PUT/DELETE /api/spaces/{id}/harnesses[/<name>]`.
  Invalid graph ⇒ 422. Resolve YAML round-trip fidelity vs editor as second writer
  (last-writer-wins) and concurrent CRUD vs a live run.

Acceptance: POST a 3-node/2-edge harness → GET round-trips losslessly; a cycle or
dangling edge → 422; on-disk YAML matches the API payload.


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
2026-06-03T17:34:17Z [agent]
Paused: Child 'pipeline-reviewer: 6.1 Harness model YAML persistence CRUD API' ended in waiting state. Completed 5, skipped 0 already-done.
```

```
2026-06-03T19:10:40Z [agent]
All tasks complete. Completed 1, skipped 6 already-done.
```

```
2026-06-03T19:13:30Z [user]
Set status to done
```
