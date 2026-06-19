---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-03T16:31:36Z'
depends_on:
- 2026-06-03-1631-featurefix-api
feature_key: null
feature_state: null
id: 2026-06-03-1631-featurefix-worker-decompose
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-03-1631-features-and-fixes
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: featurefix worker decompose
type: goal
updated_at: '2026-06-19T12:17:48Z'
waiting_question: null
---

# Brief

# Pipeline goal: Features&Fixes/S4 — decompose-from-backlog + feature_sync

Pipeline run scaffolded for the Features & Fixes arc. Verbatim request at
`.cronos/pipeline/featurefix-worker-decompose/request.md`.

## Request

# S4 — Worker: process-from-backlog decomposition + feature_state propagation

**Title:** `Features&Fixes/S4 — decompose-from-backlog + feature_sync` · **has_ui:** no · **dep:** S2

- worker.py: `_run_one` (~231-239) → add a third branch: a feature/fix in `feature_state=processing` →
  `_run_feature_decompose(feature_id)`. **Never** fall through to `_run_task`.
- **Decomposition** (note 3): run the feature in `auto` mode with a skill that reads the brief, designs a
  goal+child tasks, POSTs them, and sets `realizes=<feature_id>` on the root goal. On end: ≥1 realizing
  item → `processing→planned`; `STATUS:WAIT`/`BLOCKED` or nothing → `processing→waiting` with the question
  (reuse `_finalize` mapping ~364-392).
- **New `backend/app/feature_sync.py`** (analogue of goal_sync.py, keyed on `realizes`):
  `propagate_to_feature(item_id, store, pool)` called from `_finalize` (after `propagate_to_parent` ~435)
  and the reply path (tasks.py:535). Honor `realizes` only on the directly-linked root goal.
  Item→`waiting` & feature `planned` ⇒ `planned→waiting` (copy question up); resume ⇒ `waiting→planned`;
  item→`done`/`archived` ⇒ **Done-detection** (note 4): all items terminal AND
  `not branch_exists_on_origin(space_dir, "feature/<slug>")` after fetch ⇒ `planned→done` +
  `gh_issue_close` (slug = strip date prefix). Terminal-but-branch-present ⇒ stay `planned`.
- git_ops.py: read-only `branch_exists_on_origin(space_dir, branch)`.

**Scope files:** worker.py, `feature_sync.py` (new), git_ops.py, a decomposition skill (new, or reuse
[[pipeline-scaffold]]/[[create-goal]] with a `realizes` arg).
**Acceptance:** `/process` spawns a run creating a goal+tasks all linked via `realizes`; feature ends
`planned`; a realizing child→`waiting` bubbles the feature to `waiting` (and resuming back to `planned`);
feature→`done` only after the goal is done AND `feature/<slug>` is gone from origin (closes the issue); a
done-but-unmerged goal stays `planned`.

---

## Standing Rules (apply to all phases)

**Branch:** all phase work commits to `feature/features-and-fixes` (from `main` if
missing; never branch from another base, never merge to `main`). Use [[goal-task-commit]]
after review passes.
**Locked design:** apply the parent goal's **Locked decisions** + **Locked design notes 1–7** verbatim
(reuse `Task` with `feature`/`fix`; `feature_state` machine; per-space `FEAT-`/`FIX-`; `realizes` field;
one-way `gh` mirror, MD canonical; git-linked only). No new SQLite tables (index columns only), no Redis,
no HTTP issue API.
**Test gate:** the pipeline's `test`+`review` phases gate — pytest (≥60%) and vitest/`tsc --strict`
must pass before `doc`; commit only on a `pass` verdict. **STATUS/gating** is owned by [[pipeline-gate]].

# History

```
2026-06-05T05:48:01Z [agent]
Paused: Child 'pipeline-reviewer: Features&Fixes/S4 — decompose-from-backlog + feature_sync' ended in waiting state. Completed 5, skipped 0 already-done.
```

```
2026-06-05T12:49:35Z [agent]
All tasks complete. Completed 1, skipped 6 already-done.
```
