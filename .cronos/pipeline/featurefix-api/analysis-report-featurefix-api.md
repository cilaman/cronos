---
cc_version: '1.0'
agent: pipeline-analyst
slug: featurefix-api
phase: analysis
status: done
confidence: 0.9
inputs_used:
- memory:arc_features_fixes_board_setup
- memory:s1_data_model_impl
- memory:project_pipeline_schemas
- memory:project_pipeline_analyst_agent
- .cronos/pipeline/featurefix-api/scout-report-featurefix-api.md
- backend/app/models.py
- backend/app/feature_state.py
- backend/app/api/tasks.py
- backend/app/main.py
- backend/app/storage.py
outputs_produced:
- .cronos/pipeline/featurefix-api/analysis-report-featurefix-api.md
blockers: []
next_consumer: design
request: "New `backend/app/api/features.py` (`prefix=\"/api/features\"`), registered\
  \ like the tasks router.\nDo **not** overload `api/tasks.py`.\n- `POST /api/features`\
  \ `{space_id,title,brief,type:\"feature\"|\"fix\",priority}` -- validate git-linked\n\
  \  (else 400); allocate key; write MD; fire S3 mirror.\n- `GET /api/features?space_id=`\
  \ -> `FeatureBoard` (5 lanes via `feature_board()`).\n- `GET /api/features/{id}`\
  \ -> feature + `realizing_items`.\n- `PATCH /api/features/{id}/feature-state` ->\
  \ `transition_feature(allowed=FEATURE_USER_TRANSITIONS)`; re-fire mirror.\n- `PATCH\
  \ /api/features/{id}` -> title/brief edit; re-fire mirror.\n- `PATCH /api/features/{id}/realize`\
  \ -> `set_realizes` link/unlink.\n- `POST /api/features/{id}/process` -> `processing`\
  \ + `enqueue` decomposition (S4 trigger).\n- Thread `realizes` into `CreateTaskBody`/`store.create`,\
  \ or rely on `/realize` -- pick one."
has_ui: false
coverage_summary:
  searched:
  - backend/app/api/
  - backend/app/models.py
  - backend/app/storage.py
  - backend/app/feature_state.py
  - backend/app/main.py
  excluded:
  - frontend/: has_ui=false; S2 is backend-only
  - tests/: implementation + test phase responsibility
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_keyword
traceability:
- requirement_id: R1
  statement: A new FastAPI router api/features.py (prefix /api/features) is created
    and registered in main.py with the same dependencies=_auth pattern as the tasks
    router; it does not modify api/tasks.py.
  acceptance_criteria:
  - Given main.py is loaded, app.include_router(features_router, dependencies=_auth)
    is present and resolves without import errors.
  - No new endpoints appear in api/tasks.py; all feature routes are served from the
    new router.
  - All existing task endpoints continue to pass their tests after registration.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R2
  statement: 'Pydantic request/response schemas are added to models.py: CreateFeatureBody
    (space_id, title, brief, type, priority), PatchFeatureBody (title, brief), PatchFeatureStateBody
    (feature_state), PatchRealizeBody (item_id, feature_id), and FeatureBoard (five
    named lane fields corresponding to FeatureState values).'
  acceptance_criteria:
  - Each schema is importable from app.models and passes Pydantic v2 validation with
    valid inputs.
  - 'FeatureBoard exposes exactly five lanes: backlog, processing, planned, waiting,
    done (all list[TaskSummary]).'
  - CreateFeatureBody.type accepts only feature or fix; other values raise 422.
  - CreateFeatureBody.priority is validated in range [1, 5] consistent with the Task
    model.
  verifying_phase: test
  confidence: 0.92
- requirement_id: R3
  statement: 'POST /api/features creates a feature or fix task: it validates the space
    is git-linked (returns 400 if space.git_repo_url is None), allocates a feature_key
    via _next_feature_key(), writes the MD file, and fires the S3 mirror.'
  acceptance_criteria:
  - Given a git-linked space, when POST /api/features is called with valid body, then
    a Task with type in (feature, fix) is returned with a non-null feature_key of
    the form FEAT-NNN or FIX-NNN.
  - Given a non-git-linked space (git_repo_url is None), when POST /api/features is
    called, then 400 is returned with a descriptive error message.
  - The created task MD file exists on disk after the call.
  - The S3 mirror function is invoked exactly once for the created item.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R4
  statement: GET /api/features?space_id= returns a FeatureBoard response by calling
    store.feature_board(space_id); the tasks board endpoint (GET /api/tasks/board)
    continues to exclude items of type feature and fix.
  acceptance_criteria:
  - Given a space with at least one feature and one fix, when GET /api/features?space_id={id}
    is called, then all five FeatureState lanes are present and each item appears
    in its matching lane.
  - Given a feature item exists, when GET /api/tasks/board?space_id={id} is called,
    then the feature item does not appear in any lane.
  - Items with feature_state=None are not included in any FeatureBoard lane.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R5
  statement: GET /api/features/{id} returns a response containing the full feature/fix
    record plus the list of realizing_items populated by store.realizing_items(id);
    it returns 404 for missing or non-feature/fix IDs.
  acceptance_criteria:
  - Given a feature with two realizing tasks, when GET /api/features/{id} is called,
    then realizing_items has length 2.
  - Given an ID that does not exist or belongs to a non-feature/fix task, then 404
    is returned.
  - 'The response includes all feature-specific fields: feature_state, feature_key,
    realizes, issue_number, issue_url.'
  verifying_phase: test
  confidence: 0.9
- requirement_id: R6
  statement: PATCH /api/features/{id}/feature-state transitions the feature to a new
    FeatureState using store.transition_feature(allowed=FEATURE_USER_TRANSITIONS)
    and re-fires the S3 mirror; illegal transitions return 409.
  acceptance_criteria:
  - Given a feature in BACKLOG state, PATCH /feature-state with feature_state=processing
    returns PROCESSING.
  - Given a feature in BACKLOG state, PATCH /feature-state with feature_state=done
    (not in FEATURE_USER_TRANSITIONS) returns 409.
  - After a successful transition, the S3 mirror function is invoked once.
  - Given an ID that does not exist, 404 is returned.
  verifying_phase: test
  confidence: 0.92
- requirement_id: R7
  statement: PATCH /api/features/{id} updates the feature title and/or brief fields
    and re-fires the S3 mirror.
  acceptance_criteria:
  - Given a valid feature, PATCH /api/features/{id} with title=New Title returns title=New
    Title and bumped updated_at.
  - Given a valid feature, PATCH /api/features/{id} with brief=New brief returns the
    updated brief.
  - After a successful edit, the S3 mirror function is invoked once.
  - Given an ID that does not exist, 404 is returned.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R8
  statement: PATCH /api/features/{id}/realize links or unlinks a task to/from a feature
    using store.set_realizes(item_id, feature_id or None); the storage-layer validate_realizes()
    enforces self-reference, existence, same-space, and target-type constraints.
  acceptance_criteria:
  - Given task T and feature F in the same space, PATCH /api/features/F/realize with
    item_id=T and feature_id=F sets T.realizes=F.
  - Given task T with realizes=F, PATCH with item_id=T and feature_id=null clears
    T.realizes.
  - Given item_id == feature_id (self-reference), the request is rejected with 400
    or 422.
  - Given item_id and feature_id in different spaces, the request is rejected.
  - After the operation, GET /api/features/{F} realizing_items reflects the updated
    state.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R9
  statement: POST /api/features/{id}/process transitions the feature to PROCESSING
    state via store.transition_feature(allowed=FEATURE_USER_TRANSITIONS) and enqueues
    a decomposition sub-task that the S4 worker hook will act on.
  acceptance_criteria:
  - Given a feature in BACKLOG state, POST /api/features/{id}/process returns feature
    with feature_state=PROCESSING.
  - A decomposition task or worker-visible item is created/enqueued so S4 can proceed.
  - 'Given a feature already in PROCESSING state, the endpoint returns 409 (per transition
    table: PROCESSING->PROCESSING not in FEATURE_USER_TRANSITIONS).'
  - Given an ID that does not exist, 404 is returned.
  verifying_phase: test
  confidence: 0.82
- requirement_id: R10
  statement: 'The FeatureBoard response and the tasks Board response are fully disjoint:
    no item of type feature or fix appears in the tasks board, and no item of type
    task, goal, or issue appears in the FeatureBoard.'
  acceptance_criteria:
  - A task of type=task does not appear in any FeatureBoard lane.
  - A task of type=feature or type=fix does not appear in any Board lane from the
    tasks router.
  - Both boards can be queried simultaneously for the same space without error.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R11
  statement: All feature-specific fields (feature_state, feature_key, realizes, issue_number,
    issue_url, proposed_issue_path) are correctly serialized in the MD file and deserialized
    back through dump_task/parse_file so that a round-trip create then GET returns
    identical field values.
  acceptance_criteria:
  - After POST /api/features, the task MD frontmatter contains feature_state, feature_key,
    and type.
  - After simulated reload from disk, the feature item retains its feature_state and
    feature_key.
  verifying_phase: test
  confidence: 0.85
- requirement_id: R12
  statement: 'The feature_key allocated at creation time is immutable: subsequent
    PATCH edits to title/brief or feature-state transitions do not alter the feature_key
    value.'
  acceptance_criteria:
  - Given a created feature with feature_key=FEAT-001, after PATCH /api/features/{id}
    and PATCH /api/features/{id}/feature-state, GET /api/features/{id} still returns
    feature_key=FEAT-001.
  verifying_phase: review
  confidence: 0.92
- requirement_id: R13
  statement: All mutating endpoints (POST create, PATCH feature-state, PATCH edit)
    fire the S3 mirror function exactly once per call; read-only endpoints (GET board,
    GET single) and PATCH realize do not fire the mirror.
  acceptance_criteria:
  - S3 mirror call count equals 1 after POST create, PATCH feature-state, and PATCH
    edit.
  - S3 mirror is not called after GET /api/features, GET /api/features/{id}, or PATCH
    /realize.
  verifying_phase: test
  confidence: 0.85
- requirement_id: R14
  statement: The new features router is registered in main.py with auth dependencies
    identical to all other routers; unauthenticated requests to any /api/features/*
    path return 401.
  acceptance_criteria:
  - A request to GET /api/features?space_id=x without auth credentials returns 401.
  - All feature endpoints appear in the OpenAPI spec (/api/docs) after registration.
  verifying_phase: test
  confidence: 0.95
metrics:
  tool_calls: 9
  files_read: 6
  memory_hits: 4
---

## Summary

S2 adds a dedicated `backend/app/api/features.py` FastAPI router (prefix `/api/features`) that exposes eight endpoints covering the full lifecycle of Feature and Fix items: creation with git-linked validation and key allocation, board read, single-item fetch with realized-tasks list, state transition enforcement, title/brief editing, realize link/unlink, and a process trigger that kicks off S4 decomposition. The storage layer from S1 (feature_board, transition_feature, realizing_items, set_realizes, _next_feature_key, validate_realizes) is already implemented and stable on the feature branch; this spec covers API wiring, Pydantic schema definitions, router registration, and S3 mirror firing only. No UI work is in scope.

## Scope

### In scope
- New file `backend/app/api/features.py` with all 8 endpoints under prefix `/api/features`
- Pydantic schemas in `models.py`: `CreateFeatureBody`, `PatchFeatureBody`, `PatchFeatureStateBody`, `PatchRealizeBody`, `FeatureBoard`, `FeatureRead`
- Router registration in `main.py` (one `include_router` line, same auth pattern as tasks)
- Git-linked space validation (400 if `space.git_repo_url` is None) on POST create
- `feature_key` allocation via existing `_next_feature_key()` on POST create
- S3 mirror invocation on mutating endpoints (POST, PATCH feature-state, PATCH edit)
- `FEATURE_USER_TRANSITIONS` enforcement returning 409 on illegal transitions
- `set_realizes` / `validate_realizes` plumbing for PATCH realize
- PROCESSING state set + decomposition task enqueue on POST process (S4 trigger)
- Tasks board exclusion: `GET /api/tasks/board` must not surface feature/fix items

### Out of scope
- Frontend UI (has_ui = false; UI is a separate subgoal)
- New SQLite tables (index columns only, already added in S1)
- S4 decomposition logic itself (only the enqueue trigger is in S2 scope)
- GitHub issue HTTP API calls (one-way MD-to-mirror only; no inbound sync)
- Worker state-machine changes (only the enqueue stub needed to hand off to S4)

### Deferred
- `GET /api/features` filtering by feature_state or type query params
- Bulk PATCH operations
- Pagination on board lanes
- `realizes` threading into `CreateTaskBody` (PATCH /realize approach chosen per request)

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | New `api/features.py` router created and registered in `main.py` without touching `api/tasks.py` |
| R2 | Pydantic schemas `CreateFeatureBody`, `PatchFeatureBody`, `PatchFeatureStateBody`, `PatchRealizeBody`, `FeatureBoard` added to `models.py` |
| R3 | `POST /api/features` validates git-linked space (400 if not), allocates `feature_key`, writes MD, fires mirror |
| R4 | `GET /api/features?space_id=` returns `FeatureBoard` (5 lanes); tasks board continues to exclude features |
| R5 | `GET /api/features/{id}` returns feature record plus `realizing_items` list; 404 for missing/non-feature IDs |
| R6 | `PATCH /api/features/{id}/feature-state` enforces `FEATURE_USER_TRANSITIONS`, fires mirror, 409 on illegal transition |
| R7 | `PATCH /api/features/{id}` updates title/brief and fires mirror |
| R8 | `PATCH /api/features/{id}/realize` calls `set_realizes` to link or unlink; storage validates constraints |
| R9 | `POST /api/features/{id}/process` sets PROCESSING state and enqueues S4 decomposition task |
| R10 | `FeatureBoard` and tasks `Board` are fully disjoint; no cross-contamination between boards |
| R11 | Feature fields round-trip correctly through MD serialization (`dump_task`/`parse_file`) |
| R12 | `feature_key` is immutable across all PATCH operations |
| R13 | Mirror fires exactly once on mutating endpoints, never on read-only endpoints |
| R14 | New router registered with auth; unauthenticated requests return 401 |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). The body summary below mirrors them in compact form for the human reader.

- R1 — `main.py` includes `features_router` with `dependencies=_auth`; no new routes in `api/tasks.py`; all existing task tests still pass
- R2 — All five schemas importable; `FeatureBoard` has exactly 5 lane fields; `CreateFeatureBody.type` rejects non-feature/fix; priority in [1,5]
- R3 — Git-linked space returns Task with FEAT-/FIX-NNN key + MD on disk + mirror called once; non-git returns 400
- R4 — `GET /api/features` lanes contain only feature/fix items matching their feature_state; tasks board has no feature/fix items
- R5 — Response includes `realizing_items[]`; 404 on missing/non-feature IDs; all feature fields present
- R6 — Valid transition succeeds with updated state + mirror; invalid transition returns 409; missing ID returns 404
- R7 — title/brief updated, `updated_at` bumped, mirror fired once; 404 on missing ID
- R8 — Link sets `realizes`; null clears it; self-reference and cross-space violations rejected; GET reflects updated state
- R9 — PROCESSING state set; decomposition task enqueued; repeat PROCESSING returns 409; 404 on missing ID
- R10 — No task type bleeds into FeatureBoard; no feature type bleeds into Board; both queryable simultaneously
- R11 — MD frontmatter contains feature fields; reload from disk preserves `feature_state` and `feature_key`
- R12 — `feature_key` unchanged after any PATCH operation
- R13 — Mirror count = 1 after POST/PATCH feature-state/PATCH edit; count = 0 after GET and PATCH realize
- R14 — Unauthenticated request to any `/api/features/*` returns 401; routes appear in OpenAPI spec

## Traceability

The full requirement to acceptance criteria to verifying_phase map is the YAML `traceability[]` array. Downstream agents read the YAML directly; this section exists so a human reader sees the same routing table without parsing YAML.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | New `api/features.py` router created and registered in `main.py` without touching `api/tasks.py` |
| R2 | test | Pydantic schemas added to `models.py` covering all request/response shapes |
| R3 | test | `POST /api/features` validates git-linked, allocates key, writes MD, fires mirror |
| R4 | test | `GET /api/features?space_id=` returns `FeatureBoard`; tasks board excludes features |
| R5 | test | `GET /api/features/{id}` returns feature record plus `realizing_items`; 404 for missing IDs |
| R6 | test | `PATCH /api/features/{id}/feature-state` enforces transitions, fires mirror, 409 on illegal |
| R7 | test | `PATCH /api/features/{id}` updates title/brief and fires mirror |
| R8 | test | `PATCH /api/features/{id}/realize` calls `set_realizes`; storage validates constraints |
| R9 | test | `POST /api/features/{id}/process` sets PROCESSING and enqueues S4 decomposition task |
| R10 | test | `FeatureBoard` and tasks `Board` are fully disjoint |
| R11 | test | Feature fields round-trip correctly through MD serialization |
| R12 | review | `feature_key` is immutable across all PATCH operations |
| R13 | test | Mirror fires exactly once on mutating endpoints, never on read-only endpoints |
| R14 | test | New router registered with auth; unauthenticated requests return 401 |

## Assumptions

- `has_ui = false` rationale: the request explicitly states `has_ui: no` and all 8 endpoints are backend REST API; no frontend components are mentioned.
- The S3 mirror function referenced in the request maps to a git-based push mechanism (likely `git_ops.py` or a dedicated helper); the exact call site is implementation responsibility. The design agent should identify the concrete mirror function name.
- `POST /api/features/{id}/process` uses `FEATURE_USER_TRANSITIONS` (BACKLOG->PROCESSING is in the table) for the state transition consistent with user-initiated action; the design agent should confirm vs. a direct state write.
- The `FeatureBoard` model will use named lane fields (`backlog`, `processing`, `planned`, `waiting`, `done`) analogous to the existing `Board` model for Pydantic v2 serialization consistency.
- The `/realize` PATCH approach is used for S2; threading `realizes` into `CreateTaskBody` is deferred.
- Feature-specific Task fields (`feature_state`, `feature_key`, `realizes`, etc.) and `FeatureState` enum are already present on the `feature/features-and-fixes` branch from S1; models.py on main branch does not yet have them. All implementation targets the feature branch.
- The `FeatureRead` response schema extends `TaskRead` with a `realizing_items: list[TaskSummary]` field added at the API layer (not stored in Task model).
- `TaskType` Literal in `models.py` is extended to include `"feature" | "fix"` (done in S1).

## Open questions

- The exact call signature and module location for the S3 mirror function is not confirmed by the scout. If it does not yet exist, the design agent must decide whether to stub it or implement it inline in `api/features.py`.
- `POST /api/features/{id}/process` enqueue mechanism: does it create a child goal task under the feature, or post directly to a worker queue? The design agent must trace `worker.py` to identify the S4 hook entry point before finalizing the implementation plan for R9.

## Next consumer brief

**Read first:** `traceability[]` YAML array (14 requirements, R1-R11/R13-R14 are `verifying_phase: test`, R12 is `review`), `has_ui: false`, `## Scope` IN/OUT-OF/DEFERRED boundaries.

**Key decision points for the design agent:**

1. **S3 mirror function identity** (R3, R6, R7, R13) -- locate the concrete mirror call in `git_ops.py` or equivalent; must be invoked after POST create, PATCH feature-state, and PATCH edit. This is the highest-risk unknown in the design.

2. **POST /process enqueue mechanism** (R9) -- trace `worker.py` to find the S4 PROCESSING hook. Determine whether the endpoint creates a child task (type="goal" under the feature), posts to an internal queue, or uses another mechanism the worker already polls.

3. **FeatureRead schema shape** (R5) -- decide whether to extend `TaskRead` with a `realizing_items` field or define a standalone `FeatureRead` Pydantic model in `models.py`.

4. **Tasks board exclusion** (R4, R10) -- verify that the existing `Board` query in `storage.py` already filters `type not in ("feature","fix")`; if not, a targeted storage change is needed (not in scope of `api/features.py` but required for R4 and R10 to pass).

5. **Scope files are narrow:** `api/features.py` (new), `models.py` (FeatureBoard + request/response schemas), `main.py` (one `include_router` line). No changes to `api/tasks.py`, `feature_state.py`, or `storage.py` beyond any board-filter fix.
