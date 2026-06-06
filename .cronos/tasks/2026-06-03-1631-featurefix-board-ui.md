---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-03T16:31:36Z'
depends_on:
- 2026-06-03-1631-featurefix-api
- 2026-06-03-1631-featurefix-worker-decompose
id: 2026-06-03-1631-featurefix-board-ui
manual_order: 0
parent_id: 2026-06-03-1631-features-and-fixes
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: done
title: featurefix board ui
type: goal
updated_at: '2026-06-05T14:18:32Z'
waiting_question: null
---

# Brief

# Pipeline goal: Features&Fixes/S5 — Features board, Tasks rename, cards

Pipeline run scaffolded for the Features & Fixes arc. Verbatim request at
`.cronos/pipeline/featurefix-board-ui/request.md`.

## Request

# S5 — Features board + Tasks rename + cards + composer + realization links

**Title:** `Features&Fixes/S5 — Features board, Tasks rename, cards` · **has_ui:** yes · **dep:** S2, S4

- **types.ts:** `FeatureState` union; `FEATURE_LANES` (5) + `canFeatureTransition()`; extend `TaskType`;
  optional `feature_state/feature_key/issue_number/issue_url/realizes` on `TaskSummary` (39-64) + `Task`
  (86-112); `realized_by?: Array<{id;title;type?;state}>` (server-computed); a `FeatureBoard` interface.
  Keep the two lane systems disjoint (note 6).
- **`pages/FeaturesPage.tsx` + `components/FeaturesBoard.tsx`** (new): parallel lightweight board (note 5)
  reusing `Lane`/`Card`/`DndContext`/sensors over `FEATURE_LANES`. Drag → `useTransitionFeatureState`
  (note 7); illegal transition = no-op. Add `lg:grid-cols-5`. **Skip lane hide/restore**.
- **`Lane.tsx`:** widen `state` to `string`; add `showAdd?: boolean`; Tasks board passes
  `showAdd={state==="backlog"}` (backward-compatible).
- **`Card.tsx`:** `feature`/`fix` `TYPE_BADGE_STYLES` (91-94); `feature_key` chip; issue-link anchor
  cloning the `pr_url` anchor (476-487); a `→ realizes FEAT-NNN` chip cloning the parent-link chip
  (503-521, click-through via `onOpenTask`); on a feature card, a `realized_by` click-through list.
- **Hooks/API:** `hooks/useFeatures.ts` (new) — `useFeatureBoard(spaceId)` keyed `["features",spaceId]`
  `refetchInterval:5000`; `useTransitionFeatureState`, `useCreateFeature`. **Every feature mutation
  invalidates `["features",…]` AND `["board",…]`** (shared Backlog) + `["spaces"]`. `api.ts`: `features`,
  `transitionFeatureState`, `createFeature`.
- **Routing/nav:** router.tsx add `/features` + `/spaces/:spaceId/features`; Sidebar.tsx rename `/board`
  `"Kanban"→"Tasks"`, add `"Features"`.
- **Shared Backlog on the Tasks board** (read-only, single source of truth): an extra click-through
  Backlog column fed by `useFeatureBoard(spaceId).data.backlog`, outside the dnd `SortableContext`;
  click → `/features`. `Board.tsx`'s `TaskState` drag stays untouched.
- **Composer:** reuse `TaskForm` with a Feature/Fix `type` toggle (wired to `useCreateFeature`) on the
  Features Backlog lane header. Use [[frontend-design]] for styling.

**Scope files:** types.ts, `pages/FeaturesPage.tsx` + `components/FeaturesBoard.tsx` + `hooks/useFeatures.ts` (new), Lane.tsx, Card.tsx, api.ts, router.tsx, Sidebar.tsx.
**Acceptance:** `/features` renders 5 lanes; drag hits the feature-state endpoint only; sidebar shows
"Tasks"+"Features" and `/board` still works; feature card shows key + badge + issue link + realizing
items; a `realizes` goal/task shows a `→ realizes FEAT-NNN` chip; a feature/fix can be created from the
Features Backlog; the Tasks board shows the shared read-only Backlog with existing task flows unchanged;
`tsc --strict` clean (no lane-system key mixing).

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
2026-06-05T14:18:32Z [agent]
All tasks complete. Completed 7, skipped 0 already-done.
```
