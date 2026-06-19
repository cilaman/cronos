---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-03T16:31:36Z'
depends_on:
- 2026-06-03-1631-featurefix-data-model
feature_key: null
feature_state: null
id: 2026-06-03-1631-featurefix-api
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
title: featurefix api
type: goal
updated_at: '2026-06-19T12:17:48Z'
waiting_question: null
---

# Brief

# Pipeline goal: Features&Fixes/S2 — features API + realize + process

Pipeline run scaffolded for the Features & Fixes arc. Verbatim request at
`.cronos/pipeline/featurefix-api/request.md`.

## Request

# S2 — Feature/Fix API + realization + process action

**Title:** `Features&Fixes/S2 — features API + realize + process` · **has_ui:** no · **dep:** S1

New `backend/app/api/features.py` (`prefix="/api/features"`), registered like the tasks router.
Do **not** overload `api/tasks.py`.
- `POST /api/features` `{space_id,title,brief,type:"feature"|"fix",priority}` — validate git-linked
  (else 400); allocate key; write MD; fire S3 mirror.
- `GET /api/features?space_id=` → `FeatureBoard` (5 lanes via `feature_board()`).
- `GET /api/features/{id}` → feature + `realizing_items`.
- `PATCH /api/features/{id}/feature-state` → `transition_feature(allowed=FEATURE_USER_TRANSITIONS)`; re-fire mirror.
- `PATCH /api/features/{id}` → title/brief edit; re-fire mirror.
- `PATCH /api/features/{id}/realize` → `set_realizes` link/unlink.
- `POST /api/features/{id}/process` → `processing` + `enqueue` decomposition (S4 trigger).
- Thread `realizes` into `CreateTaskBody`/`store.create`, or rely on `/realize` — pick one.

**Scope files:** `api/features.py` (new), app factory (router reg), models.py (`FeatureBoard`/schemas).
**Acceptance:** create in git-linked → numbered feature + MD; non-git → 400; `GET` → `FeatureBoard` and
Tasks board still excludes features; `/feature-state` enforces table (illegal → 409); `/realize`
sets/clears and `GET /{id}` lists items; `/process` → `processing` and worker picks it up.

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
2026-06-04T12:29:35Z [agent]
Paused: Cannot start task: unmet dependencies: 2026-06-03-1631-pipeline-doc-sync-features-fixes-s1-mode Completed 0, skipped 0 already-done.
```

```
2026-06-04T18:41:35Z [agent]
All tasks complete. Completed 7, skipped 0 already-done.
```
