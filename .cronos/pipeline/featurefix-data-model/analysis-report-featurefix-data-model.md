---
cc_version: '1.0'
agent: pipeline-analyst
slug: featurefix-data-model
phase: analysis
status: done
confidence: 0.92
inputs_used:
- memory:project_pipeline_analyst_agent
- memory:project_pipeline_schemas
- memory:project_pipeline_verifier
- .cronos/pipeline/featurefix-data-model/scout-report-featurefix-data-model.md
- backend/app/pipeline/schemas/analysis.schema.yaml
outputs_produced:
- .cronos/pipeline/featurefix-data-model/analysis-report-featurefix-data-model.md
blockers: []
next_consumer: design
request: "# S1 — Data model: types + feature_state machine + numbering + realizes\n\
  \n**Title:** `Features&Fixes/S1 — model, feature_state, numbering, realizes` · **has_ui:**\
  \ no\n\nExtend `Task` model + storage (no API, no UI).\n- models.py: add `\"feature\"\
  `/`\"fix\"` to `TaskType`; new `FeatureState(str,Enum)` =\n  `backlog/processing/planned/waiting/done`.\
  \ Flat fields on `Task`/`TaskSummary`:\n  `feature_state: FeatureState|None`, `feature_key:\
  \ str|None` (`FEAT-001`), `realizes: str|None`,\n  `issue_number: int|None`, `issue_url:\
  \ str|None`, `proposed_issue_path: str|None` (mirror\n  `pr_url`/`proposed_pr_path`).\n\
  - storage.py: `parse_file`/`dump_task` serialize the new keys (optional via `meta.get`\
  \ → old files\n  unchanged); **widen the type guards** (note 2). SQLite: add nullable\
  \ cols\n  `feature_state/feature_key/realizes` via the idempotent `ALTER TABLE ADD\
  \ COLUMN` loop (~418-426) +\n  index `idx_tasks_space_realizes(space_id, realizes)`;\
  \ update **both** insert paths (`_db_upsert`\n  ~437-455 and `reload_all` ~520-533).\n\
  - **Transition tables** (like storage.py:41-57): `FEATURE_USER_TRANSITIONS` (`backlog->processing`,\n\
  \  `processing->backlog`, `planned->processing`, `waiting->processing`, `waiting->planned`,\
  \ `planned->done`,\n  `done->backlog`) and `FEATURE_WORKER_TRANSITIONS` (`processing->planned`,\
  \ `processing->waiting`,\n  `planned->waiting`, `waiting->planned`, `planned->done`).\
  \ New `transition_feature(task_id, new_state,\n  allowed)` — do **not** reuse `transition()`.\n\
  - `_next_feature_key(space_id, type)` = `max(existing per space+type)+1`, computed\
  \ **inside `self._lock`**\n  in `create()` (no counter file), zero-padded to 3.\n\
  - **Exclude feature/fix from `board()`/`counts_by_space()`** (note 1); add `feature_board(space_id)`\n\
  \  (bucket by `feature_state`) + `realizing_items(feature_id)`.\n- `set_realizes(item_id,\
  \ feature_id|None)` (mirror `set_parent`) with a same-space + target-is-feature/fix\n\
  \  guard (model on `validate_parent`).\n\n**Scope files:** models.py, storage.py\
  \ (+ optional `feature_state.py`).\n**Acceptance:** creating a `feature` in a git-linked\
  \ space → `feature_key=FEAT-001`,\n`feature_state=backlog`, `state=backlog`, parseable\
  \ MD + SQLite row; FEAT/FIX counters independent per\nspace; existing MD files load\
  \ unchanged after `reload_all`; feature/fix excluded from `board()`; the\ntransition\
  \ table is enforced; `set_realizes` rejects cross-space/non-feature targets."
has_ui: false
coverage_summary:
  searched:
  - backend/app/models.py
  - backend/app/storage.py
  - backend/app/pipeline/schemas/analysis.schema.yaml
  excluded:
  - 'frontend/: no UI in S1; frontend changes deferred to S6'
  - 'backend/app/api/: no API endpoints in S1 scope'
  - 'backend/tests/: test authorship is out of scope for analysis'
  strategies:
  - memory_retrieval
  - read_targeted
traceability:
- requirement_id: R1
  statement: TaskType is extended to include the literals "feature" and "fix" alongside
    the existing "task", "goal", "issue" values.
  acceptance_criteria:
  - Given models.py, when TaskType is inspected, then Literal["task", "goal", "issue",
    "feature", "fix"] is the declared type.
  - Creating a task with type="feature" or type="fix" does not raise a Pydantic validation
    error.
  verifying_phase: test
  confidence: 0.98
- requirement_id: R2
  statement: 'A new FeatureState enum exists with exactly five members: backlog, processing,
    planned, waiting, done.'
  acceptance_criteria:
  - FeatureState is a str+Enum with members BACKLOG, PROCESSING, PLANNED, WAITING,
    DONE (values matching lowercase strings).
  - FeatureState.DONE != TaskState.DONE — they are distinct enum types and must not
    be interchangeable in type-checked code.
  verifying_phase: test
  confidence: 0.97
- requirement_id: R3
  statement: 'Task and TaskSummary models carry six new optional fields: feature_state,
    feature_key, realizes, issue_number, issue_url, proposed_issue_path — all default
    to None.'
  acceptance_criteria:
  - 'Task model has fields feature_state: FeatureState | None = None, feature_key:
    str | None = None, realizes: str | None = None, issue_number: int | None = None,
    issue_url: str | None = None, proposed_issue_path: str | None = None.'
  - TaskSummary mirrors all six fields with identical types and defaults.
  - Constructing Task() or TaskSummary() without supplying any of these fields succeeds
    and leaves them as None.
  verifying_phase: test
  confidence: 0.96
- requirement_id: R4
  statement: parse_file deserializes all six new fields from YAML frontmatter using
    meta.get() with None defaults, and widens the type guard to accept "feature" and
    "fix" as valid task types.
  acceptance_criteria:
  - Given an existing .md file without any new keys, parse_file returns a Task with
    all six new fields as None (backward compatibility).
  - 'Given a .md file with feature_state: processing in frontmatter, parse_file returns
    a Task with feature_state=FeatureState.PROCESSING.'
  - 'Given a .md file with type: feature, parse_file does not raise a type-guard rejection
    error.'
  - 'An invalid feature_state string (e.g. feature_state: invalid) causes parse_file
    to raise a descriptive validation error.'
  verifying_phase: test
  confidence: 0.95
- requirement_id: R5
  statement: dump_task serializes all six new fields into the YAML frontmatter meta
    dict such that round-tripping through parse_file produces identical field values.
  acceptance_criteria:
  - 'Given a Task with feature_key="FEAT-001" and feature_state=FeatureState.BACKLOG,
    dump_task writes feature_key: FEAT-001 and feature_state: backlog to the file.'
  - Given a Task with all six new fields as None, the dumped file can be re-parsed
    by parse_file to the same Task (round-trip integrity).
  verifying_phase: test
  confidence: 0.93
- requirement_id: R6
  statement: The SQLite tasks table is migrated idempotently to include nullable columns
    feature_state (TEXT), feature_key (TEXT), realizes (TEXT), issue_number (INTEGER),
    issue_url (TEXT), proposed_issue_path (TEXT), and an index idx_tasks_space_realizes
    on (space_id, realizes).
  acceptance_criteria:
  - Running the migration twice against the same database does not raise an OperationalError.
  - After migration, the tasks table schema includes all six new columns.
  - The index idx_tasks_space_realizes exists after migration.
  verifying_phase: test
  confidence: 0.96
- requirement_id: R7
  statement: Both _db_upsert and reload_all INSERT paths write all six new fields
    to the database, using None for rows where the fields are absent.
  acceptance_criteria:
  - After creating a feature task and calling reload_all, the SQLite row contains
    the correct feature_key and feature_state values.
  - _db_upsert called with a Task that has feature_key="FEAT-001" persists feature_key="FEAT-001"
    in the database.
  - A task loaded via reload_all from a .md file with no new fields has NULL for all
    six new columns in SQLite.
  verifying_phase: test
  confidence: 0.94
- requirement_id: R8
  statement: 'FEATURE_USER_TRANSITIONS is a module-level constant containing exactly
    the seven permitted user-initiated feature state transitions: backlog->processing,
    processing->backlog, planned->processing, waiting->processing, waiting->planned,
    planned->done, done->backlog.'
  acceptance_criteria:
  - FEATURE_USER_TRANSITIONS is a frozenset or set of (FeatureState, FeatureState)
    tuples.
  - All seven transitions listed in the request are present; no additional transitions
    are included.
  - Calling transition_feature with (backlog, processing) and allowed=FEATURE_USER_TRANSITIONS
    succeeds.
  - Calling transition_feature with (backlog, done) and allowed=FEATURE_USER_TRANSITIONS
    raises a state-machine error.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R9
  statement: 'FEATURE_WORKER_TRANSITIONS is a module-level constant containing exactly
    the five permitted worker-initiated feature state transitions: processing->planned,
    processing->waiting, planned->waiting, waiting->planned, planned->done.'
  acceptance_criteria:
  - FEATURE_WORKER_TRANSITIONS is a frozenset or set of (FeatureState, FeatureState)
    tuples.
  - All five transitions listed in the request are present; no additional transitions
    are included.
  - Calling transition_feature with (processing, planned) and allowed=FEATURE_WORKER_TRANSITIONS
    succeeds.
  - Calling transition_feature with (backlog, processing) and allowed=FEATURE_WORKER_TRANSITIONS
    raises a state-machine error.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R10
  statement: transition_feature(task_id, new_feature_state, *, allowed) is a new async
    method on TaskStore that validates the (current_feature_state, new_feature_state)
    pair against the provided allowed set and updates the task's feature_state atomically,
    without touching task.state.
  acceptance_criteria:
  - transition_feature is defined separately from transition() and operates only on
    task.feature_state.
  - Given a task with feature_state=backlog, calling transition_feature with new_state=processing
    and allowed=FEATURE_USER_TRANSITIONS updates feature_state to processing and leaves
    task.state unchanged.
  - Given a disallowed transition, transition_feature raises an exception without
    modifying the task.
  - The updated task is persisted atomically using the model_copy + atomic_write +
    _reindex_locked pattern.
  verifying_phase: test
  confidence: 0.93
- requirement_id: R11
  statement: _next_feature_key(space_id, task_type) computes the next sequential FEAT-NNN
    or FIX-NNN key by scanning existing tasks in the space for the given type, finding
    the maximum numeric suffix, and returning the next value zero-padded to three
    digits; it is invoked inside self._lock in create().
  acceptance_criteria:
  - Given a space with no existing feature tasks, _next_feature_key returns "FEAT-001"
    for type="feature".
  - Given a space with existing feature_key values FEAT-001 and FEAT-003, _next_feature_key
    returns "FEAT-004" (max+1).
  - 'FEAT and FIX counters are independent: a space with FEAT-005 and FIX-001 returns
    "FIX-002" for type="fix".'
  - 'Counters are per-space: features in space A do not affect FEAT numbering in space
    B.'
  verifying_phase: test
  confidence: 0.95
- requirement_id: R12
  statement: create() assigns feature_key and sets feature_state=FeatureState.BACKLOG
    automatically when task type is "feature" or "fix"; regular task types receive
    feature_key=None and feature_state=None.
  acceptance_criteria:
  - Given type="feature" at create time, the returned Task has feature_key matching
    FEAT-NNN format and feature_state=FeatureState.BACKLOG.
  - Given type="fix" at create time, the returned Task has feature_key matching FIX-NNN
    format and feature_state=FeatureState.BACKLOG.
  - Given type="task" at create time, the returned Task has feature_key=None and feature_state=None.
  - FEAT-001 is assigned to the first feature in a given space.
  verifying_phase: test
  confidence: 0.96
- requirement_id: R13
  statement: board() and counts_by_space() exclude tasks with type="feature" or type="fix"
    from their results.
  acceptance_criteria:
  - Given a space with one task, one goal, and one feature, board() returns buckets
    containing only the task and goal.
  - Given a space with one task and one fix, counts_by_space() returns counts that
    include only the task.
  - The exclusion is enforced via a type guard rather than relying on feature_state
    being non-None.
  verifying_phase: test
  confidence: 0.97
- requirement_id: R14
  statement: feature_board(space_id) returns a dict keyed by FeatureState with TaskSummary
    lists for all feature and fix tasks bucketed by their feature_state; realizing_items(feature_id)
    returns all TaskSummary objects whose realizes field equals feature_id.
  acceptance_criteria:
  - 'Given a space with two features (one backlog, one planned) and one fix (processing),
    feature_board returns three non-empty buckets: FeatureState.BACKLOG, FeatureState.PLANNED,
    FeatureState.PROCESSING.'
  - Tasks of type "task", "goal", or "issue" do not appear in feature_board results.
  - realizing_items(feature_id) returns all TaskSummary objects whose realizes field
    equals feature_id.
  - realizing_items returns an empty list when no tasks realize the given feature_id.
  verifying_phase: test
  confidence: 0.93
- requirement_id: R15
  statement: 'set_realizes(item_id, feature_id | None) sets the realizes field on
    the item and enforces: (a) item and feature are in the same space, (b) feature_id
    target has type "feature" or "fix", (c) item_id != feature_id.'
  acceptance_criteria:
  - Given item and feature in the same space with feature.type="feature", set_realizes
    succeeds and the item's realizes field is updated atomically.
  - Given feature_id pointing to a task with type="task", set_realizes raises a validation
    error.
  - Given item and feature in different spaces, set_realizes raises a validation error.
  - Given item_id == feature_id, set_realizes raises a self-reference error.
  - Calling set_realizes(item_id, None) clears the realizes field without validation
    errors.
  verifying_phase: test
  confidence: 0.95
metrics:
  tool_calls: 6
  files_read: 2
  memory_hits: 3
---

## Summary

S1 extends the Cronos data model to support two new task types — "feature" and "fix" — each with a dedicated five-state lifecycle (FeatureState), an auto-assigned sequential key (FEAT-NNN / FIX-NNN), and a `realizes` association linking ordinary tasks to features. Storage changes are confined to `models.py` and `storage.py`: new fields on Task/TaskSummary, idempotent SQLite column additions, backward-compatible parse/dump serialization, isolated transition tables and transition function, and two new query methods (feature_board, realizing_items) plus set_realizes. Feature and fix tasks are excluded from the existing board() and counts_by_space() views to preserve the current Kanban semantics.

## Scope

### In scope
- Extend TaskType with "feature" and "fix" literals (models.py)
- Define FeatureState enum with five members: backlog, processing, planned, waiting, done (models.py)
- Add six optional fields to Task and TaskSummary: feature_state, feature_key, realizes, issue_number, issue_url, proposed_issue_path (models.py)
- Widen parse_file type guard and deserialize new fields via meta.get() (storage.py)
- Serialize new fields in dump_task (storage.py)
- Idempotent SQLite ALTER TABLE for six new nullable columns (storage.py)
- Add idx_tasks_space_realizes index (storage.py)
- Update _db_upsert INSERT path with new columns (storage.py)
- Update reload_all INSERT path with new columns (storage.py)
- Define FEATURE_USER_TRANSITIONS constant with seven permitted user transitions (storage.py)
- Define FEATURE_WORKER_TRANSITIONS constant with five permitted worker transitions (storage.py)
- Implement transition_feature() separate from transition(), operating on feature_state (storage.py)
- Implement _next_feature_key() helper: sequential, lock-safe, zero-padded, per-space+type (storage.py)
- Assign feature_key and initial feature_state in create() for feature/fix types (storage.py)
- Exclude feature/fix from board() and counts_by_space() (storage.py)
- Implement feature_board(space_id) method bucketed by FeatureState (storage.py)
- Implement realizing_items(feature_id) method (storage.py)
- Implement set_realizes(item_id, feature_id | None) with same-space and target-type validation (storage.py)

### Out of scope
- API endpoints for feature/fix CRUD, transitions, or set_realizes (deferred to S2)
- Frontend UI for feature tracking, feature board, or realizes relationships (deferred to S6)
- Worker/agent integration with feature lifecycle (e.g. auto-transition on task completion)
- Test file authorship (60% coverage floor enforced separately)
- Changes to goal_sync.py, worker.py, or agent.py

### Deferred
- API layer exposing transition_feature, feature_board, realizing_items, set_realizes (S2)
- Worker hooks to auto-advance feature_state based on child task outcomes
- GitHub issue integration using issue_number, issue_url, proposed_issue_path (fields are modeled now; sync logic is deferred)
- Frontend feature board page and realizes relationship UI (S6)
- Cycle-detection for realizes chains if transitivity is later introduced

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | TaskType extended to include "feature" and "fix" literals |
| R2 | FeatureState enum defined with five members |
| R3 | Task and TaskSummary carry six new optional fields |
| R4 | parse_file handles new fields with backward-compatible meta.get() and widened type guard |
| R5 | dump_task serializes all six new fields round-trip correctly |
| R6 | SQLite migration adds six nullable columns and realizes index idempotently |
| R7 | Both _db_upsert and reload_all INSERT paths write all six new fields |
| R8 | FEATURE_USER_TRANSITIONS constant with seven permitted user transitions |
| R9 | FEATURE_WORKER_TRANSITIONS constant with five permitted worker transitions |
| R10 | transition_feature() method: separate from transition(), operates on feature_state only |
| R11 | _next_feature_key() helper: sequential, lock-safe, zero-padded, per-space+type |
| R12 | create() assigns feature_key and sets feature_state=backlog for feature/fix types |
| R13 | board() and counts_by_space() exclude feature/fix tasks |
| R14 | feature_board() and realizing_items() new query methods |
| R15 | set_realizes() with same-space and target-type validation |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). The body summary below mirrors them in compact form for the human reader.

- R1 — TaskType literal includes "feature" and "fix"; Pydantic accepts both without error
- R2 — FeatureState has exactly five members; is distinct from TaskState
- R3 — All six fields present on Task and TaskSummary with None defaults; construction without them succeeds
- R4 — Old .md files parse unchanged; new fields deserialized correctly; invalid feature_state rejected
- R5 — Round-trip: dump then parse yields identical field values for all six new fields
- R6 — Migration runs twice without error; all six columns and the realizes index present after migration
- R7 — Both insert paths persist new fields; reload_all from legacy .md leaves them NULL
- R8 — Seven transitions present; disallowed transitions raise errors
- R9 — Five transitions present; disallowed transitions raise errors
- R10 — transition_feature operates on feature_state only; disallowed transition raises without mutation; persistence atomic
- R11 — First feature gets FEAT-001; max+1 logic correct; FEAT/FIX counters independent; counters are per-space
- R12 — feature/fix creation yields correct key format and initial feature_state=backlog; non-feature types get None
- R13 — board() and counts_by_space() results exclude feature/fix tasks; exclusion is type-guard based
- R14 — feature_board() buckets by feature_state; excludes non-feature types; realizing_items() returns correct subset
- R15 — Valid set_realizes succeeds atomically; cross-space, wrong-type, and self-reference cases raise errors; None clears the field

## Traceability

The full requirement -> acceptance criteria -> verifying_phase map is the YAML `traceability[]` array. Downstream agents read the YAML directly; this section exists so a human reader sees the same routing table without parsing YAML.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | TaskType is extended to include "feature" and "fix" alongside the existing three values. |
| R2 | test | A new FeatureState enum exists with exactly five members: backlog, processing, planned, waiting, done. |
| R3 | test | Task and TaskSummary carry six new optional fields all defaulting to None. |
| R4 | test | parse_file deserializes new fields via meta.get() with backward compatibility and widened type guard. |
| R5 | test | dump_task serializes all six new fields; round-trip through parse_file is lossless. |
| R6 | test | SQLite migration adds six nullable columns and realizes index idempotently. |
| R7 | test | Both _db_upsert and reload_all INSERT paths write all six new fields. |
| R8 | test | FEATURE_USER_TRANSITIONS contains exactly the seven permitted user-initiated transitions. |
| R9 | test | FEATURE_WORKER_TRANSITIONS contains exactly the five permitted worker-initiated transitions. |
| R10 | test | transition_feature() is separate from transition(), operates on feature_state only, persists atomically. |
| R11 | test | _next_feature_key() computes sequential zero-padded key inside self._lock, per-space+type. |
| R12 | test | create() assigns feature_key and sets feature_state=backlog for feature/fix; None for others. |
| R13 | test | board() and counts_by_space() exclude tasks with type="feature" or "fix". |
| R14 | test | feature_board() buckets by feature_state; realizing_items() returns tasks where realizes==feature_id. |
| R15 | test | set_realizes() enforces same-space, target-is-feature/fix, and no-self-reference constraints. |

## Assumptions

- has_ui=false rationale: the request explicitly states "no API, no UI" and all scope files are backend-only (models.py, storage.py); the scout confirms no frontend changes in S1.
- FeatureState.WAITING is a distinct state from TaskState.WAITING. The two enums share member names but are not interchangeable; code must never pass a FeatureState where a TaskState is expected.
- feature_key is immutable after creation. No mutation path for feature_key is required in S1.
- The realizes field is non-transitive and non-cyclic in S1. A task realizes at most one feature; cycle detection is not required.
- feature_state is initialized to FeatureState.BACKLOG at create() time for all feature/fix tasks, per the acceptance criteria in the request.
- dump_task may serialize None as YAML null or omit the key; either is acceptable as long as parse_file round-trips correctly, consistent with existing optional-field handling.
- The issue_number, issue_url, and proposed_issue_path fields are modeled as nullable storage only in S1; no business logic or sync is attached to them.
- transition_feature receives its allowed set as a parameter so it can be called with either FEATURE_USER_TRANSITIONS or FEATURE_WORKER_TRANSITIONS, matching the pattern of transition().
- The optional feature_state.py module is at the implementor's discretion; all 15 requirements are satisfiable from within models.py and storage.py alone.

## Open questions

- None.

## Next consumer brief

The design agent should read `traceability[]` (15 requirements, all `verifying_phase: test`) and `## Scope` for the exact change surface. Key decision points:

1. Module split: the request permits an optional feature_state.py for the FeatureState enum and transition tables. The design agent should decide whether to co-locate everything in models.py/storage.py or extract a thin feature_state.py module imported by both, whichever minimises circular imports.

2. transition_feature placement: must be a method on TaskStore (not a module-level function) to access self._lock and self._by_id, matching the transition() pattern at storage.py lines 722-763.

3. _next_feature_key scope: this helper must be called while self._lock is already held inside create(); it should be a non-async method or an inner expression to avoid async deadlock.

4. INSERT column ordering: _db_upsert and reload_all must list new columns in the same order as the ALTER TABLE additions (R6/R7). The design agent should fix the exact column sequence to avoid off-by-one bugs in the INSERT tuple.

5. realizing_items() implementation: can use either the new SQLite index (query-based) or an in-memory scan of self._by_id. The index approach is preferred for large spaces; the design agent should choose and document the decision.

6. Risk area — type guard widening (R4): the existing guard in parse_file (lines 247-250) must be extended to an exhaustive whitelist of all five valid types. Silent pass-through of unknown types would be a latent defect.
