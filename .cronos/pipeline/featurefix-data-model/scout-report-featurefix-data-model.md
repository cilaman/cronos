---
cc_version: "1.0"
agent: pipeline-scout
slug: featurefix-data-model
phase: scout
status: done
confidence: 0.92
inputs_used:
  - memory:architecture
  - backend/app/models.py
  - backend/app/storage.py
  - backend/app/api/tasks.py
outputs_produced:
  - .cronos/pipeline/featurefix-data-model/scout-report-featurefix-data-model.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - backend/app/models.py
    - backend/app/storage.py
    - backend/app/api/tasks.py
  excluded:
    - frontend: not required for S1 (no UI)
    - tests: coverage floor enforced separately
  strategies:
    - memory_retrieval
    - glob_structural
    - read_targeted
brief: "S1 — Data model: types + feature_state machine + numbering + realizes. Extend Task model + storage (no API, no UI)."
metrics:
  tool_calls: 11
  files_read: 3
  memory_hits: 1
---

## Summary

The Cronos task model currently supports three types (task/goal/issue) with a four-state machine (backlog/active/waiting/done/archived). The S1 task extends models.py with "feature"/"fix" TaskType literals and a new FeatureState enum (backlog/processing/planned/waiting/done). Storage.py provides idempotent SQLite schema migration, state validation via transition tables, and set_parent/set_depends_on patterns that the realizes field should mirror. The parser (parse_file) and serializer (dump_task) use optional meta.get() to preserve backward compatibility with existing markdown files.

## Coverage

### Searched
- `backend/app/models.py`: TaskState enum, TaskType Literal, Task and TaskSummary models (lines 10-102)
- `backend/app/storage.py`: parse_file/dump_task serialization (lines 225-343), SQLite schema and migrations (lines 403-451), task creation (lines 630-676), state transitions (lines 722-763), set_parent/set_depends_on patterns (lines 1011-1039)
- `backend/app/api/tasks.py`: parent/depends_on endpoints (lines 620-641), ParentBody/DependsOnBody request models (lines 127-132)

### Excluded
- Frontend components: no UI changes in S1; will be addressed in S6
- Test files: coverage floor enforced separately; test authorship is out-of-scope for scout
- Worker/goal_sync: execution paths; feature lifecycle hooks are design-phase concerns

### Strategies
- memory_retrieval: 1 hit (project_architecture_key_modules: storage.py role confirmed)
- glob_structural: located models.py, storage.py, tasks.py via path knowledge
- read_targeted: full read of critical sections (parsing, transitions, set_parent pattern); skipped large middleware code

## Findings

### Data Model Additions (models.py)

**Current state (lines 10-56):**
- TaskState enum: BACKLOG, ACTIVE, WAITING, DONE, ARCHIVED
- TaskType: Literal["task", "goal", "issue"] (line 20)
- Task model: 16 fields including `type`, `parent_id`, `depends_on`, `pr_url`, `proposed_pr_path`

**Required additions:**
- Extend TaskType to: Literal["task", "goal", "issue", "feature", "fix"]
- New FeatureState enum: backlog, processing, planned, waiting, done (values per request_text)
- Task model new fields (all optional):
  - `feature_state: FeatureState | None = None`
  - `feature_key: str | None = None` (format: FEAT-001, FIX-001)
  - `realizes: str | None = None` (task ID of the feature/fix being realized)
  - `issue_number: int | None = None`
  - `issue_url: str | None = None`
  - `proposed_issue_path: str | None = None` (mirrors pr_url/proposed_pr_path pattern)
- TaskSummary model: add same 5 fields with matching optionality

**Pattern note:** TaskSummary already mirrors Task fields (id, space_id, title, state, etc.); all new Task fields must be copied to TaskSummary (lines 78-109).

### Storage Serialization (storage.py)

**parse_file (lines 225-281):**
- Uses `meta.get("key")` for optional fields (see line 251: `parent_id = meta.get("parent_id") or None`)
- Type validation via whitelist (lines 248-250: task_type not in ("task", "goal", "issue"))
- Must extend lines 247-250 to accept "feature", "fix" in type guard
- Must add feature_state, feature_key, realizes, issue_number, issue_url, proposed_issue_path parsing
  - Example pattern line 251: `feature_state_str = meta.get("feature_state") or None`
  - Validate against FeatureState enum values (backlog/processing/planned/waiting/done)
  - Use string→enum coercion: `feature_state=feature_state_str and FeatureState(feature_state_str)`

**dump_task (lines 315-343):**
- Serializes Task fields to YAML frontmatter (meta dict)
- Currently does NOT output None values for optional fields (see line 324: `"claude_session_id": task.claude_session_id`)
- Extend meta dict to include all 5 new fields; None values will serialize as null in YAML
- Backward-compatible: old .md files without these keys will parse with None defaults

### SQLite Schema Migration (lines 403-451)

**Current tables:**
- tasks table: id, space_id, state, title, type, parent_id, depends_on_json (lines 407-416)
- discovered_tools table (for Arc 5 adoption)

**Required schema changes:**
- Add nullable columns via idempotent ALTER TABLE ADD COLUMN (pattern: lines 418-426):
  ```python
  ("feature_state", "TEXT NULL"),
  ("feature_key", "TEXT NULL"),
  ("realizes", "TEXT NULL"),
  ("issue_number", "INTEGER NULL"),
  ("issue_url", "TEXT NULL"),
  ("proposed_issue_path", "TEXT NULL"),
  ```
- Add index: `CREATE INDEX IF NOT EXISTS idx_tasks_space_realizes ON tasks(space_id, realizes)`
  (for efficient realizing_items() queries; mirrors existing idx_tasks_space_parent)

**Database upsert (lines 453-471):**
- _db_upsert updates INSERT OR REPLACE columns dynamically
- Must extend INSERT statement to include new 6 columns; use json.dumps() for complex types (but these are scalars)
- Current pattern (line 457-467) already handles optional fields; extend tuple to match new column count

**reload_all (lines 508-552):**
- Two INSERT paths: lines 537-549 and lines 540-548 (identical INSERT statement)
- Must update both INSERT statements to include new columns in same order as _db_upsert

### State Machine: Feature Transitions (new to storage.py)

**Current tables (lines 41-57):**
- USER_TRANSITIONS: allowed user-initiated state changes (e.g., BACKLOG→ACTIVE, DONE→BACKLOG)
- WORKER_TRANSITIONS: allowed worker state changes (ACTIVE→WAITING, ACTIVE→DONE, WAITING→ACTIVE)
- Pattern: sets of (from_state, to_state) tuples

**Required: Feature-specific transitions**
- Create FEATURE_USER_TRANSITIONS (separate from USER_TRANSITIONS) per request_text:
  - (BACKLOG, PROCESSING), (PROCESSING, BACKLOG), (PLANNED, PROCESSING), (WAITING, PROCESSING), (WAITING, PLANNED), (PLANNED, DONE), (DONE, BACKLOG)
- Create FEATURE_WORKER_TRANSITIONS (separate from WORKER_TRANSITIONS):
  - (PROCESSING, PLANNED), (PROCESSING, WAITING), (PLANNED, WAITING), (WAITING, PLANNED), (PLANNED, DONE)
- Note: FeatureState maps are separate enums; do NOT reuse FeatureState.BACKLOG as TaskState.BACKLOG (different enums)

**Transition function (new):**
- Create `async def transition_feature(task_id: str, new_feature_state: FeatureState, *, allowed: set[...]) -> Task:`
  (mirror of transition() at lines 722-763)
- Signature: like transition() but operates on task.feature_state field instead of task.state
- Validation: must check (task.feature_state, new_feature_state) in allowed set
- Implementation: same pattern as transition() — model_copy + atomic_write + _reindex_locked

### Task Numbering (new helper)

**Location:** Create `_next_feature_key(space_id: str, task_type: Literal["feature", "fix"]) -> str` in storage.py

**Pattern:**
- No persistent counter file; compute max existing per space+type inside self._lock in create()
- Scan self._by_id for tasks with matching space_id and type="feature" or type="fix"
- Extract numeric suffix from existing feature_key (e.g., "FEAT-001" → 1)
- Return zero-padded 3-digit string: f"{prefix}-{next_num:03d}" (FEAT-002, FIX-001, etc.)
- Counter per type: FEAT and FIX are independent within a space

**Invocation:** In create() method (line 630-676), add logic after task type validation:
```python
if type in ("feature", "fix"):
    prefix = "FEAT" if type == "feature" else "FIX"
    feature_key = _next_feature_key(space_id, type)
else:
    feature_key = None
```

### Parent-Like Pattern: set_realizes

**Existing models (set_parent):**
- Lines 1011-1024: validates via validate_parent (lines 83-124)
- validate_parent checks: not self-ref, parent in same space, no cycle in parent chain

**Required: set_realizes method**
- Signature: `async def set_realizes(item_id: str, feature_id: str | None) -> Task:`
- Validation (new): `validate_realizes(item_id, feature_id, space_id, by_id)` with checks:
  - If feature_id is not None: must exist in by_id and be in same space as item_id
  - If feature_id is not None: target task.type must be "feature" or "fix"
  - Self-reference guard: item_id != feature_id
  - (No cycle validation needed: realizes is not transitive; only tracks parent feature)
- Implementation: identical to set_parent pattern — model_copy, atomic_write, _reindex_locked

### Board Filtering

**Current board() (lines 607-626):**
- Iterates all tasks in scope (space_id), filters by state
- No type filtering; all types (task/goal/issue) appear on board

**Required changes:**
- Modify board() to exclude type="feature" and type="fix" (lines 611-613):
  - Add guard: `if task.type in ("feature", "fix"): continue`
- Add new method: `async def feature_board(space_id: str) -> dict[FeatureState, list[TaskSummary]]:`
  - Buckets feature/fix tasks by feature_state instead of state
  - Structure: {FeatureState.BACKLOG: [...], FeatureState.PROCESSING: [...], ...}

**counts_by_space() (lines 592-597):**
- Currently counts all tasks grouped by TaskState per space
- Exclude feature/fix: add guard before incrementing (line 596):
  - `if task.type in ("feature", "fix"): continue`

### Helper Methods

**realizing_items(feature_id: str) -> list[TaskSummary]:**
- Returns all tasks where task.realizes == feature_id
- Uses existing SQLite index idx_tasks_space_realizes or filters in-memory _by_id
- Called by UI later (not in S1 scope, but indexing now enables efficient queries)

## Assumptions
- FeatureState enum values map 1:1 to request_text (backlog, processing, planned, waiting, done) — no aliases or defaults beyond None
- feature_key is computed at create time and immutable (no mutation endpoint in S1)
- feature/fix tasks have distinct state machines from regular tasks; can coexist in same space without state confusion
- All feature/fix fields are optional (existing .md files without them parse to None); preserve full backward compatibility
- No API endpoint for transition_feature in S1; only transition() for regular task state; feature_state transitions only via direct field update in later phases
- "realizes" is unidirectional and non-transitive; a task realizes one feature, a feature can be realized by many tasks

## Open questions
- None.

## Next consumer brief

**Analysis agent (phase 2) should:**
1. Read this report's Finding sections 1-7 to map scope_files for architecture phase
2. Verify has_ui=false is correct (no frontend changes in S1)
3. Check if feature/fix exclusion from board() has implications for dashboard counts/activity feed
4. Confirm numbering scheme (FEAT-001 format, 3-digit zero-padded) vs. any external issue tracker integration
5. Assess whether transition_feature state machine should be editable by users in later phases or worker-only
6. Note: database_schema migrations are idempotent; backward-compatible with existing .md files (no data migration risk)
