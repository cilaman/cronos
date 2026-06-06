---
cc_version: '1.0'
agent: pipeline-architect
slug: featurefix-dashboard-e2e
phase: design
status: done
confidence: 0.86
inputs_used:
- memory:project_dashboard_design
- memory:project_s1_data_model_impl
- memory:project_s2_api_impl
- memory:project_s5_board_ui_impl
- memory:project_arc_features_fixes_board_setup
- memory:observation_importlib_reload_test_pollution
- memory:feedback_pipeline_narrow_k_coverage
- .cronos/pipeline/featurefix-dashboard-e2e/analysis-report-featurefix-dashboard-e2e.md
- .cronos/pipeline/featurefix-dashboard-e2e/scout-report-featurefix-dashboard-e2e.md
- backend/app/models.py
- backend/app/api/spaces.py
- frontend/src/pages/DashboardPage.tsx
outputs_produced:
- .cronos/pipeline/featurefix-dashboard-e2e/design-report-featurefix-dashboard-e2e.md
blockers: []
next_consumer: pipeline-implementor
coverage_summary:
  searched:
  - backend/app/models.py
  - backend/app/api/spaces.py
  - frontend/src/pages/DashboardPage.tsx
  - frontend/src/types.ts
  - backend/tests/test_feature_decompose_e2e.py
  excluded:
  - 'backend/app/storage.py: feature_state machine landed in S1; no changes needed'
  - 'backend/app/worker.py: decompose + done-detection landed in S4; only mocked in
    e2e'
  - 'frontend/src/pages/FeaturesBoard.tsx: S5 deliverable; only target of /features
    link'
  - 'Sidebar / SpaceCard / AI Performance / Test Health: locked non-regression scope
    (R6)'
  strategies:
  - memory_retrieval
  - read_targeted
iterations:
- id: I1
  type: data
  scope_files:
  - backend/app/models.py
  validation_command: cd backend && pytest tests/test_models.py -v --override-ini="addopts="
    || cd backend && pytest tests/ -k feature_totals -v --override-ini="addopts="
  max_diff_lines: 30
  depends_on: []
- id: I2
  type: backend
  scope_files:
  - backend/app/api/spaces.py
  - backend/tests/test_spaces_feature_totals.py
  validation_command: cd backend && pytest tests/test_spaces_feature_totals.py -v
    --override-ini="addopts="
  max_diff_lines: 200
  depends_on:
  - I1
- id: I3
  type: frontend
  scope_files:
  - frontend/src/types.ts
  validation_command: cd frontend && npx tsc --noEmit
  max_diff_lines: 20
  depends_on:
  - I1
- id: I4
  type: frontend
  scope_files:
  - frontend/src/pages/DashboardPage.tsx
  - frontend/src/pages/DashboardPage.featuretile.test.tsx
  validation_command: cd frontend && npx tsc --noEmit && npm test -- --run src/pages/DashboardPage.featuretile.test.tsx
  max_diff_lines: 250
  depends_on:
  - I3
- id: I5
  type: backend
  scope_files:
  - backend/tests/test_features_e2e.py
  validation_command: cd backend && pytest tests/test_features_e2e.py -v --override-ini="addopts="
  max_diff_lines: 500
  depends_on:
  - I2
- id: I6
  type: backend
  scope_files:
  - backend/tests/test_features_e2e.py
  validation_command: cd backend && pytest tests/ --cov=app --cov-report=term-missing
    --cov-fail-under=60
  max_diff_lines: 80
  depends_on:
  - I2
  - I4
  - I5
risks:
- description: Mutating the existing `totals` computation loop at spaces.py:116-118
    while adding `feature_totals` could regress the 5 task-state tiles fed by `totals`
    (R6 non-regression).
  severity: high
  mitigation: I2 instructs the implementor to append a second, independent loop after
    the existing `totals` loop (do not fold them together); I2 validation includes
    an explicit assertion that GET /api/spaces still returns all 5 TaskState keys
    in `totals` with unchanged values for a fixture with no feature tasks.
- description: The new e2e test in I5 may collide with other tests by importlib.reload()-ing
    core modules (storage/worker), corrupting subsequent pytest state (observation_importlib_reload_test_pollution).
  severity: high
  mitigation: I5 explicitly forbids `importlib.reload()` in test_features_e2e.py;
    implementor must mirror the mock-injection pattern from test_feature_decompose_e2e.py
    (monkeypatch attributes on already-imported modules, no reload). I6 runs the full
    suite to catch any test-pollution regression.
- description: Adding a 6th StatTile widens the dashboard grid; an `md:grid-cols-5`
    -> `md:grid-cols-6` change on a high-density screen may shrink existing tiles
    below the readable threshold.
  severity: medium
  mitigation: I4 keeps existing `grid-cols-2 sm:grid-cols-3` breakpoints intact (2-row
    wrap on small screens), updates only the md+ breakpoint. The 6th tile uses the
    same `<StatTile>` component with identical spacing tokens so density change is
    uniform across all 6 tiles.
- description: Narrow pytest `-k` filters fail the project-wide `--cov-fail-under=60`
    floor when run in isolation, causing implementor I2/I5 validation to falsely report
    failure even when the new tests pass (feedback_pipeline_narrow_k_coverage).
  severity: medium
  mitigation: I1, I2, I3, I5 validation commands include `--override-ini="addopts="`
    to disable the coverage gate during iteration validation. I6 runs the full suite
    with the coverage gate to enforce the 60% floor as a final check.
- description: Frontend `feature_totals` access in DashboardPage may crash if the
    backend response is from an older deploy that lacks the field (rolling-deploy
    skew), violating R4 safe-default acceptance.
  severity: medium
  mitigation: I4 instructs implementor to use `spacesData?.feature_totals?.backlog
    ?? 0` (optional chaining + nullish coalescing) and adds a Vitest assertion in
    DashboardPage.featuretile.test.tsx that the tile renders `0` when `feature_totals`
    is undefined in the mocked query result.
- description: If S3 (gh mirror) or S4 (decompose worker, done-detection) is not actually
    merged at I5 start time, the e2e will fail with missing-API errors that look like
    test bugs.
  severity: low
  mitigation: 'I5 begins with a precondition check: import `Worker._run_feature_decompose`,
    `git_ops.branch_exists_on_origin`, and `gh_issue_close`; fail fast in test setup
    with a clear xfail message if any are missing. Dependency on I2 (which already
    exercises a feature_totals path) gives early signal that S1-S5 are present.'
metrics:
  tool_calls: 8
  files_read: 7
  memory_hits: 7
  iterations_planned: 6
---

## Summary

S6 adds one Pydantic field, one backend computation, one TypeScript field, one StatTile + grid-class bump, and one new end-to-end pytest. The design fans the work into 6 iterations on a shallow DAG: I1 (data model) is the only group-0 entry; I2 (backend compute + targeted test) and I3 (TypeScript type) run in parallel as group 1; I4 (UI tile + Vitest) follows I3; I5 (e2e test) follows I2; and I6 (full-suite coverage gate) blocks on I2, I4, I5. The dominant risks are R6 non-regression (do not touch the existing `totals` loop) and importlib.reload test pollution in the new e2e — both pinned with explicit mitigations. All scope is additive; the request's locked non-regression scope (Sidebar, SpaceCard, AI Performance, Test Health) is enforced by hard `scope_files` boundaries on every iteration.

## Components

### Data
- `SpacesResponse.feature_totals: dict[FeatureState, int]` — new Pydantic field in `backend/app/models.py`, default `Field(default_factory=dict)`, sibling to existing `totals`. `FeatureState` is already imported in models.py (S1 deliverable).

### Backend
- `list_spaces()` in `backend/app/api/spaces.py` — appends a second loop after the existing `totals` loop (lines 116-118) that iterates `task_store.all()`, filters to tasks where `task.feature_state is not None`, and groups by `feature_state` into a `dict[FeatureState, int]`. The existing `totals` loop is not modified.
- `backend/tests/test_spaces_feature_totals.py` (new, targeted) — exercises four cases: no feature tasks (empty dict), single feature in `backlog`, mixed backlog+done, and a regression assertion that `totals` still contains all 5 TaskState keys with correct counts.
- `backend/tests/test_features_e2e.py` (new, end-to-end) — drives capture → decompose → planned → done + branch-deleted → issue-closed using mocks mirroring `test_feature_decompose_e2e.py`; asserts Tasks board exclusion (GET /api/tasks), Features board inclusion (GET /api/features), and `feature_totals` shape on GET /api/spaces. No `importlib.reload()`.

### Frontend
- `SpacesResponse` TypeScript interface in `frontend/src/types.ts` — adds `feature_totals: Record<FeatureState, number>;`. `FeatureState` already exported at line 34.
- `DashboardPage.tsx` — adds one `<StatTile label="Features" value={spacesData?.feature_totals?.backlog ?? 0} to="/features" />` inside the stat-tile section; changes the section grid class from `md:grid-cols-5` to `md:grid-cols-6` (small-screen classes `grid-cols-2 sm:grid-cols-3` preserved verbatim). The 5 existing tiles are not touched.
- `DashboardPage.featuretile.test.tsx` (new Vitest, co-located) — asserts (a) the 6th tile renders with `to='/features'`, (b) safe-zero default when `feature_totals` is undefined, (c) the 5 existing tiles still source from `totals` keys (no value drift).

## Implementation plan

| ID  | Type     | Depends on | Scope files (abridged)                                                            | Validation                                                                |
|-----|----------|------------|-----------------------------------------------------------------------------------|---------------------------------------------------------------------------|
| I1  | data     | —          | backend/app/models.py                                                             | cd backend && pytest tests/test_models.py -v --override-ini=...           |
| I2  | backend  | I1         | backend/app/api/spaces.py, backend/tests/test_spaces_feature_totals.py            | cd backend && pytest tests/test_spaces_feature_totals.py -v ...           |
| I3  | frontend | I1         | frontend/src/types.ts                                                             | cd frontend && npx tsc --noEmit                                           |
| I4  | frontend | I3         | frontend/src/pages/DashboardPage.tsx, frontend/src/pages/DashboardPage.featuretile.test.tsx | cd frontend && npx tsc --noEmit && npm test -- --run ...        |
| I5  | backend  | I2         | backend/tests/test_features_e2e.py                                                | cd backend && pytest tests/test_features_e2e.py -v ...                    |
| I6  | backend  | I2, I4, I5 | backend/tests/test_features_e2e.py                                                | cd backend && pytest tests/ --cov=app --cov-report=term-missing --cov-fail-under=60 |

Topological order: [I1] -> [I2, I3] -> [I4, I5] -> [I6]. The orchestrator can fan I2 and I3 in parallel (both depend only on I1), and again fan I4 and I5 in parallel (I4 depends on I3, I5 depends on I2; neither depends on the other). I6 is the final coverage gate.

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Mutating the existing `totals` loop while adding `feature_totals` regresses the 5 task-state tiles (R6 non-regression). | high | I2 appends a second independent loop, leaves spaces.py:116-118 byte-identical; I2 test asserts all 5 TaskState keys still present with unchanged counts. |
| New e2e uses `importlib.reload()` and poisons subsequent tests. | high | I5 forbids reload; mirrors monkeypatch-based mock injection from `test_feature_decompose_e2e.py`; I6 catches any pollution via full-suite run. |
| `md:grid-cols-5` -> `md:grid-cols-6` shrinks tiles below readable threshold on high-density screens. | medium | I4 preserves `grid-cols-2 sm:grid-cols-3`; only md+ breakpoint changes; uniform StatTile component shared by all 6 tiles. |
| Narrow `-k` pytest filters fail the project `--cov-fail-under=60` gate during iteration validation. | medium | I1/I2/I3/I5 use `--override-ini="addopts="`; I6 enforces the coverage floor with the full suite. |
| Older API response lacking `feature_totals` crashes DashboardPage. | medium | I4 uses `spacesData?.feature_totals?.backlog ?? 0`; Vitest covers the undefined-field case. |
| S3 or S4 not merged when I5 runs; e2e fails with missing-API noise. | low | I5 begins with import-level precondition check; depends on I2 so the missing-API signal surfaces earlier; xfail with a clear message if any S3/S4 symbol is absent. |

## Assumptions

- S1 (FeatureState enum + `feature_state` field on Task), S2 (features API + `realizes` field), S3 (gh issue mirror with `gh_issue_close` + `issue_number`), S4 (worker `_run_feature_decompose` + done-detection + `branch_exists_on_origin`), and S5 (FeaturesBoard at `/features`) are merged into `feature/features-and-fixes` before I5 runs. Analyst confirmed dep: S3, S4, S5 in the request; I5 precondition check is defense in depth.
- The tile label is "Features" (single word) and the value is `feature_totals.backlog` only (open backlog count). This resolves the analyst's open question #1 (label format) and #2 (value scope): backlog-only matches the request phrase "In Backlog" and avoids semantic drift if more FeatureState values are added later. The route is `/features` (S5 deliverable).
- The new e2e test uses the **async pytest pattern** from `test_feature_decompose_e2e.py`, not synchronous `TestClient`. This resolves analyst open question #3. Rationale: matching the canonical existing e2e minimizes mock-shape divergence and avoids re-inventing the worker-mock harness.
- `feature_totals` is a **global aggregate** on `SpacesResponse` (mirroring the existing `totals` shape), not a per-space breakdown on `SpaceSummary`. Per-space breakdown is explicitly deferred in the analysis report.
- The new Vitest in I4 is co-located (`DashboardPage.featuretile.test.tsx` next to `DashboardPage.tsx`) and runs via the existing Vitest config — no new test runner or jest-dom setup required.
- `npm test -- --run` is the correct one-shot Vitest invocation in this repo (Vitest watch is the default; `--run` forces single-pass).

## Open questions

- None. The three analyst open questions (tile label, value scope, e2e style) are resolved in `## Assumptions` above and pinned in I4/I5 scope.

## Next consumer brief

Implementors: read `iterations[]` YAML first — `scope_files` is a hard diff boundary, `validation_command` is what the tester will execute verbatim. Cross-iteration invariants the YAML alone does not capture:

1. **R6 non-regression — load-bearing.** I2 must NOT modify spaces.py:116-118 (the existing `totals` loop). Append a new loop after it. I4 must NOT modify the 5 existing `<StatTile>` JSX blocks or their `value=` expressions; only the grid class string and one new tile are in scope.
2. **Shared literal.** The route `/features` and the tile label `"Features"` must match between I4 and the S5 FeaturesBoard route. Do not introduce a typo or pluralization variant.
3. **No `importlib.reload()` anywhere in I5.** Use monkeypatch / unittest.mock patching of already-imported attributes, mirroring `test_feature_decompose_e2e.py`. This is a hard project-wide rule (`observation_importlib_reload_test_pollution`).
4. **Coverage floor.** Iterations I1–I5 use `--override-ini="addopts="` because narrow `-k` runs fail the project `--cov-fail-under=60` gate; I6 is the single canonical full-suite + coverage check.
5. **Topology.** Orchestrator: launch I1 alone; on I1 done launch I2 and I3 in parallel; on I2 done launch I5; on I3 done launch I4; I6 runs after all of I2, I4, I5 complete.
