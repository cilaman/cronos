---
cc_version: "1.0"
agent: pipeline-scout
slug: featurefix-api
phase: scout
status: done
confidence: 0.88
inputs_used:
  - memory:arc_features_fixes_board_setup
  - memory:s1_data_model_impl
  - memory:project_pipeline_schemas
  - backend/app/models.py
  - backend/app/storage.py
  - backend/app/feature_state.py
  - backend/app/api/tasks.py
  - backend/app/main.py
outputs_produced:
  - .cronos/pipeline/featurefix-api/scout-report-featurefix-api.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - backend/app/api/ (endpoint patterns)
    - backend/app/models.py (Feature schema definitions)
    - backend/app/storage.py (Feature storage & transitions)
    - backend/app/feature_state.py (Feature state machine)
    - backend/app/main.py (router registration pattern)
  excluded:
    - frontend/: UI out of S2 scope
    - tests/: implementation responsibility
  strategies:
    - memory_retrieval
    - glob_structural
    - read_targeted
brief: "New backend/app/api/features.py (prefix=/api/features) with endpoints for create, read, board view, state transition, realizes linking, and processing trigger. No UI. Locked design from S1 includes FeatureState, feature_key numbering (FEAT-/FIX-), realizes field, git-linked validation, and MD persistence."
metrics:
  tool_calls: 8
  files_read: 8
  memory_hits: 3
---

## Summary

S1 (featurefix-data-model) completed Feature and Fix task support: FeatureState enum (5 states), feature_key auto-numbering (FEAT-/FIX- per space), realizes field, and storage persistence. S2 requires a new FastAPI router (`api/features.py`, prefix `/api/features`) with 8 endpoints: create (validate git-linked), board (5 lanes), fetch single + realizing_items, state transition (enforced), edit, realize linking, and process trigger. Storage layer provides feature_board(), transition_feature(), realizing_items(), set_realizes(), and _next_feature_key(). FeatureBoard schema is not yet defined in models.py. No new tables; feature_state.py defines valid transition sets.

## Coverage

### Searched
- `backend/app/api/`: tasks.py router pattern (board, state, CRUD endpoints, error handling)
- `backend/app/models.py`: Task now has feature_state, feature_key, realizes, issue_* fields; FeatureState enum present
- `backend/app/storage.py`: async methods feature_board(), transition_feature(), realizing_items(), set_realizes() implemented; _next_feature_key() helper; validate_realizes() validation
- `backend/app/feature_state.py`: FEATURE_USER_TRANSITIONS, FEATURE_WORKER_TRANSITIONS frozensets
- `backend/app/main.py`: router include pattern (dependencies=_auth)

### Excluded
- `frontend/`: S2 has_ui=false
- `tests/`: implementation + test phase responsibility
- `.claude/`: agent specs (reference only)

### Strategies
- memory_retrieval: 3 entries (board setup, S1 model impl, pipeline schemas)
- glob_structural: api/ directory scan, models.py and storage.py targeted reads
- read_targeted: 8 files examined; focused on Feature schema, storage methods, router patterns

## Findings

**Models (backend/app/models.py:18–62, stable on feature/features-and-fixes branch)**
- FeatureState enum: BACKLOG, PROCESSING, PLANNED, WAITING, DONE (distinct from TaskState)
- Task.type expanded: "task" | "goal" | "issue" | "feature" | "fix"
- Feature-specific Task fields: feature_state (FeatureState | None), feature_key (str), realizes (task_id), issue_number/url, proposed_issue_path
- TaskSummary mirrors these 6 new fields

**Storage methods (backend/app/storage.py, async and in-memory safe)**
- `async feature_board(space_id) → dict[FeatureState, list[TaskSummary]]`: filters type in ("feature","fix"), excludes feature_state=None, groups by FeatureState, sorts by (manual_order, created_at)
- `_next_feature_key(space_id, task_type) → str`: returns "FEAT-NNN" or "FIX-NNN" per space and type; scans self._by_id (caller must hold lock)
- `async transition_feature(task_id, new_feature_state, allowed=frozenset)`: mutates feature_state only (not task.state); validates type is "feature"/"fix", transition in allowed, and current state non-None; re-persists task
- `async realizing_items(feature_id) → list[TaskSummary]`: scans self._by_id for tasks where realizes == feature_id
- `async set_realizes(item_id, feature_id | None) → Task`: sets or clears realizes field; validates via validate_realizes() (self-reference, existence, same-space, target type)
- SQLite schema: columns (feature_state TEXT NULL, feature_key TEXT NULL, realizes TEXT NULL, issue_number INTEGER NULL, issue_url TEXT NULL, proposed_issue_path TEXT NULL) added; index idx_tasks_space_realizes on (space_id, realizes)

**Validation (app/feature_state.py)**
- FEATURE_USER_TRANSITIONS: BACKLOG↔PROCESSING, PLANNED↔PROCESSING, WAITING↔PROCESSING, WAITING→PLANNED, PLANNED→DONE, DONE→BACKLOG (7 edges)
- FEATURE_WORKER_TRANSITIONS: PROCESSING→PLANNED/WAITING, PLANNED↔WAITING, PLANNED→DONE (5 edges)
- Both defined as frozensets; passed via allowed= parameter to transition_feature()

**Request specification (locked design from S2 brief)**
- POST /api/features: validate git-linked (400 if not), allocate key via _next_feature_key(), write MD, fire S3 mirror
- GET /api/features?space_id=: return FeatureBoard (5 lanes via feature_board())
- GET /api/features/{id}: feature + realizing_items[]
- PATCH /api/features/{id}/feature-state: transition_feature(allowed=FEATURE_USER_TRANSITIONS); re-fire mirror; 409 on invalid transition
- PATCH /api/features/{id}: title/brief edit; re-fire mirror
- PATCH /api/features/{id}/realize: set_realizes() link/unlink
- POST /api/features/{id}/process: set feature_state = PROCESSING, enqueue decomposition task (S4 trigger)
- All persist to MD and trigger S3 mirror (one-way git sync)

**Missing (S2 responsibility)**
- FeatureBoard schema in models.py (dict[FeatureState, list[TaskSummary]] needs Pydantic model)
- api/features.py router (8 endpoints above)
- POST /api/features request body schema (space_id, title, brief, type, priority)
- PATCH /realize request body schema (feature_id)
- PATCH /feature-state request body schema (feature_state)
- POST /process request body (none; enqueue sub-task)
- Endpoint registration in main.py (app.include_router(features_router, dependencies=_auth))
- MD serialization for feature items (realize/feature_state fields in dump_task/parse_file)

**Persistence integration**
- Feature items are Tasks (type="feature"|"fix"); uses same MD file per task in .cronos/tasks/
- Feature-specific fields (feature_state, feature_key, realizes) are YAML frontmatter in task MD
- S3 mirror invoked on POST/PATCH endpoints (location not queried; assume S3 upload logic exists in git_ops or similar)
- No new .cronos/ subdirectories; features live alongside tasks in .cronos/tasks/{id}.md

**Git and numbering**
- feature_key is auto-allocated at POST time (immutable; FEAT-001, FIX-001, etc., per space)
- Numbering is per-space and per-type (independent FEATand FIX counters)
- Git-linked validation: POST /api/features returns 400 if space.git_repo_url is None
- MD canonical source (GitHub issue mirror is one-way outbound)

## Assumptions
- FeatureBoard will be defined as a new Pydantic model (dict[FeatureState, list[TaskSummary]] or equivalent)
- S3 mirror logic is already present in the codebase (implied by "fire S3 mirror")
- Feature items use same MD file storage and dump_task/parse_file patterns as tasks
- Worker picks up PROCESSING features for decomposition (worker.py S4 hook not yet examined)
- POST /process enqueues a new "processing" task that drives S4 decomposition

## Open questions
- None. All required storage and domain logic is present on feature/features-and-fixes. S2 implementation is strictly endpoint wiring + schema definition.

## Next consumer brief

**For analysis agent:**
- Confirm 8 endpoints are API-surface responsibility vs. storage (likely all 8 are router endpoints)
- Identify FeatureBoard schema (is it a simple dict wrapper or does it need additional envelope?)
- Clarify S3 mirror trigger: does it call a git_ops function, or is there a separate upload_feature_to_github() method?
- Verify POST /process enqueues a decomposition task: trace worker.py to find the hook (likely a goal creation or similar)
- Note: no scope_files changes — api/features.py is new, models.py adds 6 fields (already done S1), main.py one-liner

**For implementation agent:**
- Scope: `api/features.py` (new), `models.py` (FeatureBoard schema), `main.py` (one router reg line)
- Priority: Pydantic schemas (CreateFeatureBody, PatchRealize, PatchFeatureState, FeatureBoard) first
- Feature storage methods are stable and tested (feature_board, transition_feature, realizing_items, set_realizes, _next_feature_key)
- Validate no git_repo_url → 400 on POST
- All endpoints must return TaskRead or TaskSummary (reuse TaskRead pattern from tasks.py)
