---
agent_mode: auto
agent_model: default
claude_session_id: 5cf5b8aa-3912-4bc6-9cf3-78ce100bd9f9
created_at: '2026-06-03T16:22:39Z'
depends_on: []
id: 2026-06-03-1622-features-and-fixes
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 3
proposed_pr_path: null
space_id: cronos-development
state: archived
title: Features and Fixes
type: task
updated_at: '2026-06-04T10:28:30Z'
waiting_question: null
---

# Brief

# Features & Fixes — Backlog, Realization, GitHub-Issue Mirror (CC-v1 pipelines)

## Context

A Cronos space holds only **goals/tasks** today (`Task.type ∈ {task, goal, issue}`); there is no way to
capture *business requirements* separately from the *work* that realizes them. This adds two first-class
types — **Feature** and **Fix** — that sit in a **Backlog**, have their own lifecycle and Kanban, are
mirrored one-way to **GitHub Issues**, and are *realized by* one or more goals/tasks. The current board is
renamed **Tasks**; a new **Features** board is added. A requirement can then be captured → decomposed →
tracked to "merged to main" → reflected as an Issue. Delivered like Arc 7
(based-on-cronos-agile-sundae.md): **one root goal + six subgoals, each a CC-v1 pipeline** via
[[pipeline-scaffold]].

**Locked decisions** (confirmed — carry verbatim into every pipeline request):

- **Reuse the `Task` model.** Add `"feature"`/`"fix"` to `TaskType` (models.py:20); reuse storage, the
  SQLite index, the `/api/tasks` substrate, and markdown-frontmatter persistence (storage.py:315-351).
- **Dedicated `feature_state` field** — own 5-state machine
  `backlog→processing→planned→waiting→done`, independent of the `TaskState` machine
  (storage.py:41-57). Feature/fix items keep a *parked* `state=backlog` (never run by
  `_run_task`/`_run_goal`); `feature_state` is the user-facing lifecycle.
- **One-way GitHub Issue mirror, local MD canonical.** Push via `gh` on create/update (extend
  `gh pr create`, git_ops.py:407-463 / autopilot_pr.py:43-137); store `issue_number`/`issue_url`; MD
  fallback when `gh` is unavailable (mirror `.cronos/pull_requests/{id}.md`).
- **Per-space numbering** `FEAT-NNN`/`FIX-NNN`, sequential per space+type; GH issue number stored apart.
- **`realizes` field on a goal/task** → the feature/fix id it realizes (one feature → many);
  reverse lookup `realizing_items(feature_id)`.
- **Git-linked only.** Feature/fix rejected in spaces with no `git_repo_url`.
- **Branch:** `feature/features-and-fixes`, from `main` if missing; no merge to `main` until the arc lands.

## Locked design notes (binding on the implementor pipelines)

1. **`feature_state` never flows through the task board.** `board()` (storage.py:591) and
   `counts_by_space()` bucket by `TaskState`; the parked `state=backlog` would leak feature/fix into the
   Tasks Kanban and double-count `SpaceSummary.task_counts`. **Exclude `type in ("feature","fix")` from
   `board()`/`counts_by_space()`**; add `feature_board()`.
2. **Widen the type guards.** `task_type not in ("task","goal","issue")` at storage.py:249, `create()`,
   `update()` silently coerce `feature`/`fix` → `task` unless updated.
3. **Process-from-backlog cannot use plan mode.** `PLAN_MODE_TOOLS` (agent.py:132) is read-only with no
   item-creation tool. Decomposition runs in **`auto` mode** with a skill (reuse the [[create-goal]]/
   [[pipeline-scaffold]] POST pattern) creating the goal+tasks and setting `realizes=<feature_id>` on the
   root goal — thread `realizes` through `CreateTaskBody`/`store.create`, or `PATCH .../realize` after.
4. **Done-detection reuses the existing merge signal.** Feature → `done` requires BOTH (a) all
   `realizing_items` terminal (`done`/`archived`, non-empty) AND (b) the realizing root goal's
   `feature/<slug>` branch gone from origin — [[goal-finalize]] deletes it only after a `--no-ff`
   merge+push. Add read-only `branch_exists_on_origin(space_dir, branch)` (`git rev-parse --verify`).
   (a)-but-branch-present → stay `planned`. Manual `planned→done` is the escape hatch.
5. **Build a parallel `FeaturesBoard.tsx`, do not parameterize `Board.tsx`** (welded to `TaskState`,
   Board.tsx:23-201). Only shared edit: `Lane.tsx` `state` prop widened to `string` + a `showAdd?: boolean`
   prop (replaces hardcoded `state==="backlog"`).
6. **Two disjoint lane systems.** Keep `LANES`/`TaskState` (types.ts:3-8) and `FEATURE_LANES`/`FeatureState`
   separate; never index a `Record<TaskState,…>` with a `FeatureState`. Dashboard feature counts go in
   **separate** optional fields (`feature_totals`/`feature_counts`), never by widening
   `totals`/`task_counts`/`Activity.state`.
7. **dnd routing.** A Features-board drag calls `useTransitionFeatureState`, never `useTransitionTask`.

## Structure: one root Goal, six subgoal pipelines

| Subgoal | Pipeline slug | has_ui | depends on |
|---|---|---|---|
| S1 | `featurefix-data-model` | no | — |
| S2 | `featurefix-api` | no | S1 |
| S3 | `featurefix-github-issues` | no | S2 |
| S4 | `featurefix-worker-decompose` | no | S2 |
| S5 | `featurefix-board-ui` | yes | S2, S4 |
| S6 | `featurefix-dashboard-e2e` | yes | S3, S4, S5 |

DAG: `S1 → S2 → {S3, S4} → S5 → S6` (S3 and S4 parallel after S2).

**How to put this into Cronos:**
0. Find the git-linked dev space id: `GET /api/spaces` → pick the cronos space (`git_repo_url` set).
1. Create the root goal (`type:goal`, `parent_id:null`): title **`Features & Fixes — backlog, realization, GitHub-issue mirror`**, brief = Context + Locked sections.
2. Per subgoal **in DAG order**, invoke [[pipeline-scaffold]] with `SPACE_ID`, the **Title**, `SLUG_HINT`, and `REQUEST_TEXT` = the subgoal's **Pipeline request** + the **Standing rules**, verbatim. Scaffold returns the goal + 7 phase tasks (scout→…→doc).
3. Reparent each pipeline goal under the root and set `depends_on` per the table (downstream `scout` depends on upstream `doc`; S3 & S4 depend only on S2's `doc`).

## Standing rules (append verbatim to every `REQUEST_TEXT`)

> **Branch:** all phase work commits to `feature/features-and-fixes` (from `main` if
> missing; never branch from another base, never merge to `main`). Use [[goal-task-commit]]
> after review passes.
> **Locked design:** apply the parent goal's **Locked decisions** + **Locked design notes 1–7** verbatim
> (reuse `Task` with `feature`/`fix`; `feature_state` machine; per-space `FEAT-`/`FIX-`; `realizes` field;
> one-way `gh` mirror, MD canonical; git-linked only). No new SQLite tables (index columns only), no Redis,
> no HTTP issue API.
> **Test gate:** the pipeline's `test`+`review` phases gate — pytest (≥60%) and vitest/`tsc --strict`
> must pass before `doc`; commit only on a `pass` verdict. **STATUS/gating** is owned by [[pipeline-gate]].

---

## S1 — Data model: types + `feature_state` machine + numbering + `realizes`
**Title:** `Features&Fixes/S1 — model, feature_state, numbering, realizes` · **has_ui:** no

**Pipeline request:** Extend `Task` model + storage (no API, no UI).
- models.py: add `"feature"`/`"fix"` to `TaskType`; new `FeatureState(str,Enum)` =
  `backlog/processing/planned/waiting/done`. Flat fields on `Task`/`TaskSummary`:
  `feature_state: FeatureState|None`, `feature_key: str|None` (`FEAT-001`), `realizes: str|None`,
  `issue_number: int|None`, `issue_url: str|None`, `proposed_issue_path: str|None` (mirror
  `pr_url`/`proposed_pr_path`).
- storage.py: `parse_file`/`dump_task` serialize the new keys (optional via `meta.get` → old files
  unchanged); **widen the type guards** (note 2). SQLite: add nullable cols
  `feature_state/feature_key/realizes` via the idempotent `ALTER TABLE ADD COLUMN` loop (~418-426) +
  index `idx_tasks_space_realizes(space_id, realizes)`; update **both** insert paths (`_db_upsert`
  ~437-455 and `reload_all` ~520-533).
- **Transition tables** (like storage.py:41-57): `FEATURE_USER_TRANSITIONS` (`backlog→processing`,
  `processing→backlog`, `planned→processing`, `waiting→processing`, `waiting→planned`, `planned→done`,
  `done→backlog`) and `FEATURE_WORKER_TRANSITIONS` (`processing→planned`, `processing→waiting`,
  `planned→waiting`, `waiting→planned`, `planned→done`). New `transition_feature(task_id, new_state,
  allowed)` — do **not** reuse `transition()`.
- `_next_feature_key(space_id, type)` = `max(existing per space+type)+1`, computed **inside `self._lock`**
  in `create()` (no counter file), zero-padded to 3.
- **Exclude feature/fix from `board()`/`counts_by_space()`** (note 1); add `feature_board(space_id)`
  (bucket by `feature_state`) + `realizing_items(feature_id)`.
- `set_realizes(item_id, feature_id|None)` (mirror `set_parent`) with a same-space + target-is-feature/fix
  guard (model on `validate_parent`).

**Scope files:** models.py, storage.py (+ optional `feature_state.py`).
**Acceptance:** creating a `feature` in a git-linked space → `feature_key=FEAT-001`,
`feature_state=backlog`, `state=backlog`, parseable MD + SQLite row; FEAT/FIX counters independent per
space; existing MD files load unchanged after `reload_all`; feature/fix excluded from `board()`; the
transition table is enforced; `set_realizes` rejects cross-space/non-feature targets.

## S2 — Feature/Fix API + realization + `process` action
**Title:** `Features&Fixes/S2 — features API + realize + process` · **has_ui:** no · **dep:** S1

**Pipeline request:** New `backend/app/api/features.py` (`prefix="/api/features"`), registered like the
tasks router. Do **not** overload `api/tasks.py`.
- `POST /api/features` `{space_id,title,brief,type:"feature"|"fix",priority}` — validate git-linked
  (else 400, where `space_store` is available, tasks.py:350-352); allocate key; write MD; fire S3 mirror.
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

## S3 — GitHub Issue one-way mirror
**Title:** `Features&Fixes/S3 — GitHub issue mirror (one-way)` · **has_ui:** no · **dep:** S2

**Pipeline request:** New `backend/app/git_issues.py`, like `gh_pr_create` (git_ops.py:417-464) + the MD fallback (autopilot_pr.py:116-137).
- `gh_issue_upsert(space_dir, *, title, body, labels, issue_number) -> (int|None, str|None)`:
  `issue_number is None` → `gh issue create --label feature|fix` (parse number+url); else
  `gh issue edit <n>`. Reuse the `shutil.which("gh")` guard, `create_subprocess_exec`, 60s timeout,
  graceful-None, and `detect_github_remote()`.
- `gh_issue_close(space_dir, issue_number)` for feature→done.
- Fallback (no remote / `gh` None): write `.cronos/issues/{feature_id}.md` + persist `proposed_issue_path`.
- `store.set_issue_refs(task_id, *, issue_number, issue_url, proposed_issue_path)` (mirror `set_pr_refs`).
- **Fires** after the local MD write succeeds, on create + any title/brief/feature_state change. Swallow
  all `gh` exceptions at the call site (worker.py:430-431 pattern); never block the response.

**Scope files:** `git_issues.py` (new), storage.py (`set_issue_refs`), `api/features.py` (call sites).
**Acceptance:** create with `gh` → number/url persisted, label applied; update → same issue edited (no
dup); `gh` absent / non-GitHub → `.cronos/issues/{id}.md` + `proposed_issue_path`, no error; a stale
`issue_number` degrades to MD fallback without crashing.

## S4 — Worker: process-from-backlog decomposition + `feature_state` propagation
**Title:** `Features&Fixes/S4 — decompose-from-backlog + feature_sync` · **has_ui:** no · **dep:** S2

**Pipeline request:**
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

## S5 — Features board + Tasks rename + cards + composer + realization links
**Title:** `Features&Fixes/S5 — Features board, Tasks rename, cards` · **has_ui:** yes · **dep:** S2, S4

**Pipeline request:**
- **types.ts:** `FeatureState` union; `FEATURE_LANES` (5) + `canFeatureTransition()`; extend `TaskType`;
  optional `feature_state/feature_key/issue_number/issue_url/realizes` on `TaskSummary` (39-64) + `Task`
  (86-112); `realized_by?: Array<{id;title;type?;state}>` (server-computed); a `FeatureBoard` interface.
  Keep the two lane systems disjoint (note 6).
- **`pages/FeaturesPage.tsx` + `components/FeaturesBoard.tsx`** (new): parallel lightweight board (note 5)
  reusing `Lane`/`Card`/`DndContext`/sensors over `FEATURE_LANES`. Drag → `useTransitionFeatureState`
  (note 7); illegal transition = no-op. Add `lg:grid-cols-5`. **Skip lane hide/restore** (avoids the
  `KNOWN_LANE_STATES` landmine, storage.ts).
- **`Lane.tsx`:** widen `state` to `string`; add `showAdd?: boolean`; Tasks board passes
  `showAdd={state==="backlog"}` (backward-compatible).
- **`Card.tsx`:** `feature`/`fix` `TYPE_BADGE_STYLES` (91-94); `feature_key` chip; issue-link anchor
  cloning the `pr_url` anchor (476-487); a `→ realizes FEAT-NNN` chip cloning the parent-link chip
  (503-521, click-through via `onOpenTask`); on a feature card, a `realized_by` click-through list (idiom
  from `children_progress`, 524-543).
- **Hooks/API:** `hooks/useFeatures.ts` (new) — `useFeatureBoard(spaceId)` keyed `["features",spaceId]`
  `refetchInterval:5000`; `useTransitionFeatureState`, `useCreateFeature`. **Every feature mutation
  invalidates `["features",…]` AND `["board",…]`** (shared Backlog) + `["spaces"]`. `api.ts`: `features`,
  `transitionFeatureState`, `createFeature`.
- **Routing/nav:** router.tsx add `/features` + `/spaces/:spaceId/features`; Sidebar.tsx rename `/board`
  `"Kanban"→"Tasks"`, add `"Features"`.
- **Shared Backlog on the Tasks board** (read-only, single source of truth): an extra click-through
  Backlog column fed by `useFeatureBoard(spaceId).data.backlog`, outside the dnd `SortableContext` (or
  `dragDisabled` Cards); click → `/features`. `Board.tsx`'s `TaskState` drag stays untouched. **Leave
  `ViewEditor` `TYPE_OPTS` unchanged**; confirm `/api/tasks` board excludes feature/fix.
- **Composer:** reuse `TaskForm` with a Feature/Fix `type` toggle (wired to `useCreateFeature`) on the
  Features Backlog lane header. Use [[frontend-design]] for styling.

**Scope files:** types.ts, `pages/FeaturesPage.tsx` + `components/FeaturesBoard.tsx` + `hooks/useFeatures.ts` (new), Lane.tsx, Card.tsx, api.ts, router.tsx, Sidebar.tsx.
**Acceptance:** `/features` renders 5 lanes; drag hits the feature-state endpoint only; sidebar shows
"Tasks"+"Features" and `/board` still works; feature card shows key + badge + issue link + realizing
items; a `realizes` goal/task shows a `→ realizes FEAT-NNN` chip; a feature/fix can be created from the
Features Backlog; the Tasks board shows the shared read-only Backlog with existing task flows unchanged;
`tsc --strict` clean (no lane-system key mixing).

## S6 — Dashboard & stats impact + end-to-end verification
**Title:** `Features&Fixes/S6 — dashboard impact + e2e` · **has_ui:** yes · **dep:** S3, S4, S5

**Pipeline request:**
- **Dashboard** (DashboardPage.tsx): add a minimal **"Features"/"In Backlog"** tile linking to
  `/features`, fed by a **new** `feature_totals: Record<FeatureState,number>` on `SpacesResponse` — do
  **not** widen `totals`/`task_counts`/`Activity.state` (note 6). AI Performance + Test Health untouched.
  Per-space badges + feature activity events are **optional stretch**; guaranteed = tile + total.
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

## After all six land — manual verification

`docker compose up --build` in a GitHub-linked space, then exercise the full path from the UI: create a
**Feature** (→ `FEAT-001` + GH Issue) → **Process** (→ **Planned**, realizing goal+tasks chipped) →
finalize the goal ([[goal-finalize]] merges + deletes `feature/<slug>` → feature **Done**, Issue closed).
Confirm the **Tasks** board's shared read-only **Backlog** and the Dashboard tile. Then manual-merge.

## Files of record

**New files:** `app/api/features.py`, `app/git_issues.py`, `app/feature_sync.py`, a decomposition skill,
`tests/test_features_e2e.py`; `pages/FeaturesPage.tsx`, `components/FeaturesBoard.tsx`,
`hooks/useFeatures.ts`. **Modified:** per subgoal Scope files (chiefly `models.py`+`storage.py`,
`worker.py`+`git_ops.py`, `types.ts`/`Lane.tsx`/`Card.tsx`/`api.ts`/`router.tsx`/`Sidebar.tsx`,
`DashboardPage.tsx`+`api/spaces.py`).

**Reused (do not rebuild):** atomic frontmatter writes (storage.py:315-351); idempotent
`ALTER TABLE ADD COLUMN` migration; `gh` subprocess + `shutil.which` guard + MD fallback
(git_ops.py:417-464, autopilot_pr.py:116-137); the `feature/<slug>` lifecycle
([[goal-branch-setup]]/[[goal-finalize]]) as the Done signal; `goal_sync` propagation; the worker event
bus (`enqueue`/`on_idle`); `Lane`/`Card`/dnd-kit; `TaskForm`; the 7-phase [[pipeline-scaffold]] flow.

# History

```
2026-06-03T16:33:29Z [agent] run=0 model=claude-sonnet-4-6 mode=auto
I'll set up the Cronos board for this arc: get the space ID, create the root goal, then scaffold the 6 subgoal pipelines.

The space ID is `cronos-development`. Let me read the pipeline-scaffold skill to understand how to use it properly.

Let me check the tasks API for patching parent_id and depends_on.

Let me check the goal-task-commit and goal-branch-setup skills to understand branch naming.

Now I have everything I need. I'll write one Python script to create the root goal, scaffold all 6 subgoals with correct deps and custom doc briefs, then reparent everything.

All 6 subgoals scaffolded successfully. Let me verify the board state and pipeline files.

All checks pass. Now I'll save the arc board setup to memory and finalize.

Memory saved. Now I'll finalize the task.

## Step 1 — Verify completion

The task created:
- Root goal `2026-06-03-1631-features-and-fixes` (branch `feature/features-and-fixes`)
- 6 CC-v1 pipeline subgoals (S1–S6) scaffolded with 7 phase tasks each
- All subgoals reparented under root
- Cross-goal DAG deps wired on scout tasks per spec
- All pipeline-state.json + request.md + phases-log.jsonl files initialized
- Memory saved to space-root memory

All objectives complete.

## Step 3 — Handle git

Only `.cronos/test-coverage.md` is tracked in git and that's unrelated to this task (runtime data). The pipeline state files are untracked runtime data — no code changes were made. Skipping commit.

## Step 4 — Write memory

Memory was already written in the previous step (space-root `project_arc_features_fixes_board_setup.md` + MEMORY.md updated).

MEMORY[fact]: Cronos board for Features & Fixes arc fully wired — root goal `2026-06-03-1631-features-and-fixes` (branch: `feature/features-and-fixes`) + 6 CC-v1 pipeline subgoals S1–S6 under it, cross-goal DAG deps on scout tasks, all pipeline-state.json initialized. All doc tasks use /goal-task-commit (not /goal-finalize); merge to main is manual after all 6 pass.

STATUS: DONE
```
