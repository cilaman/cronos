---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-03T16:31:37Z'
depends_on:
- 2026-06-03-1631-featurefix-github-issues
- 2026-06-03-1631-featurefix-worker-decompose
- 2026-06-03-1631-featurefix-board-ui
feature_key: null
feature_state: null
id: 2026-06-03-1631-featurefix-dashboard-e2e
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
title: featurefix dashboard e2e
type: goal
updated_at: '2026-06-19T12:17:48Z'
waiting_question: null
---

# Brief

# Pipeline goal: Features&Fixes/S6 — dashboard impact + e2e

Pipeline run scaffolded for the Features & Fixes arc. Verbatim request at
`.cronos/pipeline/featurefix-dashboard-e2e/request.md`.

## Request

# S6 — Dashboard & stats impact + end-to-end verification

**Title:** `Features&Fixes/S6 — dashboard impact + e2e` · **has_ui:** yes · **dep:** S3, S4, S5

- **Dashboard** (DashboardPage.tsx): add a minimal **"Features"/"In Backlog"** tile linking to
  `/features`, fed by a **new** `feature_totals: Record<FeatureState,number>` on `SpacesResponse` — do
  **not** widen `totals`/`task_counts`/`Activity.state` (note 6). AI Performance + Test Health untouched.
- **Backend totals:** extend `SpacesResponse`/`SpaceSummary` (api/spaces.py:86-119) with feature-count
  fields (separate from `task_counts`). StatsPage/per-task stats out of scope (no agent runs).
- **E2E pytest** `backend/tests/test_features_e2e.py` (deterministic; TestClient; stub agent
  subprocess + `gh`): capture → `FEAT-001` + MD + mocked issue (number/url) → `/process` →
  decomposition creates goal+tasks with `realizes` → `planned` → drive goal to `done` + simulate
  `feature/<slug>` deleted on origin → feature `done` + issue closed; assert Tasks board excludes
  it, Features board buckets it, `feature_totals` reflects it.

**Scope files:** DashboardPage.tsx, api/spaces.py, types.ts (feature-count fields), `backend/tests/test_features_e2e.py` (new).
**Acceptance:** dashboard shows feature presence (≥ tile + total) without altering the 5 task tiles or
`task_counts`-driven UI (Spaces grid, Sidebar open-count); AI Performance + Test Health render
identically; the e2e passes end-to-end; `tsc --strict` + pytest ≥60% green.

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
2026-06-05T15:12:02Z [agent]
All tasks complete. Completed 7, skipped 0 already-done.
```
