---
cc_version: '1.0'
agent: pipeline-architect
slug: featurefix-api
phase: design
status: done
confidence: 0.86
inputs_used:
- memory:arc_features_fixes_board_setup
- memory:s1_data_model_impl
- memory:project_pipeline_schemas
- memory:project_pipeline_architect_agent
- memory:pipeline_narrow_k_coverage
- memory:worktree_main_vs_workspace
- .cronos/pipeline/featurefix-api/request.md
- .cronos/pipeline/featurefix-api/scout-report-featurefix-api.md
- .cronos/pipeline/featurefix-api/analysis-report-featurefix-api.md
- backend/app/main.py
- backend/app/models.py
- backend/app/api/tasks.py
- backend/app/storage.py
outputs_produced:
- .cronos/pipeline/featurefix-api/design-report-featurefix-api.md
blockers: []
next_consumer: pipeline-implementor
coverage_summary:
  searched:
  - backend/app/main.py
  - backend/app/models.py
  - backend/app/api/tasks.py
  - backend/app/storage.py
  - backend/app/api/ (router pattern survey)
  excluded:
  - frontend/: has_ui=false in analysis report
  - tests/: implementor authors tests inside each iteration's scope_files
  - feature_state.py: S1-owned, contract already locked (FEATURE_USER_TRANSITIONS)
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
iterations:
- id: I1
  title: Add request/response Pydantic schemas to models.py
  type: backend
  scope_files:
  - backend/app/models.py
  - backend/tests/test_feature_schemas.py
  validation_command: cd backend && pytest tests/test_feature_schemas.py -v --override-ini="addopts="
  max_diff_lines: 250
  depends_on: []
- id: I2
  title: Stub S3 mirror hook + S4 enqueue helper (no-op shims with stable signatures)
  type: backend
  scope_files:
  - backend/app/feature_hooks.py
  - backend/tests/test_feature_hooks.py
  validation_command: cd backend && pytest tests/test_feature_hooks.py -v --override-ini="addopts="
  max_diff_lines: 200
  depends_on: []
- id: I3
  title: Filter type in ('feature','fix') out of TaskStore.board() so tasks board
    stays disjoint from FeatureBoard
  type: backend
  scope_files:
  - backend/app/storage.py
  - backend/tests/test_storage_board_excludes_features.py
  validation_command: cd backend && pytest tests/test_storage_board_excludes_features.py
    -v --override-ini="addopts="
  max_diff_lines: 150
  depends_on: []
- id: I4
  title: Create api/features.py router skeleton + register in main.py (auth-parity,
    OpenAPI surface)
  type: backend
  scope_files:
  - backend/app/api/features.py
  - backend/app/main.py
  - backend/tests/api/test_features_router_registration.py
  validation_command: cd backend && pytest tests/api/test_features_router_registration.py
    -v --override-ini="addopts="
  max_diff_lines: 300
  depends_on:
  - I1
- id: I5
  title: POST /api/features — git-linked guard, key allocation, MD write, mirror fire
  type: backend
  scope_files:
  - backend/app/api/features.py
  - backend/tests/api/test_features_create.py
  validation_command: cd backend && pytest tests/api/test_features_create.py -v --override-ini="addopts="
  max_diff_lines: 350
  depends_on:
  - I1
  - I2
  - I4
- id: I6
  title: GET /api/features?space_id= → FeatureBoard via feature_board()
  type: backend
  scope_files:
  - backend/app/api/features.py
  - backend/tests/api/test_features_board.py
  validation_command: cd backend && pytest tests/api/test_features_board.py -v --override-ini="addopts="
  max_diff_lines: 200
  depends_on:
  - I1
  - I3
  - I4
- id: I7
  title: GET /api/features/{id} → feature + realizing_items[]
  type: backend
  scope_files:
  - backend/app/api/features.py
  - backend/tests/api/test_features_read.py
  validation_command: cd backend && pytest tests/api/test_features_read.py -v --override-ini="addopts="
  max_diff_lines: 250
  depends_on:
  - I1
  - I4
- id: I8
  title: PATCH /api/features/{id}/feature-state — transition table enforcement, mirror
    re-fire, 409 on illegal
  type: backend
  scope_files:
  - backend/app/api/features.py
  - backend/tests/api/test_features_state_transition.py
  validation_command: cd backend && pytest tests/api/test_features_state_transition.py
    -v --override-ini="addopts="
  max_diff_lines: 300
  depends_on:
  - I2
  - I4
  - I5
- id: I9
  title: PATCH /api/features/{id} — title/brief edit, key immutability, mirror re-fire
  type: backend
  scope_files:
  - backend/app/api/features.py
  - backend/tests/api/test_features_edit.py
  validation_command: cd backend && pytest tests/api/test_features_edit.py -v --override-ini="addopts="
  max_diff_lines: 250
  depends_on:
  - I2
  - I4
  - I5
- id: I10
  title: PATCH /api/features/{id}/realize — set_realizes link/unlink, no mirror fire
  type: backend
  scope_files:
  - backend/app/api/features.py
  - backend/tests/api/test_features_realize.py
  validation_command: cd backend && pytest tests/api/test_features_realize.py -v --override-ini="addopts="
  max_diff_lines: 250
  depends_on:
  - I4
  - I5
  - I7
- id: I11
  title: POST /api/features/{id}/process — transition to PROCESSING + S4 enqueue stub
  type: backend
  scope_files:
  - backend/app/api/features.py
  - backend/tests/api/test_features_process.py
  validation_command: cd backend && pytest tests/api/test_features_process.py -v --override-ini="addopts="
  max_diff_lines: 250
  depends_on:
  - I2
  - I4
  - I5
  - I8
- id: I12
  title: Full backend test suite — confirm 60% coverage floor holds with new module
  type: backend
  scope_files:
  - backend/tests/test_pipeline_coverage_smoke.py
  validation_command: cd backend && pytest tests/ --cov=app --cov-report=term-missing
    --cov-fail-under=60
  max_diff_lines: 100
  depends_on:
  - I1
  - I2
  - I3
  - I4
  - I5
  - I6
  - I7
  - I8
  - I9
  - I10
  - I11
risks:
- description: App-factory mounting drift — features_router could be added but not
    included with dependencies=_auth, leaving /api/features/* unauthenticated; or
    it could be registered before app.state.store is wired, causing import-time crashes.
  severity: high
  mitigation: I4 includes test_features_router_registration.py which asserts (a) the
    router is present in app.routes with prefix='/api/features', (b) an unauthenticated
    GET /api/features returns 401 (R14), and (c) every route's dependencies list contains
    require_auth. I4's scope_files explicitly enumerate main.py so the implementor
    is forced to wire it there, with the exact line shape `app.include_router(features_router,
    dependencies=_auth)` after the existing tasks_router include (line 526).
- description: MD canonical write-failure semantics — POST /api/features must allocate
    a key, persist the Task object, AND write the MD file; if MD write fails after
    the Task is persisted in-memory/SQLite, the system enters an inconsistent state
    where the key is burned but no MD exists, and a retry would allocate a second
    key (FEAT-002) for the same feature.
  severity: high
  mitigation: 'I5 follows the same pattern as the existing tasks POST: storage.create()
    is the single source of truth and is responsible for the MD round-trip. The router
    does not write MD itself; it calls store.create(type=''feature''|''fix'', ...)
    which already invokes dump_task on success. If create() raises, no Task object
    is returned and the key-allocation path inside _next_feature_key (which scans
    self._by_id under the store lock) sees no committed entry on the next attempt.
    I5''s test asserts that a forced MD-write failure leaves no in-memory Task and
    no allocated key visible to a follow-up call.'
- description: FEATURE_USER_TRANSITIONS divergence from S1 — if the implementor hand-codes
    the allowed transition set inside api/features.py instead of importing it from
    feature_state.py, a later S1-side edit to the transition table will silently desync
    the API.
  severity: medium
  mitigation: 'I8''s acceptance criteria pins the import: `from ..feature_state import
    FEATURE_USER_TRANSITIONS` and passes it through verbatim to `store.transition_feature(allowed=FEATURE_USER_TRANSITIONS)`.
    Test asserts the constant is imported (introspect module-level reference) and
    that the 409-on-illegal path is driven by this exact frozenset, not a re-declared
    local.'
- description: S3 mirror hook signature locks S3 in — if I2's no-op hook takes the
    wrong argument shape (e.g. accepts a Task model when S3 will need a (Task, space)
    tuple, or returns None when S3 needs an awaitable), every S2 call site will need
    to be edited in S3, leaking S2 churn into S3's diff.
  severity: medium
  mitigation: 'I2 defines the shim as `async def mirror_feature_to_github(task: Task,
    *, space: Space, reason: Literal[''create'',''state_change'',''edit'']) -> None:
    return None` — async (so S3 can `await` HTTP calls), takes the Task and Space
    (since git_repo_url lives on Space, not Task), and tags the trigger reason so
    S3 can route to different code paths without a refactor. The signature is documented
    in I2''s module docstring as ''S3 contract — DO NOT change without an S3 design
    change request''. S2 callers (I5/I8/I9/I11) await this function once per mutating
    call; I13 mirror-count test (in I5/I8/I9) uses monkeypatch to count invocations.'
- description: Mirror-count regression — R13 demands exactly one mirror fire per mutating
    endpoint and zero on read paths or /realize. A naive implementation may double-fire
    (e.g. once from the router and once from a worker callback) or skip-fire on 4xx
    error paths.
  severity: medium
  mitigation: Every mutating iteration (I5/I8/I9/I11) includes a test that patches
    `mirror_feature_to_github` with a Mock and asserts `mock.call_count == 1` on success
    and `== 0` on validation-failure (e.g. non-git-linked → 400, illegal transition
    → 409, 404 missing id). I10 (realize) and I6/I7 (GET) assert `mock.call_count
    == 0`. The mirror is called from a single helper inside api/features.py so the
    count is concentrated in one code path.
- description: Workspace-vs-feature-branch drift — the implementor agent will receive
    scope_files like `backend/app/feature_state.py` and `FEATURE_USER_TRANSITIONS`
    that only exist on the `feature/features-and-fixes` branch (per project_s1_data_model_impl
    memory + observation_worktree_main_vs_workspace). If they edit files in the main
    worktree and not the workspace worktree, goal-task-commit will fail to pick up
    the changes.
  severity: medium
  mitigation: Every iteration's scope_files uses workspace-relative paths only; implementor
    inherits the workspace worktree which is already on `feature/features-and-fixes`
    (parent goal branch per project_arc_features_fixes_board_setup memory). Implementor
    should run `git branch --show-current` as a preflight inside the workspace before
    any edit; if it returns anything other than `feature/features-and-fixes`, escalate.
    This is reinforced in 'Next consumer brief' below.
- description: Narrow -k pytest scope cannot validate 60% coverage floor — per project_pipeline_narrow_k_coverage
    memory, narrow per-iteration tests always violate --cov-fail-under=60. The validation_command
    on I1–I11 uses --override-ini='addopts=' to disable the coverage gate during per-iteration
    validation.
  severity: low
  mitigation: I12 is the dedicated final iteration that runs the full backend suite
    WITHOUT the override, so the 60% floor is asserted exactly once at the end of
    the iteration DAG. Per-iteration commands set validation_command_passed=true on
    narrow scope, then I12 acts as the gate before doc phase. Memory feedback_pipeline_narrow_k_coverage
    cited verbatim.
metrics:
  tool_calls: 12
  files_read: 7
  memory_hits: 6
  iterations_planned: 12
---

## Summary

S2 adds a dedicated `backend/app/api/features.py` FastAPI router (prefix `/api/features`) with eight endpoints that wrap S1's storage primitives (`feature_board`, `transition_feature`, `realizing_items`, `set_realizes`, `_next_feature_key`) and a new `feature_hooks.py` module that provides no-op shims with stable signatures for the S3 mirror and S4 enqueue (locking those contracts now so S3/S4 add behavior without churning S2). The iteration DAG is wide at the base (I1 schemas, I2 hooks, I3 board exclusion all parallel) and converges through I4 (router skeleton + registration) into one endpoint per iteration (I5–I11), all gated by a final I12 that asserts the 60 % coverage floor on the full backend suite. The single load-bearing tradeoff in the risk register: the S3 hook signature `async def mirror_feature_to_github(task: Task, *, space: Space, reason: Literal[...])` is locked at I2 and cited from every mutating endpoint; the alternative (let S3 design the signature later) would force a wide S2 refactor when S3 lands.

## Components

### Data
- `FeatureBoard` (Pydantic model in `models.py`) — five named lane fields (`backlog`, `processing`, `planned`, `waiting`, `done`) each `list[TaskSummary]`, mirroring the existing `Board` shape for serialization consistency. Covers R2, R4, R10.
- `CreateFeatureBody`, `PatchFeatureBody`, `PatchFeatureStateBody`, `PatchRealizeBody` (Pydantic request schemas in `models.py`) — `type: Literal["feature","fix"]`, `priority: int = Field(ge=1, le=5)`, etc. Covers R2.
- `FeatureRead` (Pydantic response schema in `models.py`) — extends `TaskRead`-equivalent fields plus `realizing_items: list[TaskSummary]`. Covers R5.

### Backend
- `backend/app/api/features.py` (NEW) — eight endpoints under `prefix="/api/features"`, `tags=["features"]`, `dependencies=_auth` via main.py registration. Single mirror-call helper internal to the module concentrates R13 enforcement.
- `backend/app/feature_hooks.py` (NEW) — two no-op async shims: `mirror_feature_to_github(task, *, space, reason)` for S3 and `enqueue_feature_decomposition(task)` for S4. Module docstring marks these as S3/S4 contracts; signature changes require a phase-level design change.
- `backend/app/storage.py` (EDIT) — single targeted change to `TaskStore.board()` to filter out `task.type in ("feature","fix")` before lane assignment. Covers R4, R10.
- `backend/app/main.py` (EDIT) — one new import + one new `app.include_router(features_router, dependencies=_auth)` line, placed adjacent to the existing tasks_router include (line 526). Covers R1, R14.

### Frontend
Omitted — `has_ui: false` in the analysis report.

## Implementation plan

| ID  | Type    | Depends on                       | Scope files (abridged)                                                            | Validation                                                                                  |
|-----|---------|----------------------------------|-----------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------|
| I1  | backend | —                                | backend/app/models.py, backend/tests/test_feature_schemas.py                       | cd backend && pytest tests/test_feature_schemas.py -v --override-ini="addopts="            |
| I2  | backend | —                                | backend/app/feature_hooks.py, backend/tests/test_feature_hooks.py                  | cd backend && pytest tests/test_feature_hooks.py -v --override-ini="addopts="              |
| I3  | backend | —                                | backend/app/storage.py, backend/tests/test_storage_board_excludes_features.py      | cd backend && pytest tests/test_storage_board_excludes_features.py -v --override-ini="addopts=" |
| I4  | backend | I1                               | backend/app/api/features.py, backend/app/main.py, backend/tests/api/test_features_router_registration.py | cd backend && pytest tests/api/test_features_router_registration.py -v --override-ini="addopts=" |
| I5  | backend | I1, I2, I4                       | backend/app/api/features.py, backend/tests/api/test_features_create.py             | cd backend && pytest tests/api/test_features_create.py -v --override-ini="addopts="        |
| I6  | backend | I1, I3, I4                       | backend/app/api/features.py, backend/tests/api/test_features_board.py              | cd backend && pytest tests/api/test_features_board.py -v --override-ini="addopts="         |
| I7  | backend | I1, I4                           | backend/app/api/features.py, backend/tests/api/test_features_read.py               | cd backend && pytest tests/api/test_features_read.py -v --override-ini="addopts="          |
| I8  | backend | I2, I4, I5                       | backend/app/api/features.py, backend/tests/api/test_features_state_transition.py   | cd backend && pytest tests/api/test_features_state_transition.py -v --override-ini="addopts=" |
| I9  | backend | I2, I4, I5                       | backend/app/api/features.py, backend/tests/api/test_features_edit.py               | cd backend && pytest tests/api/test_features_edit.py -v --override-ini="addopts="          |
| I10 | backend | I4, I5, I7                       | backend/app/api/features.py, backend/tests/api/test_features_realize.py            | cd backend && pytest tests/api/test_features_realize.py -v --override-ini="addopts="       |
| I11 | backend | I2, I4, I5, I8                   | backend/app/api/features.py, backend/tests/api/test_features_process.py            | cd backend && pytest tests/api/test_features_process.py -v --override-ini="addopts="       |
| I12 | backend | I1, I2, I3, I4, I5, I6, I7, I8, I9, I10, I11 | backend/tests/test_pipeline_coverage_smoke.py                          | cd backend && pytest tests/ --cov=app --cov-report=term-missing --cov-fail-under=60        |

### Per-iteration acceptance (mapped to traceability)

**I1 — Schemas.** Covers R2.
- `CreateFeatureBody(space_id: str, title: str, brief: str, type: Literal["feature","fix"], priority: int = Field(ge=1, le=5))` importable and validates.
- `PatchFeatureBody(title: str | None = None, brief: str | None = None)` importable.
- `PatchFeatureStateBody(feature_state: FeatureState)` importable; rejects unknown enum values.
- `PatchRealizeBody(item_id: str, feature_id: str | None)` importable; `feature_id` accepts `None` for unlink.
- `FeatureBoard(backlog, processing, planned, waiting, done: list[TaskSummary])` — exactly five fields named to match `FeatureState` values (lowercased).
- `FeatureRead` is `TaskRead`-shaped plus `realizing_items: list[TaskSummary]`.

**I2 — Hooks.** Locks signatures so S3/S4 can wire behavior without S2 churn.
- `async def mirror_feature_to_github(task: Task, *, space: Space, reason: Literal["create","state_change","edit"]) -> None` exists, returns None, is awaitable.
- `async def enqueue_feature_decomposition(task: Task) -> None` exists, returns None, is awaitable.
- Both functions have docstrings marking them as S3/S4 contracts.
- Test asserts both functions are present, awaitable, and accept the documented signature via `inspect.signature`.

**I3 — Board exclusion.** Covers R4 (partial), R10.
- `TaskStore.board(space_id)` skips tasks where `task.type in ("feature","fix")` before lane assignment.
- Test creates one task, one feature, one fix in the same space; asserts the resulting `Board` has only the task and that feature/fix are absent from all four lanes.

**I4 — Router skeleton + registration.** Covers R1, R14.
- `backend/app/api/features.py` defines `router = APIRouter(prefix="/api/features", tags=["features"])` with eight route stubs (all returning 501 Not Implemented at this iteration so the registration test can assert wiring without endpoint logic).
- `backend/app/main.py` adds `from .api.features import router as features_router` and `app.include_router(features_router, dependencies=_auth)` adjacent to the tasks router line.
- Test asserts: (a) `/api/features` resolves through OpenAPI introspection, (b) GET `/api/features?space_id=x` without auth → 401, (c) authenticated GET returns a documented (not 404) response code.
- I4 explicitly does NOT touch `api/tasks.py` — R1 requires no edits there.

**I5 — POST /api/features.** Covers R3, R11, R13 (one mirror call), R14.
- 400 when `space.git_repo_url is None`.
- On success: returns a `FeatureRead` with `feature_key` matching `^FEAT-\d{3}$` or `^FIX-\d{3}$`; MD file exists on disk; `mirror_feature_to_github` was invoked exactly once with `reason="create"`.
- Implementation calls `store.create(type=body.type, ...)` then `_next_feature_key` inside the store lock; the router never bypasses the store.
- Test patches `mirror_feature_to_github` with a Mock and asserts `call_count == 1`; tests the non-git-linked branch returns 400 and `call_count == 0`.

**I6 — GET /api/features?space_id=.** Covers R4, R10, R13 (zero mirror calls).
- Returns a `FeatureBoard` populated from `await store.feature_board(space_id)`.
- Feature items appear in their `feature_state` lane; items with `feature_state is None` are omitted.
- Test patches mirror Mock and asserts `call_count == 0`.

**I7 — GET /api/features/{id}.** Covers R5, R11, R13 (zero mirror calls).
- 404 for missing IDs or for tasks where `type not in ("feature","fix")`.
- Returns `FeatureRead` with `realizing_items` populated from `await store.realizing_items(id)`.
- Test creates feature F with two tasks T1, T2 having `realizes=F`; asserts `realizing_items` length 2.
- Test patches mirror Mock and asserts `call_count == 0`.

**I8 — PATCH /api/features/{id}/feature-state.** Covers R6, R12, R13 (one mirror call).
- Imports `FEATURE_USER_TRANSITIONS` verbatim from `feature_state.py` and passes it to `store.transition_feature(allowed=FEATURE_USER_TRANSITIONS)`.
- Returns 409 with descriptive detail on disallowed transitions; 404 on missing IDs.
- `feature_key` is unchanged across the transition (R12).
- Test asserts mirror `call_count == 1` on success and `0` on 409.

**I9 — PATCH /api/features/{id}.** Covers R7, R12, R13 (one mirror call).
- Updates `title` and/or `brief`; `updated_at` bumped.
- `feature_key` is unchanged (R12).
- 404 on missing IDs.
- Test asserts mirror `call_count == 1` on success and `0` on 404.

**I10 — PATCH /api/features/{id}/realize.** Covers R8, R13 (zero mirror calls).
- Calls `await store.set_realizes(body.item_id, body.feature_id or None)`.
- Self-reference (`item_id == feature_id`) and cross-space attempts surface as 400/422 from `validate_realizes` raising `StorageError` — router catches and returns 400.
- Test patches mirror Mock and asserts `call_count == 0`.
- After link, GET /api/features/{F} `realizing_items` reflects the new T.

**I11 — POST /api/features/{id}/process.** Covers R9, R13 (one mirror call via the state transition).
- Calls `store.transition_feature(id, FeatureState.PROCESSING, allowed=FEATURE_USER_TRANSITIONS)` then `await enqueue_feature_decomposition(task)`.
- Returns 409 on second invocation (PROCESSING → PROCESSING is not in `FEATURE_USER_TRANSITIONS`).
- 404 on missing IDs.
- Test asserts mirror `call_count == 1` (from the state-change leg) and `enqueue_feature_decomposition` called once.

**I12 — Full suite coverage gate.** Covers no specific requirement; gates the phase.
- Runs the entire backend test suite with the default coverage config.
- Asserts `--cov-fail-under=60` passes.
- Per `feedback_pipeline_narrow_k_coverage` memory: narrow `-k` validation steps in I1–I11 always violate the 60 % floor, so they use `--override-ini="addopts="`; I12 is the single full-suite gate. If I12 fails, the implementor must add tests to whatever new code lacks coverage before the test phase will pass.

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| App-factory mounting drift (router missing, auth missing, OpenAPI absent) | high | I4 dedicated registration test asserts presence in `app.routes`, `dependencies=_auth`, and 401-on-unauth. |
| MD canonical write-failure leaves a burned key with no MD on disk | high | I5 routes through `store.create()` which owns the MD round-trip; key allocation runs inside the store lock so a failed create is fully rolled back. |
| FEATURE_USER_TRANSITIONS divergence from S1 (local copy in router) | medium | I8 imports the frozenset verbatim from `feature_state.py`; test introspects the import. |
| S3 mirror hook signature locks S3 in to wrong shape | medium | I2 ships `async def mirror_feature_to_github(task: Task, *, space: Space, reason: Literal[...]) -> None` — async, accepts both Task and Space, tagged by trigger reason; docstring marks it as a phase contract. |
| Mirror-count regression (R13: must be exactly 1 on mutating, 0 on read/realize) | medium | Every mutating-endpoint iteration includes a Mock-patch test asserting `call_count`; mirror is funnelled through a single internal helper in `api/features.py`. |
| Workspace-vs-feature-branch drift (S1 code only on `feature/features-and-fixes`) | medium | All scope_files are workspace-relative; implementor preflight is documented in 'Next consumer brief'. |
| Narrow `-k` pytest scope violates 60 % coverage floor | low | I1–I11 use `--override-ini="addopts="`; I12 is the single full-suite gate at end of DAG. |

## Assumptions

- S1 deliverables (FeatureState enum, FEATURE_USER_TRANSITIONS frozenset, six new Task fields, feature_board / transition_feature / realizing_items / set_realizes / _next_feature_key / validate_realizes storage methods, MD serialization round-trip in dump_task / parse_file) are committed on `feature/features-and-fixes` and the workspace worktree is checked out on that branch. Verified by `project_s1_data_model_impl` memory.
- The implementor is bounded to the parent goal's `feature/features-and-fixes` branch and uses [[goal-task-commit]] after the review phase passes — never branches elsewhere, never merges to main. Verified by `project_arc_features_fixes_board_setup` memory and the request's Standing Rules.
- `Board` model in `models.py` has four lanes (`backlog`, `active`, `waiting`, `done`); `FeatureBoard` mirrors this shape but with five lanes named after `FeatureState` values lowercased (`backlog`, `processing`, `planned`, `waiting`, `done`). Verified by Read of `models.py` lines 111–117.
- `TaskStore.board()` does NOT currently filter `type in ("feature","fix")` on the workspace branch (lines 607–626). I3 is required to make R4 and R10 pass; this is a one-condition addition inside the existing loop, not a schema change.
- The S3 mirror function does not yet exist as a callable on this branch; I2 introduces it as a no-op async stub with a signature that S3 can fill in without changing call sites. Per analysis report Open question #1, this is the design's chosen resolution.
- The S4 worker hook entry point is not yet defined on this branch; I2 introduces `enqueue_feature_decomposition(task)` as the lock-in point. Per analysis report Open question #2, this is the design's chosen resolution — S2 does not need to know where S4 picks up the work, only that the enqueue point has a stable signature.
- `realizes` is plumbed via `PATCH /realize` only (analysis report assumption confirmed); `CreateTaskBody` is NOT extended in S2. This honours the request's pick-one instruction.
- Per `observation_subgoal_topo_ordering`: this is a leaf design (no sibling subgoals here), so iteration ordering is purely intra-design.

## Open questions

- None. The two questions raised in the analysis report's `## Open questions` are resolved by I2's stub-with-locked-signature strategy: the S3 mirror function identity is established here (`backend/app/feature_hooks.py::mirror_feature_to_github`), and the S4 enqueue entry point is established here (`backend/app/feature_hooks.py::enqueue_feature_decomposition`). Real implementations are S3/S4 scope.

## Next consumer brief

**Read first (YAML):** `iterations[]` (12 entries, topo-ordered), each iteration's `scope_files` (hard diff boundary — do NOT modify files outside this list), `validation_command` (per-iteration pytest call with `--override-ini="addopts="`), and `risks[]` (R13 mirror-count and FEATURE_USER_TRANSITIONS import are the load-bearing cross-iteration invariants).

**Cross-iteration invariants not derivable from YAML alone:**

1. **Branch.** All work happens on `feature/features-and-fixes`. Preflight: run `git -C <workspace> branch --show-current` before any edit; if it does not return `feature/features-and-fixes`, STOP and escalate.
2. **Mirror funnel.** Every mutating endpoint (I5, I8, I9, I11) routes its mirror call through a single internal helper in `api/features.py` — do NOT call `mirror_feature_to_github` from two places per endpoint. R13 mirror-count tests will fail.
3. **Transition import.** I8 and I11 must `from ..feature_state import FEATURE_USER_TRANSITIONS` — never redeclare the set locally. Tests introspect the module reference.
4. **Storage as source of truth.** I5 routes MD writes through `store.create(type=...)`; the router never writes MD directly. Same for I8/I9/I11 — they call `store.transition_feature` / `store.update` not their own writes.
5. **R10 cross-board disjointness.** I3 lands the storage filter; I6's `FeatureBoard` test must also assert the disjointness from the tasks `Board` on the same space (a regression in I3 will fail I6's assertion as well, providing belt-and-suspenders).
6. **Per-iter pytest flag.** Every per-iter `validation_command` carries `--override-ini="addopts="` to bypass the 60 % coverage floor on narrow `-k`-equivalent runs (per `feedback_pipeline_narrow_k_coverage` memory). I12 is the single full-suite coverage gate; if I12 fails, the implementor must add coverage rather than skip the gate.
7. **Out-of-scope no-ops.** S3 (real GitHub mirror) and S4 (decomposition worker) are explicitly OUT of S2 scope. I2's shims must return None and must NOT make HTTP calls, spawn workers, or touch git. They exist purely as signature contracts.

**Self-verify result:** `python -m app.pipeline.verify --agent design --slug featurefix-api --space /data/spaces/cronos-development` → expected exit code 0 (gate_decision: proceed). Reported below.
