---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-03T16:31:36Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-03-1631-features-and-fixes
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
title: features and fixes
type: goal
updated_at: '2026-06-19T12:17:48Z'
waiting_question: null
---

# Brief

# Features & Fixes — backlog, realization, GitHub-issue mirror

Umbrella arc adding Feature and Fix types to Cronos with a dedicated Backlog,
lifecycle, GitHub Issue one-way mirror, worker decomposition, Features board UI,
and dashboard integration.

## Context

A Cronos space holds only goals/tasks today; there is no way to capture *business requirements*
separately from the *work* that realizes them. This adds two first-class types — **Feature** and
**Fix** — that sit in a **Backlog**, have their own lifecycle and Kanban, are mirrored one-way to
**GitHub Issues**, and are *realized by* one or more goals/tasks.

## Locked decisions

- **Reuse the `Task` model.** Add `"feature"`/`"fix"` to `TaskType` (models.py:20); reuse storage,
  the SQLite index, and markdown-frontmatter persistence (storage.py:315-351).
- **Dedicated `feature_state` field** — own 5-state machine
  `backlog→processing→planned→waiting→done`, independent of `TaskState`.
  Feature/fix items keep a parked `state=backlog` (never run by `_run_task`/`_run_goal`).
- **One-way GitHub Issue mirror, local MD canonical.** Push via `gh` on create/update;
  store `issue_number`/`issue_url`; MD fallback when `gh` unavailable.
- **Per-space numbering** `FEAT-NNN`/`FIX-NNN`, sequential per space+type.
- **`realizes` field on a goal/task** → the feature/fix id it realizes.
- **Git-linked only.** Feature/fix rejected in spaces with no `git_repo_url`.

## Locked design notes (binding on implementors)

1. **`feature_state` never flows through the task board.** Exclude `type in ("feature","fix")` from
   `board()`/`counts_by_space()`; add `feature_board()`.
2. **Widen type guards.** `task_type not in ("task","goal","issue")` at storage.py:249 must include "feature"/"fix".
3. **Process-from-backlog cannot use plan mode.** Decomposition runs in `auto` mode.
4. **Done-detection reuses merge signal.** Feature→`done` requires all realizing_items terminal AND
   `feature/<slug>` gone from origin. Manual `planned→done` is the escape hatch.
5. **Build a parallel `FeaturesBoard.tsx`**, do not parameterize `Board.tsx`.
6. **Two disjoint lane systems.** `LANES`/`TaskState` and `FEATURE_LANES`/`FeatureState` separate.
7. **dnd routing.** Features-board drag calls `useTransitionFeatureState`, never `useTransitionTask`.

## DAG

| Subgoal | Slug | dep |
|---|---|---|
| S1 | featurefix-data-model | — |
| S2 | featurefix-api | S1 |
| S3 | featurefix-github-issues | S2 |
| S4 | featurefix-worker-decompose | S2 |
| S5 | featurefix-board-ui | S2, S4 |
| S6 | featurefix-dashboard-e2e | S3, S4, S5 |

Branch: `feature/features-and-fixes` (shared by all subgoals). Manual merge to `main` after all 6 pass.

# History

```
2026-06-04T12:29:35Z [agent]
Paused: Sub-goal 'featurefix api' ended in waiting state. Completed 0, skipped 0 already-done.
```

```
2026-06-04T19:39:57Z [agent]
Paused: Sub-goal 'featurefix github issues' ended in waiting state. Completed 2, skipped 0 already-done.
```

```
2026-06-04T21:57:36Z [agent]
Paused: Child 'featurefix github issues' is in active state and needs attention. Completed 0, skipped 2 already-done.
```

```
2026-06-05T04:11:48Z [agent]
Paused: Child 'featurefix github issues' is in active state and needs attention. Completed 0, skipped 2 already-done.
```

```
2026-06-05T05:48:01Z [agent]
Paused: Sub-goal 'featurefix worker decompose' ended in waiting state. Completed 0, skipped 3 already-done.
```

```
2026-06-05T12:12:05Z [agent]
Paused: Child 'featurefix worker decompose' is in active state and needs attention. Completed 0, skipped 3 already-done.
```

```
2026-06-05T12:45:17Z [agent]
Paused: Child 'featurefix worker decompose' is in active state and needs attention. Completed 0, skipped 3 already-done.
```

```
2026-06-05T15:12:02Z [agent]
All tasks complete. Completed 2, skipped 4 already-done.
```
