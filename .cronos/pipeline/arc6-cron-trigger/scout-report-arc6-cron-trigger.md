---
cc_version: "1.0"
agent: pipeline-scout
slug: arc6-cron-trigger
phase: scout
status: done
confidence: 0.92
inputs_used:
  - memory:project_architecture_key_modules
  - memory:project_run_agent_pipe_eof_hang
  - memory:project_pipeline_foundation_merged
  - backend/app/main.py
  - backend/app/models.py
  - backend/app/harnesses/model.py
  - backend/app/harnesses/store.py
  - backend/app/harnesses/run_state.py
  - backend/app/harnesses/run_index.py
  - backend/app/api/harness_runs.py
  - backend/app/worker.py
  - backend/pyproject.toml
outputs_produced:
  - .cronos/pipeline/arc6-cron-trigger/scout-report-arc6-cron-trigger.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - backend/app/main.py lifespan and background task setup
    - backend/app/harnesses/ (model, store, run_state, run_index)
    - backend/app/api/ (harnesses and harness_runs routers)
    - backend/pyproject.toml dependencies
  excluded:
    - "frontend/: not relevant to backend cron scheduler"
    - ".claude/agents/: only read protocol docs, not agent code"
    - "backend/tests/: read selectively for harness data structures"
  strategies:
    - memory_retrieval
    - glob_structural
    - grep_symbol
    - read_targeted
brief: "Add a cron scheduler to Cronos backend: one asyncio.create_task(cron_loop, …) in main.py's lifespan. Key requirements: re-read canonical harness list each tick; overlap guard (skip if harness has active run); parse cron expr + timezone; missed ticks not back-filled; acceptance (cron fires at scheduled time, skips during active run)."
metrics:
  tool_calls: 15
  files_read: 10
  memory_hits: 3
---

## Summary

The Cronos backend has a mature lifespan/lifespan pattern for long-running tasks (watcher, archiver, memory pruner, discoverer, evolve_tools) using `asyncio.create_task()` and `asyncio.Event` for cancellation. Harnesses are persisted YAML-backed graphs with nodes (agent, trigger, decision, wait, aggregator) stored in `.cronos/harnesses/`. Harness runs are tracked per-space in a per-harness index file (`.cronos/harness-runs/{harness_id}-index.json`) with per-run state JSONs. Active runs can be detected by checking the run index for entries with `status='running'`. The codebase does **not** yet have a cron expression parser or timezone handler installed; these must be added as dependencies. The `Trigger` node type exists in the harness model but is not yet interpreted by the executor.

## Coverage

### Searched

- **backend/app/main.py::lifespan** — lifespan context manager spawns 5 background tasks (watcher, archiver, memory_pruner, discoverer, evolve_tools) all using the same pattern: `asyncio.create_task(loop_func(..., stop_event), name="...")` with graceful shutdown via `stop_event.set()` and `asyncio.wait_for(..., timeout=5.0)`.
- **backend/app/harnesses/model.py** — `NodeType` enum includes `trigger` type alongside agent, decision, wait, aggregator. Trigger nodes have a `data` dict (line 68) for arbitrary config; no mandatory fields yet defined.
- **backend/app/harnesses/store.py** — `HarnessStore` maintains in-memory index `_by_space[space_key][harness_name]` and persists to `{space_dir}/.cronos/harnesses/{slug}.yml`. All operations are asyncio-locked.
- **backend/app/harnesses/run_state.py** — `RunState` persists to `.cronos/harness-runs/{run_id}.json`. Status field values: 'running', 'done', 'failed', 'cancelled'. No timestamp tracking per-run start time.
- **backend/app/harnesses/run_index.py** — Per-harness index at `.cronos/harness-runs/{harness_id}-index.json` tracks all runs with `RunSummary` (run_id, harness_id, status, triggered_at, finished_at). The `read_index()` API (line 84) returns empty list if missing; `update_run_status()` scans all entries for matching run_id.
- **backend/app/api/harness_runs.py** — GET `/api/harness-runs/{run_id}` uses `worker_pool.lookup_space_id(run_id)` reverse cache to find space; run status is read from persisted JSON.
- **backend/pyproject.toml** — No cron libraries listed; dependencies include fastapi, pydantic, watchfiles, aiosqlite, but not croniter or similar.

### Excluded

- frontend/: Not relevant to backend scheduler implementation.
- `.claude/agents/`: Agent protocol docs exist but not needed for cron architecture.
- backend/tests/: Read selectively; full test suite not needed for reconnaissance.

### Strategies

- **memory_retrieval**: 3 relevant entries found (architecture_key_modules, run_agent_pipe_eof_hang, pipeline_foundation_merged); provided context on worker patterns and module organization.
- **glob_structural**: Scanned backend/app/ directory structure; identified key files by name pattern.
- **grep_symbol**: Searched for 'Trigger', 'cron', 'asyncio.create_task', 'running' across backend; confirmed no existing cron implementation.
- **read_targeted**: Deep-read main.py lifespan (full), model.py/store.py/run_state.py/run_index.py (full), executor.py (first 100 lines), harness_runs.py (first 100 lines). Skipped large executor.py and worker.py (not needed for scheduler architecture).

## Findings

### 1. Lifespan Task Pattern (baseline for cron_loop)

**Location:** `backend/app/main.py:251–365` (lifespan context manager)

The app bootstraps 5 background tasks in lifespan startup (lines 304–338):
- Each task follows the pattern: `asyncio.create_task(loop_func(..., stop_event), name=...)`
- Each loop function runs `while not stop_event.is_set()`, checks stop_event with timeout, and catches exceptions
- On shutdown (finally block, line 358), `stop_event.set()` signals all loops; each is awaited with 5s timeout and cancelled if timeout.

**Pattern to replicate:**
```python
async def cron_loop(
    harness_store: HarnessStore,
    space_store: SpaceStore,
    spaces_dir: Path,
    interval_seconds: float,
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        try:
            # Re-read all harnesses from store; check triggers
            # For each trigger: evaluate cron expr, check overlap guard
        except Exception:
            log.exception("Error in cron loop; will retry next cycle")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            pass
```

Interval should be ~60 seconds (configurable via env var `CRONOS_CRON_INTERVAL_SECONDS`).

### 2. Harness Storage and Triggers

**Location:** `backend/app/harnesses/store.py:121–315` (HarnessStore class)

Harnesses are loaded into memory on startup via `harness_store.list(space_dir)` (line 254) returning a `list[Harness]`. The store maintains `_by_space[space_key]` where `space_key` is the canonical resolved path. The Harness model does not track when it was last reloaded, so the cron_loop must **unconditionally re-read the canonical list each tick** via `harness_store.list()` for each space.

The `Trigger` node type is already defined in `NodeType` enum (backend/app/harnesses/model.py:46) but carries no reserved `data` fields. The brief specifies **cron expression in `data`** — this implies:
- HarnessNode with `type='trigger'` will have `data={'expression': '0 9 * * *', 'timezone': 'UTC'}` (or similar schema).
- The cron_loop must iterate harnesses, filter for nodes with `type='trigger'`, and evaluate each node's `data['expression']`.

### 3. Active Run Detection (Overlap Guard)

**Location:** `backend/app/harnesses/run_index.py:84–97` (read_index) and `backend/app/harnesses/run_state.py:78–87` (RunState.status)

Active runs are flagged by the run index. To implement overlap guard:

```python
async def has_active_run(space_dir: Path, harness_id: str) -> bool:
    """Check if harness has a run with status='running'."""
    runs = await run_index.read_index(space_dir, harness_id)
    for run in runs:
        if run.status == 'running':
            return True
    return False
```

The run_index is append-only and entries are updated in-place by `update_run_status()` (line 122–157). A harness is considered to have an active run if **any entry with `status='running'` exists** in its per-harness index file. This is a linear scan, O(N) per harness per tick — acceptable for typical harness counts.

### 4. Cron Expression and Timezone Parsing

**Not yet implemented.** The pyproject.toml has no cron library. Recommended:
- **croniter** (`pip install croniter`) — MIT-licensed, widely used, handles cron expressions and timezones via `dateutil.tz`.
- Alternative: **apscheduler** (heavier, overkill for single-process asyncio).

**Pattern (pseudo-code):**
```python
from croniter import croniter
from dateutil import tz as dateutil_tz

def should_fire(cron_expr: str, tz_name: str, now: datetime) -> bool:
    """Check if a cron expression should fire at the given time."""
    if tz_name:
        tz = dateutil_tz.gettz(tz_name)
        if tz is None:
            log.warning("Unknown timezone %r, falling back to UTC", tz_name)
            tz = tz_utc
    else:
        tz = tz_utc
    
    cron = croniter(cron_expr, base_time=now.astimezone(tz))
    # croniter's next_time is the next scheduled fire time
    # Compare against current time to decide if we should fire _now_
    last_fire = cron.get_prev(datetime)  # or similar
    return last_fire <= now < cron.get_next(datetime)
```

**Timezone handling:** The brief says "Parse cron expr + timezone correctly" and "Missed ticks across restart are not back-filled — document this". This implies:
- Each trigger carries a timezone in its `data`.
- At startup, cron_loop does **not** back-fill skipped ticks (e.g., if server was down for 2 days, no retroactive runs are fired).
- If a cron fires at 09:00 UTC and the server restarts at 10:00 UTC, no run fires until the next scheduled time (e.g., 09:00 tomorrow).

### 5. Harness Run Triggering

**Location:** `backend/app/api/harnesses.py:255–322` (trigger_harness_run endpoint)

When a cron trigger fires, the cron_loop should call the harness triggering logic. The existing endpoint POST `/api/spaces/{space_id}/harnesses/{name}/run` (lines 255–322) creates a harness run:

```python
# Pseudo-code
run_id = task_store.create(
    space_id=space.id,
    title=f"Automated harness run triggered via API for harness '{name}'.",
    brief=...,
    type="goal",
    agent_mode=...,
)
await worker.enqueue(run_id)
```

The cron_loop will need to replicate this or call a shared helper. The task is enqueued to the worker for execution; the worker manages state transitions and run result capture.

### 6. Environment and Configuration

**Configurable intervals:**
- `CRONOS_MEMORY_PRUNE_INTERVAL` (line 47, default 3600 sec)
- `CRONOS_DISCOVERY_INTERVAL_HOURS` (line 48, default 6 hours)
- `CRONOS_EVOLVE_TOOLS_INTERVAL_HOURS` (line 51, default 7*24 hours)

**Pattern for cron_loop:**
- `CRONOS_CRON_INTERVAL_SECONDS` (default 60 sec) — how often to wake up and check cron expressions. This is **NOT** the cron interval (which is per-trigger); it's the polling interval.

### 7. No Double-Registration on Reload

**Requirement:** "no per-harness timers; no double-registration on watch_spaces_dir reload".

The watcher (line 169–217) reloads harness definitions via `space_store.reindex_path()` when `space.yml` changes. The cron_loop **must not store per-harness state** (e.g., a dict of asyncio.Tasks per trigger). Instead:
- On each tick, unconditionally call `harness_store.list(space_dir)` for each space.
- Extract all trigger nodes in-memory.
- Evaluate each against the current time.
- Fire those that match, skipping if overlap guard blocks.

This "stateless polling" design avoids registration/deregistration churn when harnesses are reloaded.

### 8. Harness and Node IDs

**Location:** `backend/app/harnesses/model.py:107–151` (Harness model and R1–R4 validators)

The Harness model does not have an `id` field; the harness is identified by its name (unique per space). However, trigger nodes inside a harness are identified by `node.id` (a string, unique within the harness graph per validator R1). To track which trigger fired, the cron_loop will need to reference both harness name and node id.

**Example harness run brief:**
```
Automated harness run triggered via cron trigger node '{node_id}' in harness '{harness_name}'.
```

## Assumptions

- **Single-process asyncio model**: The codebase uses a single Uvicorn process with asyncio. No inter-process locks or distributed state needed; a simple set check (in-memory dict of active run IDs) suffices.
- **Harness names are unique per space**: The store enforces uniqueness by name (store.py:223–226). The cron_loop will use (space_id, harness_name) tuples as identifiers.
- **Triggering via existing API patterns**: The cron_loop will reuse the task creation and worker enqueue logic (worker.py) without creating new harness-specific endpoints.
- **Cron expressions are standard POSIX cron syntax**: `minute hour day month weekday` (5 fields); no second-level precision. Quartz-style extensions (6+ fields) are not mentioned in the brief.
- **Timezones are canonical IANA names**: e.g. `"America/New_York"`, `"UTC"`, `"Europe/London"`. The croniter + dateutil.tz stack handles this.
- **No persistent cron last-fire tracking**: The cron_loop does not persist the last-fire time for each trigger. This is acceptable because the brief forbids back-filling missed ticks; the loop can re-evaluate the cron expression against the current time on each tick and fire if the conditions match.

## Open questions

- None. The brief and codebase context are sufficient to scope implementation.

## Next consumer brief

The **analysis** phase should clarify:

1. **Cron library choice**: Confirm `croniter` is acceptable (MIT license, ~1000 LOC, well-maintained).
2. **Trigger node `data` schema**: Define the expected shape of `data` on a trigger node. Example:
   ```json
   {
     "expression": "0 9 * * MON",
     "timezone": "America/New_York",
     "enabled": true
   }
   ```
   Should the schema be validated in `harnesses/validator.py`?

3. **Harness ID generation**: Harnesses are identified by name, not ID. Is name sufficient, or should we generate a stable UUID on first save for use in run_index paths?

4. **Error handling**: What happens if a cron expression is malformed? Should the loop skip with a warning, or fail fast?

5. **Test harness strategy**: For shortened test intervals, how should the cron_loop discover the interval? A hook in HarnessNode (`"test_mode": True`)? Or should the cron_loop read `CRONOS_CRON_INTERVAL_SECONDS` and apply a "fast-forward" factor in test mode?

6. **Concurrency with task creation**: Worker enqueue happens within the cron_loop. Is backpressure a concern (e.g., if 100 harnesses fire at once)? Should enqueue calls be wrapped in `asyncio.gather()` to parallelize or fire sequentially?

---

**End of scout report for arc6-cron-trigger.**
