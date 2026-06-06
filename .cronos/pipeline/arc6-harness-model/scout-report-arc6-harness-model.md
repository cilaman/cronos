---
cc_version: "1.0"
agent: pipeline-scout
slug: arc6-harness-model
phase: scout
status: done
confidence: 0.88
inputs_used:
  - memory:project_architecture_key_modules
  - memory:project_pipeline_schemas
  - memory:project_arc6_board_setup
  - backend/app/models.py
  - backend/app/space_storage.py
  - backend/app/storage.py
  - backend/app/api/tasks.py
  - backend/app/api/spaces.py
  - backend/app/main.py
  - backend/app/pipeline/schemas/research.schema.yaml
outputs_produced:
  - .cronos/pipeline/arc6-harness-model/scout-report-arc6-harness-model.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - backend/app/models.py — Pydantic BaseModel patterns
    - backend/app/storage.py — atomic_write, cycle detection (_dep_cycle_path, validate_depends_on)
    - backend/app/space_storage.py — YAML round-trip (parse_space_yaml, dump_space), path-safe filenames
    - backend/app/api/tasks.py — CRUD patterns, DI, validation, error responses
    - backend/app/api/spaces.py — router registration, HTTPException status codes
    - backend/app/main.py — app.state DI, async Lock patterns
    - backend/app/pipeline/schemas/research.schema.yaml — YAML header structure & validation rules
  excluded:
    - frontend/: not needed for data model design
    - backend/app/agent.py: not relevant to harness storage/API (executor phase)
    - backend/app/worker.py: executor scope, not data layer
  strategies:
    - memory_retrieval
    - glob_structural
    - read_targeted

brief: "Reconnaissance of Cronos codebase patterns for harness data layer. Focus on data model (Pydantic), storage (atomic YAML write), API patterns (CRUD, DI), and graph validation (DAG, cycles)."

metrics:
  tool_calls: 18
  files_read: 7
  memory_hits: 3
---

## Summary

The Cronos codebase provides mature patterns for the harness data layer across four critical areas. Pydantic BaseModel with `model_validator`, `model_copy`, and YAML serialization is the standard (Space, Task, View models). Atomic writes use tmpfile + `os.replace` (storage.py:346). The cycle detection algorithm (`_dep_cycle_path` / `validate_depends_on`) uses BFS over a dependency graph and is directly adaptable to harness edge validation. API patterns follow FastAPI routers with dependency injection (DI) via `Request.app.state`, exception mapping to HTTP status codes (422 for validation, 404 for missing, 409 for conflict), and model validators for post-hoc constraints. Path-safe filenames are generated deterministically from titles (slugify) with collision handling.

## Coverage

### Searched
- backend/app/models.py — Pydantic v2 BaseModel patterns: `Field` constraints, `model_validator(mode="after")`, `model_copy(update={...})`
- backend/app/storage.py — Atomic write pattern (tmpfile + secrets.token_hex + os.replace), cycle detection (BFS: `_dep_cycle_path`, ancestor walk: `validate_parent`), path resolution
- backend/app/space_storage.py — YAML parse/dump (parse_space_yaml, dump_space), in-memory index with async Lock, reindex on file change, uniqueness validation
- backend/app/api/tasks.py — Router DI (get_store, get_space_store, get_pool), request injection, error handling (HTTPException with status code mapping), model response schemas
- backend/app/api/spaces.py — CreateSpaceBody/UpdateSpaceBody pattern, validation on entry, error classification (SpaceError → 400, SpaceNotFound → 404, SpaceRepoConflict → 409)
- backend/app/main.py — app.state initialization, async Lock + locked dictionary operations, background task lifecycle
- backend/app/pipeline/schemas/research.schema.yaml — YAML header structure (required fields, metrics, constraints), validation rules (R1-R7)

### Excluded
- frontend/: UI layer not needed for data model reconnaissance
- backend/app/agent.py: agent execution scope, not storage/API design
- backend/app/worker.py: background executor; harness is data layer first

### Strategies
- memory_retrieval: 3 memory entries (architecture, pipeline schemas, arc6 board) confirmed key module roles + schema structure
- glob_structural: Identified backend/app/*.py, backend/app/api/*.py, backend/app/pipeline/schemas/ as target zones
- read_targeted: Depth-read storage.py, space_storage.py, tasks.py for patterns; skipped large test files; focused on imports + method signatures first

## Findings

### 1. Pydantic Model Design Pattern

**Standard:** BaseModel with constrained Field, post-validation, and model_copy immutability.

From models.py:
- Space (L120–153): `id`, `name`, `color` (hex validation via Field pattern), `views: list[View]`, `git_repo_url` (nullable), `@model_validator(mode="after")` for cross-field rules (view id uniqueness L145–152).
- Task (L33–56): flattened design (no nested dict), `depends_on: list[str]` (list of IDs), `parent_id: str | None`, `created_at: datetime`, `updated_at: datetime`.
- View (L23–31): `id` (kebab-case, 32 chars max), `lanes: list[TaskState]`, `type_filter: list[TaskType] | None`.

**Precedent for HarnessNode:**
- Use `id: str` as primary key (UUID or timestamped slug not required; tasks use `{date}-{title}-{collision-suffix}`).
- Use `data: dict` for type-specific config (tasks don't use a generic dict, but Space uses `agent_defaults: dict[str, str]`).
- Flatten structure (avoid deeply nested dicts initially); ports/position can be simple dicts within the model.
- Post-validation with `@model_validator(mode="after")` for graph constraints (e.g., ports referenced in edges exist).

### 2. Atomic Write & YAML Serialization

**Pattern:** storage.py:346–351 (atomic_write) + space_storage.py:153–198 (parse_space_yaml / dump_space).

```python
def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{secrets.token_hex(4)}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
```

**YAML round-trip:**
- Parse: `yaml.safe_load(raw) or {}` → Pydantic validation → model_copy for normalization → atomic_write if changed.
- Dump: Extract dict from model, ensure enums `.value`, handle None/defaults, return `yaml.safe_dump(data, sort_keys=False, allow_unicode=True)`.

**For harnesses (.cronos/harnesses/<name>.yml):**
- Use same atomic_write pattern.
- Name uniqueness: store index `_by_name: dict[str, Harness]` (like `_by_id` for tasks).
- Path-safe filename: slugify(name) + collision suffix if needed (see slugify + generate_task_id pattern).

### 3. Cycle Detection (DAG Validation)

**Algorithm:** storage.py:126–179 (validate_depends_on + _dep_cycle_path).

BFS from each dependency, tracking came_from to reconstruct cycle path if target_id is reachable:
```python
def _dep_cycle_path(target_id: str, start_id: str, by_id: dict[str, Task]) -> list[str] | None:
    came_from: dict[str, str | None] = {start_id: None}
    queue: list[str] = [start_id]
    while queue:
        current_id = queue.pop(0)
        node = by_id.get(current_id)
        if node is None:
            continue
        for next_id in node.depends_on:
            if next_id == target_id:
                # Reconstruct path
                ...
```

**Adaptation for harnesses:**
- Replace `node.depends_on` with iteration over outbound edges: `for edge in edges if edge.source_node == current_node_id`.
- Each edge target is a node_id (not port-specific initially; refine later if needed).
- Validate:
  1. No self-loops (edge.source != edge.target).
  2. Both source/target nodes exist in the graph.
  3. Both port IDs exist in their respective nodes' port dicts.
  4. No cycles via BFS through edges.

### 4. API & Router Patterns

**DI via Request.app.state** (tasks.py:36–65):
```python
def get_store(request: Request) -> TaskStore:
    return request.app.state.store

def get_space_store(request: Request) -> SpaceStore:
    return request.app.state.space_store

@router.get("/{task_id}", response_model=TaskRead)
async def get_task(task_id: str, request: Request) -> TaskRead:
    store = get_store(request)
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, ...)
    ...
```

**Error classification** (tasks.py:365–406, spaces.py:169–195):
- StorageError → 400 (bad request, e.g., invalid cycle)
- TaskNotFound / SpaceNotFound → 404
- InvalidTransition / SpaceRepoConflict → 409 (conflict, e.g., name already taken)
- ValidationError (Pydantic) → 422 (unprocessable entity)

**For harnesses API** (`GET/POST/PUT/DELETE /api/spaces/{space_id}/harnesses[/<name>]`):
- POST: CreateHarnessBody with `name`, `description`, nodes, edges; validate via graph rules; return 422 if cycle/dangling edge detected.
- GET: Fetch by name; return 404 if not found.
- PUT: Update YAML; last-writer-wins (check concurrent scenarios with live runs).
- DELETE: Remove; verify no active runs referencing it (TBD in executor phase).

**Router registration** (main.py:363–374):
- Create `backend/app/api/harnesses.py` with `router = APIRouter(prefix="/api/harnesses", tags=["harnesses"])`.
- Include in main.py: `app.include_router(harnesses_router, dependencies=_auth)`.

### 5. In-Memory Index + File Watcher Pattern

**Pattern:** space_storage.py:201–311 (SpaceStore).

```python
class SpaceStore:
    def __init__(self, spaces_dir: Path) -> None:
        self._by_id: dict[str, Space] = {}
        self._lock = asyncio.Lock()
    
    async def reload_all(self) -> None:
        async with self._lock:
            self._by_id.clear()
            # scan disk, parse YAML, index
    
    def _reindex_locked(self, path: Path) -> None:
        # react to file changes on disk
        # parse YAML, update index
    
    async def reindex_path(self, path: Path) -> None:
        async with self._lock:
            self._reindex_locked(path)
```

**For HarnessStore:**
- Mirror SpaceStore structure: `_by_space_id: dict[str, dict[str, Harness]]` (nested: space → name → harness).
- Watch `.cronos/harnesses/*.yml` in main.py:watch_spaces_dir (similar to space.yml watcher).
- Async Lock protects concurrent reads/writes.

### 6. Validation & Error Handling Precedent

**Post-validation with @model_validator** (models.py:145–152):
```python
@model_validator(mode="after")
def _view_ids_unique(self) -> "Space":
    seen: set[str] = set()
    for v in self.views:
        if v.id in seen:
            raise ValueError(f"Duplicate view id {v.id!r}")
        seen.add(v.id)
    return self
```

**For HarnessNode:**
- Validate that `ports` dict keys match any edge endpoints referencing this node.
- Use `@model_validator(mode="after")` to cross-check edges.nodes.

**For Harness (full graph):**
- Separate validator in HarnessStore.create/update (not in the model) because it needs `by_id` access for cycle checking.
- Raise StorageError (like storage.py) on cycle detection.

### 7. Path-Safe Filename Generation

**Pattern:** storage.py:356–375 (slugify + generate_task_id).

```python
def slugify(title: str) -> str:
    slug = _SLUG_RE.sub("-", title.lower()).strip("-")
    if not slug:
        slug = "untitled"
    return slug[:MAX_SLUG_LEN].rstrip("-") or "untitled"

def generate_task_id(title: str, now: datetime, taken: set[str]) -> str:
    base = f"{now.strftime('%Y-%m-%d-%H%M')}-{slugify(title)}"
    if base not in taken:
        return base
    for _ in range(10):
        candidate = f"{base}-{secrets.token_hex(2)}"
        if candidate not in taken:
            return candidate
    raise StorageError("Could not generate a unique task id")
```

**For harness names:**
- Harness name (user-facing, max ~80 chars) → filename via slugify.
- Uniqueness check: before create/update, verify name not in `_by_name` for this space.
- No timestamp needed (unlike task IDs); use collision suffix only if needed.

### 8. Metadata & Timestamp Patterns

**Standard fields** (models.py, space_storage.py):
- `created_at: datetime` — set once, never updated.
- `updated_at: datetime` — refreshed on every write.
- Use `datetime.now(tz=UTC)` (explicit UTC) for consistency.
- Serialize to ISO 8601: `_iso(dt: datetime) -> str` (storage.py:311–312).

**For Harness:**
- Add `created_at`, `updated_at`, `version: str` (e.g., "1.0") for future versioning.

### 9. Secondary Index Pattern

**Pattern:** space_storage.py:220–239 (_by_repo index for uniqueness enforcement).

```python
def _index_repo_locked(self, space: Space) -> None:
    if space.git_repo_url is None:
        return
    key = _normalize_repo_url(space.git_repo_url)
    self._by_repo[key] = space.id

def _unindex_repo_locked(self, space: Space) -> None:
    if space.git_repo_url is None:
        return
    key = _normalize_repo_url(space.git_repo_url)
    if self._by_repo.get(key) == space.id:
        self._by_repo.pop(key, None)
```

**For harnesses:**
- Maintain secondary index: `_name_by_space: dict[str, set[str]]` to check uniqueness before insert.
- Or flat: `_names_taken: set[tuple[str, str]]` (space_id, name) for global uniqueness if harnesses are space-scoped.

---

## Assumptions

- **Harnesses are space-scoped:** each harness lives at `{space}/.cronos/harnesses/<name>.yml`, isolated per space. (Storage.py scopes tasks per space; consistent pattern.)
- **Nodes and edges are always in memory:** no lazy-load of large harness definitions. (Task/Goal counts are usually <10k per space; harness graphs expected <1000 nodes.)
- **Last-writer-wins for concurrent CRUD:** if two requests update the same harness, the later write overwrites. (Space and task storage follow this; for harnesses we add a note in API docs.)
- **No soft-delete for harnesses:** DELETE removes permanently (not archived like tasks). Can be restored from git if needed.
- **Ports are simple dicts:** `{port_id: {label: str, type: 'in'|'out', ...}}` not a separate table. (Simpler for first iteration; refine if needed.)
- **Edge condition labels are optional:** condition can be null; default is "always." (Matches optional behavior in your brief.)

---

## Open questions

- None identified in this phase. Cycle detection algorithm clarity and API error response codes are straightforward adaptations. Next phase (analysis) will scope UI requirements and run/execution binding.

## Next consumer brief

The analysis agent should read:
1. **YAML header fields & validation rules** from research.schema.yaml (L34–175) — understand how to structure HarnessNode, HarnessEdge, Harness YAML headers.
2. **Cycle detection algorithm** from storage.py:126–179 — confirm BFS approach is suitable for node/edge graphs.
3. **DI & error handling** from api/tasks.py:36–65, 365–406 — plan endpoint signatures and exception mapping.
4. **Findings 1–9** above for design decisions:
   - Pydantic BaseModel + @model_validator(mode="after") for node/edge/harness constraints.
   - Atomic write + YAML round-trip for persistence.
   - Index + file watcher for in-memory caching.
   - Space-scoped storage under `.cronos/harnesses/`.
5. **Key unresolved:** last-writer-wins vs. conflict detection on concurrent updates (note in API docs for now).
6. **Test acceptance criteria:** POST a 3-node/2-edge harness → GET round-trips losslessly; a cycle or dangling edge → 422 HTTP response; on-disk YAML matches API payload byte-for-byte (test YAML dumps consistency).

