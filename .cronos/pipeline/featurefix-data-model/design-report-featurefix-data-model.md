---
cc_version: '1.0'
agent: pipeline-architect
slug: featurefix-data-model
phase: design
status: done
confidence: 0.86
inputs_used:
- memory:project_pipeline_architect_agent
- memory:project_pipeline_schemas
- memory:project_pipeline_verifier
- memory:project_arc_features_fixes_board_setup
- memory:project_architecture_key_modules
- .cronos/pipeline/featurefix-data-model/request.md
- .cronos/pipeline/featurefix-data-model/analysis-report-featurefix-data-model.md
- .cronos/pipeline/featurefix-data-model/scout-report-featurefix-data-model.md
- backend/app/pipeline/schemas/design.schema.yaml
- backend/app/storage.py
- backend/app/models.py
outputs_produced:
- .cronos/pipeline/featurefix-data-model/design-report-featurefix-data-model.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - backend/app/models.py
  - backend/app/storage.py
  - backend/app/pipeline/schemas/design.schema.yaml
  - .cronos/pipeline/featurefix-data-model/analysis-report-featurefix-data-model.md
  - .cronos/pipeline/featurefix-data-model/scout-report-featurefix-data-model.md
  excluded:
  - 'frontend/: has_ui=false in S1; UI deferred to S6 per arc-features-and-fixes plan'
  - 'backend/app/api/: no endpoints in S1; deferred to featurefix-api subgoal'
  - 'backend/app/worker.py, goal_sync.py: no worker/lifecycle hooks for feature_state
    in S1'
  - 'backend/tests/: pytest authorship owned by the test-architect phase that follows'
  strategies:
  - memory_retrieval
  - read_targeted
iterations:
- id: I1
  type: data
  scope_files:
  - backend/app/models.py
  - backend/app/feature_state.py
  validation_command: cd /data/spaces/cronos-development/backend && python -c "import
    app.models, app.feature_state" && cd /data/spaces/cronos-development/backend &&
    pytest tests/ -k "feature_state_enum or task_feature_fields or task_summary_feature_fields
    or task_type_extended" -q
  max_diff_lines: 200
  depends_on: []
- id: I2
  type: data
  scope_files:
  - backend/app/storage.py
  validation_command: cd /data/spaces/cronos-development/backend && python -c "import
    app.storage" && cd /data/spaces/cronos-development/backend && pytest tests/ -k
    "ensure_db_schema_feature or feature_columns_present or idx_tasks_space_realizes
    or migration_idempotent" -q
  max_diff_lines: 150
  depends_on:
  - I1
- id: I3
  type: data
  scope_files:
  - backend/app/storage.py
  validation_command: cd /data/spaces/cronos-development/backend && python -c "from
    app.storage import parse_file, dump_task" && cd /data/spaces/cronos-development/backend
    && pytest tests/ -k "parse_file_feature or dump_task_feature or feature_round_trip
    or legacy_md_backward_compat" -q
  max_diff_lines: 200
  depends_on:
  - I1
  - I2
- id: I4
  type: backend
  scope_files:
  - backend/app/feature_state.py
  - backend/app/storage.py
  validation_command: cd /data/spaces/cronos-development/backend && python -c "from
    app.feature_state import FEATURE_USER_TRANSITIONS, FEATURE_WORKER_TRANSITIONS"
    && cd /data/spaces/cronos-development/backend && pytest tests/ -k "feature_user_transitions
    or feature_worker_transitions" -q
  max_diff_lines: 120
  depends_on:
  - I1
- id: I5
  type: backend
  scope_files:
  - backend/app/storage.py
  validation_command: cd /data/spaces/cronos-development/backend && python -c "from
    app.storage import TaskStore; assert hasattr(TaskStore, 'transition_feature')"
    && cd /data/spaces/cronos-development/backend && pytest tests/ -k "transition_feature
    or feature_state_unchanged_task_state" -q
  max_diff_lines: 220
  depends_on:
  - I1
  - I2
  - I3
  - I4
- id: I6
  type: backend
  scope_files:
  - backend/app/storage.py
  validation_command: cd /data/spaces/cronos-development/backend && pytest tests/
    -k "next_feature_key or create_feature_assigns_key or fix_counter_independent
    or feat_per_space_isolation or non_feature_no_key" -q
  max_diff_lines: 180
  depends_on:
  - I5
- id: I7
  type: backend
  scope_files:
  - backend/app/storage.py
  validation_command: cd /data/spaces/cronos-development/backend && python -c "from
    app.storage import TaskStore; assert hasattr(TaskStore, 'feature_board')" && cd
    /data/spaces/cronos-development/backend && pytest tests/ -k "board_excludes_feature
    or counts_by_space_excludes_feature or feature_board_buckets" -q
  max_diff_lines: 220
  depends_on:
  - I6
- id: I8
  type: backend
  scope_files:
  - backend/app/storage.py
  - backend/app/models.py
  validation_command: cd /data/spaces/cronos-development/backend && python -c "from
    app.storage import TaskStore; assert hasattr(TaskStore, 'set_realizes') and hasattr(TaskStore,
    'realizing_items')" && cd /data/spaces/cronos-development/backend && pytest tests/
    -k "set_realizes or realizing_items or validate_realizes" -q
  max_diff_lines: 200
  depends_on:
  - I5
- id: I9
  type: data
  scope_files:
  - backend/app/storage.py
  validation_command: cd /data/spaces/cronos-development/backend && pytest tests/
    -k "db_upsert_feature_persists or reload_all_feature_persists or feature_row_after_reload"
    -q
  max_diff_lines: 120
  depends_on:
  - I5
risks:
- description: Type-guard widening in parse_file (R4) could silently downgrade unknown
    task types to "task" because the existing pattern coerces invalid types to "task"
    rather than raising. If the whitelist is extended naively, a typo like "feaure"
    would silently become "task" and any feature-specific fields would be orphaned
    in YAML but invisible in the model.
  severity: medium
  mitigation: Implementor must preserve the existing coerce-to-task semantics for
    unknown types and add the two new literals to the whitelist explicitly. I3 test
    coverage must include both a positive (feature/fix accepted) and negative (unknown
    type coerced or rejected) case. Document the chosen behaviour as a comment next
    to the widened guard in parse_file.
- description: Locking deadlock in _next_feature_key. The helper is called from inside
    create() while self._lock is already held; if it is later refactored to async
    or to re-acquire the lock, the store will deadlock on the first feature creation.
  severity: high
  mitigation: I5 implements _next_feature_key as a synchronous private method that
    reads self._by_id directly without acquiring any lock. Docstring must state the
    "self._lock must already be held by caller" precondition. I6 test coverage exercises
    multiple back-to-back feature creations in a single space — a deadlock would surface
    as a hung pytest run, not a wrong result.
- description: SQLite INSERT tuple drift between _db_upsert and reload_all. Both paths
    must list the new six columns in identical order; a copy-paste error in one path
    silently defaults new fields to NULL after reload_all, breaking R7 end-to-end
    persistence.
  severity: medium
  mitigation: Implementor introduces a module-level constant (e.g. _TASK_INSERT_COLS)
    or a helper that both _db_upsert and reload_all consume, so column order cannot
    drift. I9 validation creates a feature task, calls reload_all, and re-queries
    SQLite to assert the row still has the expected feature_key and feature_state
    values (not NULL).
- description: FeatureState/TaskState name collision (both enums have BACKLOG, WAITING,
    DONE members). Loosely typed code that accepts a "state-like" argument could mix
    them, leading to a feature being moved to TaskState.DONE via transition_feature
    or vice versa.
  severity: medium
  mitigation: I4 isolates FEATURE_USER_TRANSITIONS / FEATURE_WORKER_TRANSITIONS in
    feature_state.py, typed strictly as set[tuple[FeatureState, FeatureState]]. transition_feature
    accepts new_feature_state typed as FeatureState (not str or TaskState). I5 test
    coverage asserts task.state is unchanged after a successful transition_feature
    call, catching enum cross-wiring at the model level.
- description: realizes index/column race during first migration. The idempotent ALTER
    TABLE pattern is safe but realizing_items must not depend on the SQLite index
    existing before _ensure_db_schema has run; otherwise queries against a fresh database
    could miss the index.
  severity: low
  mitigation: realizing_items is implemented as an in-memory scan of self._by_id (not
    a SQLite SELECT). _ensure_db_schema is invoked by reload_all before any _db_upsert.
    The index exists for future query-based variants but is not load-bearing in S1.
metrics:
  tool_calls: 12
  files_read: 7
  memory_hits: 5
  iterations_planned: 9
---

## Summary

S1 extends the Cronos task data model with two new types (`feature`, `fix`),
a five-state `FeatureState` enum (backlog/processing/planned/waiting/done),
six optional flat fields on `Task`/`TaskSummary`, and a per-space sequential
`FEAT-NNN`/`FIX-NNN` numbering scheme — all confined to `backend/app/models.py`,
`backend/app/storage.py`, and an optional new `backend/app/feature_state.py`.
The plan is decomposed into nine atomic iterations, topologically ordered as
model-first (I1) then schema/serialization/transitions (I2, I3, I4) then
mutation surface (I5) then numbering and query layers (I6, I7) then realizes
(I8) and an end-to-end persistence cross-check (I9). The DAG is intentionally
wide at the model layer so the storage path (I3, I4) can be built in parallel
where dependencies allow. The key tradeoff is co-locating the transition
frozensets in a new `feature_state.py` module to keep `FeatureState`
importable without forcing a `TaskStore` import, at the cost of one extra
file in the diff.

## Components

### Data
- `backend/app/models.py` — `TaskType` literal extended to include `"feature"`
  and `"fix"`; new `FeatureState(str, Enum)` with five members; six new
  optional fields added to both `Task` and `TaskSummary`. `summarize()` in
  storage.py is updated to copy the new fields onto `TaskSummary`.
- `backend/app/feature_state.py` (new) — `FEATURE_USER_TRANSITIONS` and
  `FEATURE_WORKER_TRANSITIONS` frozensets of `(FeatureState, FeatureState)`
  tuples. Pure data module; no imports from `storage.py`.
- `backend/app/storage.py` — `parse_file` widens its type-guard whitelist
  (currently `("task", "goal", "issue")`) to also accept `"feature"`, `"fix"`,
  and deserializes the six new fields via `meta.get()`; `dump_task` serializes
  them. `_ensure_db_schema` adds six nullable columns plus the
  `idx_tasks_space_realizes` index via the existing idempotent ALTER loop.

### Backend
- `backend/app/storage.py::_next_feature_key(space_id, type)` — synchronous
  private helper invoked from inside `self._lock` in `create()`. Scans
  `self._by_id`, parses the numeric suffix of existing `feature_key` values
  matching the prefix, returns `f"{prefix}-{n:03d}"`. No counter file.
- `backend/app/storage.py::create()` — when `type in ("feature", "fix")`,
  assigns `feature_key` via `_next_feature_key` and sets
  `feature_state=FeatureState.BACKLOG`; otherwise leaves both as `None`.
  Widens the `type not in (...)` guard to accept the two new literals.
- `backend/app/storage.py::transition_feature(task_id, new_feature_state, *, allowed)`
  — new async method modelled on `transition()` but operating exclusively on
  `task.feature_state`. Never mutates `task.state`. Validates
  `(current, new) in allowed` and persists via the `model_copy + atomic_write +
  _reindex_locked` pattern.
- `backend/app/storage.py::feature_board(space_id)` — returns a
  `dict[FeatureState, list[TaskSummary]]` of feature/fix tasks bucketed by
  `feature_state`. Excludes regular task types.
- `backend/app/storage.py::realizing_items(feature_id)` — returns
  `list[TaskSummary]` whose `realizes == feature_id`. Implemented as an
  in-memory scan of `self._by_id`; the new SQLite index is future-proofing.
- `backend/app/storage.py::set_realizes(item_id, feature_id | None)` — mirrors
  `set_parent`. Uses a new module-level `validate_realizes()` helper that
  enforces same-space, target-is-`feature`-or-`fix`, and no-self-reference.
  Passing `None` clears the field with no validation.
- `backend/app/storage.py::board()` and `::counts_by_space()` — add a
  `task.type in ("feature", "fix"): continue` guard before lane assignment /
  bucket increment.
- `backend/app/storage.py::_db_upsert` and `reload_all` INSERT paths — both
  extend the column list and tuple in identical order to include the six new
  fields. The implementor introduces a single source of truth (module-level
  constant or shared helper) to prevent drift.

<!-- No ### Frontend sub-section: has_ui=false for S1. -->

## Implementation plan

| ID  | Type    | Depends on        | Scope files (abridged)                                          | Validation (pytest -k narrow)                          |
|-----|---------|-------------------|-----------------------------------------------------------------|--------------------------------------------------------|
| I1  | data    | -                 | backend/app/models.py, backend/app/feature_state.py             | `-k "feature_state_enum or task_feature_fields or ..."`  |
| I2  | data    | I1                | backend/app/storage.py                                          | `-k "ensure_db_schema_feature or feature_columns_present or ..."` |
| I3  | data    | I1, I2            | backend/app/storage.py                                          | `-k "parse_file_feature or dump_task_feature or legacy_md_backward_compat"` |
| I4  | backend | I1                | backend/app/feature_state.py, backend/app/storage.py            | `-k "feature_user_transitions or feature_worker_transitions"` |
| I5  | backend | I1, I2, I3, I4    | backend/app/storage.py                                          | `-k "transition_feature or feature_state_unchanged_task_state"` |
| I6  | backend | I5                | backend/app/storage.py                                          | `-k "next_feature_key or create_feature_assigns_key or ..."` |
| I7  | backend | I6                | backend/app/storage.py                                          | `-k "board_excludes_feature or counts_by_space_excludes_feature or feature_board_buckets"` |
| I8  | backend | I5                | backend/app/storage.py, backend/app/models.py                   | `-k "set_realizes or realizing_items or validate_realizes"` |
| I9  | data    | I5                | backend/app/storage.py                                          | `-k "db_upsert_feature_persists or reload_all_feature_persists or feature_row_after_reload"` |

The full one-liner validation commands (including the smoke `python -c "import
..."` prefix) are in the YAML `iterations[].validation_command` — that is the
machine-readable source of truth; this table abridges them for human reading.
All commands assume CWD `/data/spaces/cronos-development/backend`. The
expected pytest test names are reserved by this design; the test-architect
phase that follows is responsible for authoring tests under those names.

## Risks

| Risk                                                                | Severity | Mitigation                                                                                                            |
|---------------------------------------------------------------------|----------|-----------------------------------------------------------------------------------------------------------------------|
| Type-guard widening silently coerces unknown types to "task"        | medium   | Preserve coerce-to-task semantics; I3 covers positive + negative cases; comment next to widened guard                  |
| _next_feature_key deadlock if accidentally re-acquires self._lock   | high     | Sync (non-async) helper; precondition in docstring; I6 exercises multi-feature creation back-to-back                  |
| INSERT tuple drift between _db_upsert and reload_all                | medium   | Single shared column-order source (module constant); I9 reload_all + SQLite re-query asserts persistence              |
| FeatureState/TaskState name collision (shared member names)         | medium   | Strict typing on transition_feature signature; I5 asserts task.state unchanged after feature transition               |
| realizes index/column race during first migration                   | low      | _ensure_db_schema runs before any _db_upsert; realizing_items uses in-memory scan, not the SQLite index                |

## Assumptions

- **Optional feature_state.py is taken.** The request permits this; the design
  uses it to host the two transition frozensets so they stay importable
  without pulling in `TaskStore`. The `FeatureState` enum itself remains in
  `models.py` per analysis assumption.
- **realizing_items implementation is in-memory.** The new SQLite index is
  created (per R6) but the method scans `self._by_id`. This avoids an async
  sqlite trip in the hot path; the index is future-proofing for the API
  phase.
- **Numbering is per-space + per-type.** A space's `FEAT-` counter is
  independent of its `FIX-` counter and of any other space's counters
  (analysis R11 — explicit acceptance criterion).
- **transition_feature does not touch task.state.** Distinct from `transition()`
  (analysis R10). Worker hooks that bridge `task.state` → `task.feature_state`
  are deferred to a later subgoal.
- **dump_task may emit YAML nulls.** The existing convention (e.g. `pr_url`
  serialized as null when None) is preserved. parse_file's `meta.get(...) or
  None` idiom round-trips nulls correctly.
- **No new SQLite tables.** Per the parent goal's Locked decisions — index
  columns only on the existing `tasks` table.
- **Test names are reserved by this design.** Test-architect (next phase)
  authors pytest tests under the names referenced in `validation_command`
  via `-k`. The implementor is not responsible for writing them.

## Open questions

- None. All 15 requirements from the analysis report have explicit iteration
  coverage and validation; the optional `feature_state.py` module is taken
  by this design.

## Next consumer brief

The implementation agent should treat `iterations[]` as the machine-readable
plan, with `scope_files` as a hard boundary (any file outside `models.py`,
`storage.py`, `feature_state.py` is out-of-scope — no test authorship, no
API edits). Read in YAML order:

1. **`iterations[].scope_files`** — exactly which file(s) the iteration may
   touch. Three iterations (I1, I4, I8) modify two files; the rest are
   `storage.py`-only.
2. **`iterations[].validation_command`** — a Bash one-liner that first imports
   the changed module (smoke test for syntax/import errors) and then runs
   `pytest tests/ -k "..."` against a narrow set of test names reserved by
   this design. The test-architect phase authors tests under those names;
   the implementor relies on them existing when validation runs.
3. **`risks[]`** — the `_next_feature_key` deadlock risk (severity=high) is
   the only high-severity item; preserve the "lock-must-be-held"
   precondition in the helper's docstring.

Cross-iteration invariants the implementor must preserve verbatim:

- **Column order in `_db_upsert` and `reload_all` MUST match exactly.** Use a
  module-level `_TASK_INSERT_COLS` constant (or equivalent shared helper)
  consumed by both call sites — this is the load-bearing fix for the I9
  end-to-end check.
- **`FeatureState` and `TaskState` are distinct enums.** Never accept one
  where the other is expected; `transition_feature` is typed against
  `FeatureState` only.
- **`feature_key` is immutable post-create.** No mutation path is added; do
  not expose one even as a private helper.
- **`parse_file` widening preserves coerce-to-task semantics for unknown
  types.** The existing pattern (`if task_type not in (...): task_type =
  "task"`) is extended, not replaced with a raise.

Traceability — every analysis requirement maps to at least one iteration:

| Analysis req | Iterations |
|--------------|------------|
| R1 (TaskType extended)                                | I1     |
| R2 (FeatureState enum)                                | I1     |
| R3 (six fields on Task + TaskSummary)                 | I1     |
| R4 (parse_file widened guard + meta.get)              | I3     |
| R5 (dump_task round-trip)                             | I3     |
| R6 (SQLite migration + realizes index)                | I2     |
| R7 (both INSERT paths)                                | I2, I9 |
| R8 (FEATURE_USER_TRANSITIONS)                         | I4     |
| R9 (FEATURE_WORKER_TRANSITIONS)                       | I4     |
| R10 (transition_feature method)                       | I5     |
| R11 (_next_feature_key per-space per-type)            | I5, I6 |
| R12 (create() assigns key + initial state)            | I5, I6 |
| R13 (board/counts_by_space exclude feature+fix)       | I7     |
| R14 (feature_board + realizing_items)                 | I7, I8 |
| R15 (set_realizes with guards)                        | I8     |
