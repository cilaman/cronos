---
cc_version: '1.0'
agent: pipeline-analyst
slug: featurefix-dashboard-e2e
phase: analysis
status: done
confidence: 0.92
inputs_used:
- memory:project_dashboard_design
- memory:project_s2_api_impl
- memory:project_s5_board_ui_impl
- memory:project_arc_features_fixes_board_setup
- memory:project_s1_data_model_impl
- .cronos/pipeline/featurefix-dashboard-e2e/scout-report-featurefix-dashboard-e2e.md
- backend/app/models.py
- backend/app/api/spaces.py
- frontend/src/pages/DashboardPage.tsx
- frontend/src/types.ts
- backend/tests/test_feature_decompose_e2e.py
outputs_produced:
- .cronos/pipeline/featurefix-dashboard-e2e/analysis-report-featurefix-dashboard-e2e.md
blockers: []
next_consumer: design
request: "# S6 — Dashboard & stats impact + end-to-end verification\n\n**Title:**\
  \ `Features&Fixes/S6 — dashboard impact + e2e` · **has_ui:** yes · **dep:** S3,\
  \ S4, S5\n\n- **Dashboard** (DashboardPage.tsx): add a minimal **\"Features\"/\"\
  In Backlog\"** tile linking to\n  `/features`, fed by a **new** `feature_totals:\
  \ Record<FeatureState,number>` on `SpacesResponse` — do\n  **not** widen `totals`/`task_counts`/`Activity.state`\
  \ (note 6). AI Performance + Test Health untouched.\n- **Backend totals:** extend\
  \ `SpacesResponse`/`SpaceSummary` (api/spaces.py:86-119) with feature-count\n  fields\
  \ (separate from `task_counts`). StatsPage/per-task stats out of scope (no agent\
  \ runs).\n- **E2E pytest** `backend/tests/test_features_e2e.py` (deterministic;\
  \ TestClient; stub agent\n  subprocess + `gh`): capture → `FEAT-001` + MD + mocked\
  \ issue (number/url) → `/process` →\n  decomposition creates goal+tasks with `realizes`\
  \ → `planned` → drive goal to `done` + simulate\n  `feature/<slug>` deleted on origin\
  \ → feature `done` + issue closed; assert Tasks board excludes\n  it, Features board\
  \ buckets it, `feature_totals` reflects it.\n\n**Scope files:** DashboardPage.tsx,\
  \ api/spaces.py, types.ts (feature-count fields), `backend/tests/test_features_e2e.py`\
  \ (new).\n**Acceptance:** dashboard shows feature presence (≥ tile + total) without\
  \ altering the 5 task tiles or\n`task_counts`-driven UI (Spaces grid, Sidebar open-count);\
  \ AI Performance + Test Health render\nidentically; the e2e passes end-to-end; `tsc\
  \ --strict` + pytest ≥60% green."
has_ui: true
coverage_summary:
  searched:
  - backend/app/models.py
  - backend/app/api/spaces.py
  - frontend/src/pages/DashboardPage.tsx
  - frontend/src/types.ts
  - backend/tests/test_feature_decompose_e2e.py
  excluded:
  - backend/app/worker.py: no changes required; mocked in e2e test
  - frontend/src/components/: no new components needed, StatTile is inline in DashboardPage.tsx
  - backend/app/storage.py: feature_state machine validated by S1-S4; no changes required
  strategies:
  - memory_retrieval
  - read_targeted
traceability:
- requirement_id: R1
  statement: 'SpacesResponse Pydantic model gains a new field `feature_totals: dict[FeatureState,
    int]` with a default empty dict, separate from the existing `totals` and not widening
    any task-count fields.'
  acceptance_criteria:
  - Given the existing SpacesResponse model in backend/app/models.py, when `feature_totals`
    is added as a `dict[FeatureState, int]` field with `Field(default_factory=dict)`,
    then the model serializes a key `feature_totals` in the JSON response distinct
    from `totals`.
  - The `totals`, `task_counts` (on SpaceSummary), and `Activity.state` fields are
    unmodified.
  - FeatureState import is already present in models.py; no new imports needed beyond
    confirming FeatureState is accessible.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R2
  statement: The `list_spaces` endpoint in backend/app/api/spaces.py computes `feature_totals`
    by iterating all tasks and grouping those with a non-None `feature_state` by that
    state, returning a count per FeatureState value.
  acceptance_criteria:
  - Given tasks with `feature_state` values, when GET /api/spaces is called, then
    `feature_totals` contains correct counts for each FeatureState key present.
  - Given no feature tasks exist, when GET /api/spaces is called, then `feature_totals`
    is an empty dict.
  - The existing `totals` computation loop (lines 116-118 of spaces.py) is not modified.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R3
  statement: 'The TypeScript `SpacesResponse` interface in frontend/src/types.ts gains
    a `feature_totals: Record<FeatureState, number>` field so the frontend type matches
    the backend contract.'
  acceptance_criteria:
  - 'Given the existing `SpacesResponse` interface, when `feature_totals: Record<FeatureState,
    number>` is added, then `tsc --strict` passes without error.'
  - '`FeatureState` is already exported from types.ts (line 34); no new type declaration
    is needed.'
  - 'The `totals: Record<TaskState, number>` field on SpacesResponse is not changed.'
  verifying_phase: test
  confidence: 0.95
- requirement_id: R4
  statement: DashboardPage.tsx adds a single new StatTile labeled 'Features' (or 'Features
    / In Backlog') linking to `/features`, displaying the count from `feature_totals.backlog`
    with a safe zero default.
  acceptance_criteria:
  - Given the data returned by useSpaces includes `feature_totals`, when DashboardPage
    renders, then a StatTile with `to='/features'` is present in the stat tile section.
  - The tile value equals `spacesData.feature_totals?.backlog ?? 0` or an equivalent
    safe access expression.
  - Given `feature_totals` is undefined (older API response), when DashboardPage renders,
    the tile renders 0 and does not throw.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R5
  statement: The stat tile grid in DashboardPage.tsx is updated from `md:grid-cols-5`
    to `md:grid-cols-6` to accommodate the 6th tile without breaking the responsive
    layout.
  acceptance_criteria:
  - The section containing StatTile components uses a CSS grid class that displays
    6 columns on medium+ screens.
  - On small screens the grid wraps gracefully using existing `sm:grid-cols-3` and
    `grid-cols-2` classes (preserved or equivalently updated).
  - The 5 existing task-state tiles remain in the same relative order with unchanged
    values sourced from `totals`.
  verifying_phase: review
  confidence: 0.9
- requirement_id: R6
  statement: 'Non-regression: the 5 existing stat tiles, Sidebar open-count, SpaceCard
    task_counts grid, AI Performance card, and Test Health card are visually and functionally
    unchanged.'
  acceptance_criteria:
  - The existing 5 StatTile components read from `totals` (TaskState-keyed), not `feature_totals`.
  - Sidebar open-count logic (derived from task state counts) has no code changes.
  - SpaceCard per-space task count grid continues to use `task_counts` (SpaceSummary
    field).
  - AI Performance and Test Health card components have no changes to their data source,
    markup, or styling.
  verifying_phase: review
  confidence: 0.95
- requirement_id: R7
  statement: 'A new file `backend/tests/test_features_e2e.py` is created that drives
    the full feature lifecycle deterministically: capture (FEAT-001 + MD + mocked
    GitHub issue) → /process (decomposition creates realizing goal+tasks with `realizes`
    field) → planned → drive goal to done + simulate `feature/<slug>` branch deleted
    on origin → feature done + GitHub issue closed.'
  acceptance_criteria:
  - Given a feature task with `feature_key=FEAT-001`, `issue_number=42`, and mocked
    `gh_issue_close`, when the test drives the worker through decompose and done,
    then `gh_issue_close` is called with `issue_number=42`.
  - Given the realizing goal reaches `done` and the feature branch does not exist
    on origin (mocked), when done-detection logic runs, then `feature_state` transitions
    to `done`.
  - The test does not use `importlib.reload()` on core modules.
  - The test does not make real network calls or git operations; all external I/O
    is mocked.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R8
  statement: 'The e2e test asserts Tasks board exclusion, Features board inclusion,
    and `feature_totals` correctness: feature tasks with `feature_state=done` do not
    appear in task board lanes, appear in /api/features with correct state, and `feature_totals`
    in GET /api/spaces reflects the done count.'
  acceptance_criteria:
  - Given a feature task with `feature_state=done`, when the tasks board is queried
    (GET /api/tasks or board endpoint), then the feature task is absent from backlog/active/waiting/done
    task lanes.
  - Given the same feature task, when GET /api/features is called for the space, then
    the task appears with `feature_state='done'`.
  - 'The `feature_totals` dict in GET /api/spaces reflects `done: 1` (or incremented
    count) after the feature reaches done.'
  verifying_phase: test
  confidence: 0.85
- requirement_id: R9
  statement: The full pytest suite passes at or above the 60% coverage floor and `tsc
    --strict` passes for the frontend changes, after all S6 changes are applied.
  acceptance_criteria:
  - Running `pytest tests/ --cov=app --cov-report=term-missing --cov-fail-under=60`
    exits 0.
  - Running `tsc --strict` (or `npm run build`) for the frontend exits 0 with no type
    errors.
  - The new test_features_e2e.py contributes additional coverage for the feature_totals
    computation path in api/spaces.py.
  verifying_phase: test
  confidence: 0.92
metrics:
  tool_calls: 9
  files_read: 6
  memory_hits: 5
---

## Summary

S6 extends the Cronos dashboard with a single new "Features" stat tile fed by a new `feature_totals` field on `SpacesResponse`, and adds a comprehensive end-to-end pytest that exercises the full feature lifecycle (capture, decompose, planned, done, branch-delete, issue-close). All changes are additive: existing task-count fields, UI tiles, and analytics cards are untouched. The scope is tightly bounded to four files — `DashboardPage.tsx`, `api/spaces.py`, `types.ts`, and a new `test_features_e2e.py` — providing a low-blast-radius implementation target. Dependencies S1–S5 must be merged to `feature/features-and-fixes` before this subgoal begins.

## Scope

### In scope
- Add `feature_totals: dict[FeatureState, int]` field to `SpacesResponse` in `backend/app/models.py`
- Compute `feature_totals` in `list_spaces()` in `backend/app/api/spaces.py`
- Add `feature_totals: Record<FeatureState, number>` to the `SpacesResponse` TypeScript interface in `frontend/src/types.ts`
- Add one new `StatTile` (label: "Features", value: `feature_totals.backlog`) linking to `/features` in `frontend/src/pages/DashboardPage.tsx`
- Adjust stat tile grid class from `md:grid-cols-5` to `md:grid-cols-6`
- Create `backend/tests/test_features_e2e.py` covering the full feature lifecycle with deterministic mocks

### Out of scope
- `SpaceSummary.task_counts` — must not be widened or renamed
- `totals` field on `SpacesResponse` — must not be modified
- `Activity.state` type — must not be widened (locked design note 6)
- StatsPage and per-task stats (explicitly excluded by request: "no agent runs")
- Sidebar open-count logic — derives from task states only, no changes
- SpaceCard grid — uses `task_counts` per-space, must not reference `feature_totals`
- AI Performance card and Test Health card — explicitly untouched per request

### Deferred
- Per-space `feature_totals` breakdown on `SpaceSummary` (only global totals on `SpacesResponse` needed for MVP)
- Dashboard tile toggling or user preferences for feature tile visibility
- Showing all active (non-done) feature counts rather than backlog-only in the tile

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | Add `feature_totals: dict[FeatureState, int]` field to `SpacesResponse` Pydantic model |
| R2 | Compute `feature_totals` in `list_spaces()` endpoint by grouping tasks by feature_state |
| R3 | Add `feature_totals: Record<FeatureState, number>` to TypeScript `SpacesResponse` interface |
| R4 | Add a new StatTile in DashboardPage showing backlog-count linking to `/features` |
| R5 | Adjust stat tile grid to 6 columns without breaking responsive layout |
| R6 | Non-regression: 5 existing tiles, Sidebar, SpaceCard, AI Performance, Test Health unchanged |
| R7 | Create `test_features_e2e.py` covering capture→process→decompose→planned→done+branch-delete→issue-close |
| R8 | E2E asserts Tasks board exclusion, Features board inclusion, and `feature_totals` in GET /api/spaces |
| R9 | Full test suite passes at ≥60% coverage and `tsc --strict` exits 0 |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). The body summary below mirrors them in compact form for the human reader.

- R1 — `SpacesResponse` gains `feature_totals` with default empty dict; `totals`/`task_counts`/`Activity.state` untouched
- R2 — `list_spaces()` computes feature_totals from task iteration; empty dict when no feature tasks; existing totals loop unmodified
- R3 — `tsc --strict` passes after adding `feature_totals: Record<FeatureState, number>` to TypeScript interface
- R4 — StatTile with `to='/features'` renders; value is `feature_totals?.backlog ?? 0`; no crash when field absent
- R5 — Grid uses `md:grid-cols-6`; small-screen wrapping preserved; 5 existing tiles unchanged
- R6 — All 5 existing tiles source from `totals`; Sidebar/SpaceCard/AI Performance/Test Health code unmodified
- R7 — E2E drives full lifecycle with mocks; `gh_issue_close` called with correct issue_number; `feature_state=done` asserted; no real I/O
- R8 — Feature task absent from task board after done; present in /api/features; `feature_totals.done >= 1`
- R9 — pytest ≥60% exits 0; tsc --strict exits 0

## Traceability

The full requirement → acceptance criteria → verifying_phase map is the YAML `traceability[]` array. Downstream agents read the YAML directly; this section exists so a human reader sees the same routing table without parsing YAML.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | SpacesResponse Pydantic model gains `feature_totals: dict[FeatureState, int]` separate from `totals` |
| R2 | test | `list_spaces()` computes feature_totals by iterating tasks grouped by feature_state |
| R3 | test | TypeScript SpacesResponse gains `feature_totals: Record<FeatureState, number>` |
| R4 | test | DashboardPage adds StatTile linking to `/features` with value from feature_totals.backlog |
| R5 | review | Stat tile grid adjusts to 6 columns; responsive layout preserved |
| R6 | review | 5 existing tiles, Sidebar, SpaceCard, AI Performance, Test Health are unchanged |
| R7 | test | test_features_e2e.py covers full lifecycle: capture→decompose→planned→done+branch-delete→issue-close |
| R8 | test | E2E asserts Tasks board exclusion, Features board inclusion, feature_totals in /api/spaces |
| R9 | test | pytest ≥60% green; tsc --strict passes |

## Assumptions

- S1 (FeatureState, feature_state field on Task), S2 (features API), S3 (gh mirroring, issue fields), S4 (decompose worker, realizes field), and S5 (FeaturesBoard UI, /features route) are fully merged to `feature/features-and-fixes` before S6 begins, per the dep: S3, S4, S5 constraint in the request.
- `feature_totals` is a global aggregate (all spaces) on `SpacesResponse`, mirroring the pattern of `totals` — per-space breakdown is deferred.
- The tile value for "Features / In Backlog" is `feature_totals.backlog` only (the open backlog count), not a sum of all non-done states. The request labels the tile "In Backlog"; backlog-only is the minimal safe interpretation.
- The new e2e test uses the async pytest pattern from `test_feature_decompose_e2e.py`. The request text says "TestClient" but the existing canonical e2e uses async pytest; the design agent should resolve this before implementation (noted in Open questions).
- `importlib.reload()` must not be used in the new test (project-wide constraint from `observation_importlib_reload_test_pollution` memory entry).
- has_ui=true rationale: the request explicitly marks `has_ui: yes` and requires changes to `DashboardPage.tsx` (React component with a new visual StatTile and grid layout change).
- The `feature_totals` computation in `list_spaces()` iterates `task_store.all()` and filters by tasks that have a non-None `feature_state`, then groups by that state — matching the existing `totals` loop pattern at lines 116-118 of spaces.py.

## Open questions

- Tile label: the request lists both "Features" and "In Backlog" as label candidates. The `StatTile` component takes a single `label` prop. The design agent should determine whether to use "Features / In Backlog" as a combined string or whether to extend StatTile to support a sub-label.
- Feature tile value scope: the request says "In Backlog" which implies `feature_totals.backlog` only. Confirm this is not intended to show all active (backlog + processing + planned) features.
- E2E test style: the request says "TestClient" but `test_feature_decompose_e2e.py` uses async pytest. The design agent should pick one pattern and note it in the design report.

## Next consumer brief

Read `traceability[]` first — all 9 requirements are ground truth for this subgoal. `has_ui=true` routes through the UI sub-track.

**Files and blast radius (implementor priority order):**
1. `backend/app/models.py` — 1-line Pydantic field addition to `SpacesResponse` (R1); FeatureState is already imported
2. `backend/app/api/spaces.py` — 4-5 lines appended to `list_spaces()` to compute `feature_totals` (R2); the existing `totals` loop at lines 116-118 must not be touched
3. `frontend/src/types.ts` — 1-line addition to `SpacesResponse` interface (R3); `FeatureState` already exported at line 34
4. `frontend/src/pages/DashboardPage.tsx` — add 1 `<StatTile>` in the stat tile `<section>`; change grid class from `md:grid-cols-5` to `md:grid-cols-6` (R4, R5); existing 5 tiles must not change (R6)
5. `backend/tests/test_features_e2e.py` — new file, ~200-300 lines, following `test_feature_decompose_e2e.py` mock pattern (R7, R8)

**Critical non-regression constraint (R6):** the Sidebar, SpaceCard, AI Performance, and Test Health code paths must not be touched. Locked design note 6 prohibits widening `totals`/`task_counts`/`Activity.state`.

**Key design decisions to resolve before implementation:** StatTile label string format; feature tile value (backlog-only vs. backlog+processing); e2e async vs. TestClient style.
