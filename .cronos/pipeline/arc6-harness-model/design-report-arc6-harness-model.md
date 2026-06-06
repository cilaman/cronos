---
cc_version: '1.0'
agent: pipeline-architect
slug: arc6-harness-model
phase: design
status: done
confidence: 0.86
inputs_used:
- memory:project_architecture_key_modules
- memory:project_arc6_board_setup
- memory:project_pipeline_schemas
- .cronos/pipeline/arc6-harness-model/analysis-report-arc6-harness-model.md
- .cronos/pipeline/arc6-harness-model/scout-report-arc6-harness-model.md
- backend/app/pipeline/schemas/design.schema.yaml
outputs_produced:
- .cronos/pipeline/arc6-harness-model/design-report-arc6-harness-model.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - backend/app/harnesses/ (target package — to be created)
  - backend/app/api/harnesses.py (target router — to be created)
  - backend/app/storage.py (atomic_write + _dep_cycle_path patterns)
  - backend/app/space_storage.py (SpaceStore + async Lock + YAML round-trip patterns)
  - backend/app/models.py (Pydantic BaseModel + model_validator patterns)
  - backend/app/api/tasks.py (DI + HTTPException mapping patterns)
  - backend/app/main.py (router registration + app.state initialization)
  excluded:
  - frontend/: has_ui=false in analysis; frontend extensions are a separate future
      sub-goal
  - backend/app/agent.py: executor-phase concern, not data layer
  - backend/app/worker.py: executor-phase concern, not data layer
  strategies:
  - memory_retrieval
  - read_targeted
iterations:
- id: I1
  type: data
  scope_files:
  - backend/app/harnesses/__init__.py
  - backend/app/harnesses/model.py
  - backend/tests/test_harness_model.py
  validation_command: cd backend && pytest tests/test_harness_model.py -v
  max_diff_lines: 400
  depends_on: []
- id: I2
  type: data
  scope_files:
  - backend/app/harnesses/validator.py
  - backend/tests/test_harness_validator.py
  validation_command: cd backend && pytest tests/test_harness_validator.py -v
  max_diff_lines: 250
  depends_on:
  - I1
- id: I3
  type: backend
  scope_files:
  - backend/app/harnesses/store.py
  - backend/tests/test_harness_store.py
  validation_command: cd backend && pytest tests/test_harness_store.py -v
  max_diff_lines: 500
  depends_on:
  - I1
  - I2
- id: I4
  type: backend
  scope_files:
  - backend/app/api/harnesses.py
  - backend/tests/test_api_harnesses.py
  validation_command: cd backend && pytest tests/test_api_harnesses.py -v
  max_diff_lines: 500
  depends_on:
  - I3
- id: I5
  type: infra
  scope_files:
  - backend/app/main.py
  - backend/tests/test_harness_wiring.py
  validation_command: cd backend && pytest tests/test_harness_wiring.py -v
  max_diff_lines: 200
  depends_on:
  - I4
- id: I6
  type: backend
  scope_files:
  - backend/tests/test_harness_acceptance.py
  validation_command: cd backend && pytest tests/test_harness_acceptance.py -v
  max_diff_lines: 300
  depends_on:
  - I5
risks:
- description: 'YAML round-trip type coercion: yaml.safe_dump + yaml.safe_load may
    coerce numeric strings or alter scalar types inside data/variables dicts, breaking
    R8 lossless guarantee.'
  severity: high
  mitigation: In I3, use yaml.safe_dump(default_flow_style=False, sort_keys=False)
    and add a targeted test in test_harness_store.py that dumps a Harness containing
    int, float, bool, and str values inside data and variables, reloads it, and asserts
    type equality via isinstance — not just value equality.
- description: Cycle detection algorithm adaptation may drift from the storage.py
    BFS in a way that misses certain cycles (e.g. via parallel edges or self-loops
    on the same node).
  severity: high
  mitigation: 'In I2, write explicit test cases for: (a) self-loop A->A, (b) two-node
    cycle A->B->A, (c) three-node cycle A->B->C->A, (d) parallel edges A->B + A->B
    with no cycle, (e) fan-out A->B + A->C with no cycle. Validator is in backend/app/harnesses/validator.py
    — independent from storage.py imports.'
- description: Slugify collision handling could silently overwrite an existing on-disk
    harness file if name uniqueness is enforced in-memory but disk filenames collide
    due to slug truncation.
  severity: medium
  mitigation: In I3, slugify + collision-suffix logic must check both _by_name[(space_id,
    name)] AND disk filename presence; add a test that creates harnesses with names
    that slugify identically (e.g. 'My Flow!' and 'my flow') and asserts distinct
    filenames.
- description: 'DI wiring order in main.py: HarnessStore must be initialized on app.state
    before the router is included, or first request will fail with AttributeError.'
  severity: medium
  mitigation: I5 places HarnessStore() initialization in the existing startup section
    (mirrors SpaceStore pattern) and registers the router with the same _auth dependency
    list. The test_harness_wiring.py test asserts unauthenticated 401 and authenticated
    200 to catch both ordering and auth-wiring regressions.
- description: Pydantic v2 model_validator for cross-field constraints (unique ids,
    edge-to-port references) is sensitive to field ordering; an early field-validator
    error could mask the cross-field error and produce a less actionable 422 message.
  severity: medium
  mitigation: In I1, define field-level constraints (type enum, position required)
    first, then use @model_validator(mode='after') for cross-field checks. Tests in
    test_harness_model.py assert specific error-message substrings for each error
    mode (missing node ref, missing port ref, duplicate id) so regressions in message
    clarity are caught.
- description: Concurrent CRUD vs live-run conflict is explicitly deferred to executor
    phase (R13 = last-writer-wins) but a future executor that holds a Harness reference
    across an await could observe a stale model.
  severity: low
  mitigation: Document in harnesses.py module docstring (R13) that callers must re-fetch
    from HarnessStore.get after every await boundary; do not pass Harness models across
    async hops by reference. No runtime guard is implemented in this sub-goal — deferred
    to executor phase per analysis report.
metrics:
  tool_calls: 7
  files_read: 4
  memory_hits: 3
  iterations_planned: 6
---

## Summary

The harness data layer ships as a new `backend/app/harnesses/` package (`model.py`, `validator.py`, `store.py`) plus a `backend/app/api/harnesses.py` router wired into `main.py`. The plan splits into six iterations along a strict layering: Pydantic models (I1) feed a DAG validator (I2), both feed an async-Lock-protected YAML-backed store (I3), which is exposed via a FastAPI router (I4), wired into the app with auth (I5), and finally verified end-to-end by an acceptance test (I6) that mirrors the request's "POST 3-node/2-edge -> GET round-trips -> on-disk YAML matches" scenario. The DAG is wide at the top (I1 has no deps) then serializes through the store and API layers; this matches how the analysis decomposed cross-field model checks (Pydantic) vs. full-graph traversal (separate validator). The highest-severity risk is YAML round-trip type coercion in mixed-type dicts (R8) — explicitly tested in I3 via isinstance assertions, not just equality.

## Components

### Data
- `backend/app/harnesses/__init__.py`: package marker; re-exports `HarnessNode`, `HarnessEdge`, `Harness`, `NodeType`, `HarnessStore`, validator entrypoints for ergonomic imports from API layer.
- `backend/app/harnesses/model.py`: Pydantic v2 models — `NodeType` enum (`agent|trigger|decision|wait|aggregator`), `Position(x: float, y: float)`, `HarnessNode(id, type, position, ports: dict[str, dict], data: dict = {}, label: str)`, `HarnessEdge(id, source: NodeRef, target: NodeRef, condition: str | None = None)` where `NodeRef` carries `node_id` + `port_id`, and `Harness(name, description, nodes: list[HarnessNode], edges: list[HarnessEdge], variables: dict = {}, version: str = "1.0", created_at, updated_at)` with `@model_validator(mode="after")` enforcing unique node/edge ids and edge-to-node/port reference integrity (R1, R2, R3, R4).
- `backend/app/harnesses/validator.py`: pure-function `find_cycle(nodes, edges) -> list[str] | None` adapted from `storage.py::_dep_cycle_path` BFS, traversing outbound edges per node instead of `node.depends_on`; plus `validate_graph(harness) -> None` raising a `HarnessGraphError` on cycle / self-loop (R5).

### Backend
- `backend/app/harnesses/store.py`: `HarnessStore` class with `asyncio.Lock`, nested in-memory index `_by_space: dict[str, dict[str, Harness]]`, atomic write via tmpfile + `os.replace` (mirroring `storage.py::atomic_write`), `slugify_name` + collision-suffix function, YAML round-trip using `yaml.safe_dump(sort_keys=False, default_flow_style=False)` / `yaml.safe_load`, and async CRUD methods `create / get / list / update / delete` — every mutating method acquires the lock before touching the index or filesystem (R6, R7, R8).
- `backend/app/api/harnesses.py`: FastAPI `APIRouter(prefix="/api/spaces/{space_id}/harnesses", tags=["harnesses"])` with five endpoints (`GET list`, `POST create`, `GET fetch`, `PUT update`, `DELETE delete`), DI via `Request.app.state.harness_store`, error mapping: `HarnessNotFound -> 404`, `HarnessNameConflict -> 409`, `HarnessGraphError | ValidationError -> 422`. Module docstring explicitly notes last-writer-wins concurrency contract (R9, R10, R11, R13).
- `backend/app/main.py` (modified): instantiate `HarnessStore()` on app startup, attach to `app.state.harness_store`, `app.include_router(harnesses_router, dependencies=_auth)` after existing routers (R12).
- `backend/tests/test_harness_acceptance.py`: end-to-end test executing the analyst's R14 acceptance scenario verbatim — POST a 3-node/2-edge harness, GET it back, assert field-for-field equality, then load the on-disk `.cronos/harnesses/<slug>.yml`, parse it, construct a `Harness` model, and assert it equals the GET response (R14).

## Implementation plan

| ID | Type     | Depends on | Scope files (abridged)                                                  | Validation                                                       |
|----|----------|------------|-------------------------------------------------------------------------|------------------------------------------------------------------|
| I1 | data     | -          | backend/app/harnesses/__init__.py, model.py, tests/test_harness_model.py | cd backend && pytest tests/test_harness_model.py -v              |
| I2 | data     | I1         | backend/app/harnesses/validator.py, tests/test_harness_validator.py     | cd backend && pytest tests/test_harness_validator.py -v          |
| I3 | backend  | I1, I2     | backend/app/harnesses/store.py, tests/test_harness_store.py             | cd backend && pytest tests/test_harness_store.py -v              |
| I4 | backend  | I3         | backend/app/api/harnesses.py, tests/test_api_harnesses.py               | cd backend && pytest tests/test_api_harnesses.py -v              |
| I5 | infra    | I4         | backend/app/main.py, tests/test_harness_wiring.py                       | cd backend && pytest tests/test_harness_wiring.py -v             |
| I6 | backend  | I5         | backend/tests/test_harness_acceptance.py                                | cd backend && pytest tests/test_harness_acceptance.py -v         |

## Risks

| Risk                                                                                                                            | Severity | Mitigation                                                                                                                                                                                                  |
|---------------------------------------------------------------------------------------------------------------------------------|----------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| YAML round-trip type coercion in mixed-type data/variables dicts may violate R8 lossless guarantee.                             | high     | I3 uses yaml.safe_dump(default_flow_style=False, sort_keys=False); test asserts type equality via isinstance for int/float/bool/str inside data and variables.                                              |
| Cycle detection adaptation may miss self-loops or parallel-edge cycles relative to the storage.py BFS reference.                | high     | I2 includes explicit tests for self-loop, two-node cycle, three-node cycle, parallel edges, and fan-out; validator lives in backend/app/harnesses/validator.py independent of storage.py.                   |
| Slugify collision could silently overwrite an on-disk file if uniqueness is checked only in-memory.                             | medium   | I3 checks both _by_name AND on-disk filename presence; test creates "My Flow!" and "my flow" and asserts distinct filenames.                                                                                |
| HarnessStore must be on app.state before router include, else first request raises AttributeError.                              | medium   | I5 mirrors SpaceStore init order; test_harness_wiring.py asserts unauthenticated 401 + authenticated 200/404.                                                                                               |
| Pydantic field-validator ordering could mask cross-field validation errors and produce unclear 422 messages.                    | medium   | I1 places field-level constraints first, @model_validator(mode='after') last; tests assert specific error-message substrings for each error mode.                                                           |
| Concurrent CRUD vs future live-run (executor phase) could observe stale Harness models across await boundaries.                 | low      | R13 documented in harnesses.py docstring as last-writer-wins; callers must re-fetch after await. No runtime guard in this sub-goal — deferred to executor phase per analysis.                               |

## Assumptions

- Implementor will use Pydantic v2 (`@model_validator(mode="after")`, `Field(default_factory=dict)`) consistent with `backend/app/models.py`.
- `yaml.safe_dump(sort_keys=False, default_flow_style=False)` is acceptable for stable, human-readable on-disk YAML — same convention as `backend/app/space_storage.py::dump_space`.
- The harness API is space-scoped under `/api/spaces/{space_id}/harnesses`; no global / cross-space endpoints in this sub-goal.
- Pydantic ValidationError mapping to HTTP 422 is automatic in FastAPI when the request body model carries the constraint; for store-level errors (cycle, dangling edge raised post-Pydantic), the router catches and re-raises as `HTTPException(status_code=422, detail=...)` — consistent with `api/tasks.py:365-406`.
- Tests use `tmp_path` fixtures and an isolated space directory; no test depends on real on-disk data outside the pytest temp tree.
- `created_at` and `updated_at` carry tz-aware UTC datetimes (`datetime.now(tz=UTC)`) consistent with `storage.py::_iso`.

## Open questions

- None. Analysis open-questions section explicitly returned "None"; all design decisions trace to existing Cronos patterns the scout report cited by path:line.

## Next consumer brief

Read `iterations[]` directly — the table above mirrors it for humans only. Cross-iteration invariants the YAML cannot express:

1. **The slugify function defined in I3 (`store.py`) is the canonical filename derivation** — I4 must NOT re-implement slugify in the router; import from `app.harnesses.store`. I6's acceptance test asserts disk filename matches `slugify(name)`.
2. **`HarnessGraphError` is defined in I2 (`validator.py`) and re-raised from I3 (`store.py::create/update`)** — I4 catches it once at the router boundary. Do not introduce parallel exception hierarchies.
3. **The Pydantic models in I1 do NOT call the cycle validator from I2** — cycle check happens in I3 (store layer) because it requires full-graph context. I1 model_validator is field/reference checks only (R4); I2 validator is cycle check only (R5).
4. **R13 last-writer-wins requires an explicit module docstring in `backend/app/api/harnesses.py`** — review phase verifies this; implementor must not skip it.
5. **R14 acceptance test (I6) is the gating end-to-end check** — if it fails the entire sub-goal blocks. Run the analyst's acceptance scenario verbatim (POST 3-node/2-edge -> GET round-trip -> on-disk YAML parity).
