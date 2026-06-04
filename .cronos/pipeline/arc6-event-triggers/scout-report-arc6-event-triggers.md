---
cc_version: "1.0"
agent: pipeline-scout
slug: arc6-event-triggers
phase: scout
status: done
confidence: 0.90
inputs_used:
  - memory:project_arc6_board_setup
  - memory:project_arc6_64_run_lifecycle_review
  - backend/app/harnesses/__init__.py
  - backend/app/harnesses/model.py
  - backend/app/harnesses/executor.py
  - backend/app/harnesses/run_trigger.py
  - backend/app/harnesses/run_state.py
  - backend/app/harnesses/cron.py
  - backend/app/api/harnesses.py
  - backend/app/worker.py
  - backend/app/main.py
outputs_produced:
  - .cronos/pipeline/arc6-event-triggers/scout-report-arc6-event-triggers.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - backend/app/harnesses/
    - backend/app/worker.py
    - backend/app/main.py
    - backend/app/api/harnesses.py
  excluded:
    - "frontend/: harness event triggers are a backend subsystem concern"
  strategies:
    - memory_retrieval
    - glob_structural
    - grep_symbol
    - read_targeted
brief: "Add three event Trigger kinds to the harnesses subsystem: task-state-change, webhook, and file-change, with debouncing and fan-out when multiple harnesses subscribe to one event"
metrics:
  tool_calls: 15
  files_read: 11
  memory_hits: 2
---

## Summary

The harnesses subsystem is an async DAG executor for visual agent workflows (Arc 6 SG 6.4 merged). Harness runs are triggered manually via POST `/api/spaces/{space_id}/harnesses/{name}/run` or by the cron loop evaluating trigger nodes. The worker processes task finalization in `_finalize()` and transitions tasks via `store.finalize_run()`. File changes are detected via `watchfiles.awatch()` in `watch_spaces_dir()` with simple per-tool throttling (1-second debounce). Three trigger kinds should integrate as: (1) task-state-change hooks into `_finalize()` to emit after state persistence; (2) webhook routes as a new POST endpoint that enqueues harness runs via the same `enqueue_harness_run()` helper; (3) file-change integrates with existing watcher by extracting events to a shared event bus with per-event debounce windows and harness subscriptions resolved at enqueue time.

## Coverage

### Searched
- backend/app/harnesses/ (13 modules: model, executor, cron, run_trigger, run_state, store, decision, aggregator, validator, wait, interpolate, brief_composer, run_index)
- backend/app/worker.py (1448 lines: _finalize, _run_task, _run_initial_harness_run, _resume_harness_run, _publish event management)
- backend/app/main.py (watch_spaces_dir loop, file event throttling via _sha_throttle dict)
- backend/app/api/harnesses.py (CRUD endpoints, POST /{name}/run trigger, DELETE with active-run guard)

### Excluded
- frontend/: harness triggers are backend-only (no UI changes needed for event schema)
- backend/app/models.py: only reviewed schemas relevant to harness runs (TaskState, Harness, HarnessNode)

### Strategies
- memory_retrieval: 2 relevant entries found (arc6 board structure, run-lifecycle review with worker integration pattern)
- glob_structural: located all harnesses/*.py files via bash find; identified worker.py, main.py, and api/harnesses.py as integration points
- grep_symbol: searched for class HarnessExecutor, event hooks, _publish, finalize, watch patterns
- read_targeted: comprehensively read executor init (lines 241-276), run_state persistence (atomic JSON writes), worker _finalize (lines 729-868), main.py watch_spaces_dir (lines 171-218), cron loop structure (lines 124-200), run_trigger.enqueue_harness_run (lines 34-103), run_state waiting_node_id semantics (lines 92-106)

## Findings

### Task-state-change trigger

**Integration point: `backend/app/worker.py:_finalize()` lines 817–861**

After `store.finalize_run()` persists new_state and the state machine transitions are complete, a task-state-change event should be emitted when `new_state == TaskState.DONE`. The current flow is:
- Line 807: `await self.store.finalize_run()` updates task state in DB
- Lines 817–836: post-DONE autopilot PR hook fires (async but not awaited; side effect)
- Lines 839–861: post-DONE merge task hook for adopted tools
- Lines 864–867: `goal_sync.propagate_to_parent()` for parent goal state propagation

**Design option:** Insert event emission after line 816 (finalize_run succeeds) and before line 817 (PR hook). The event should include task_id, space_id, old_state, new_state, and timestamp (ISO-8601 UTC). Event consumers (harnesses subscribed to this event) should be enqueued immediately via `enqueue_harness_run()` with a standardized brief including the state transition context.

**Coupling avoidance:** Do NOT import harnesses or worker_pool directly into worker.py. Instead, accept an optional event_handler callback in Worker.__init__ (already accepts harness_store, space_store, stats_store, etc.). This keeps worker.py orthogonal.

### Webhook trigger

**Integration point: New endpoint POST `/api/spaces/{space_id}/harnesses/{name}/webhook`**

The existing POST `/{name}/run` endpoint (api/harnesses.py:254–299) is the canonical harness-run trigger. A webhook endpoint should:
- Accept a JSON body with schema: `{ "harness_name": string, "payload": object, "auth_token"?: string }`
- Validate that a webhook is configured on the harness (schema addition to HarnessNode with type=trigger, kind=webhook)
- Call the same `enqueue_harness_run()` helper with brief containing the webhook payload

**Auth scheme:** Basic HTTP Bearer token (static per harness, stored in harness YAML). The endpoint should verify the token before enqueueing; mismatched tokens return 401 Unauthorized.

**Harness schema addition:** HarnessNode with type=trigger gains a kind field ("cron" | "webhook" | "task-state" | "file-change"). Webhook nodes require `data.webhook_path` (e.g. `/my-webhook`) and `data.auth_token`. The API endpoint maps incoming paths to harnesses by matching data.webhook_path.

### File-change trigger

**Integration point: Extend `backend/app/main.py:watch_spaces_dir()` lines 171–218**

Current architecture:
- `watchfiles.awatch()` yields raw filesystem changes (Modify, Add, Delete, etc.)
- For `.md` files: calls `task_store.reindex_path(path)` unconditionally (no debounce)
- For tools manifest: uses `_sha_throttle` dict keyed by (space_id, kind, name) with 1-second debounce window

**Design for file-change triggers:**
1. Extract debounce logic into a shared `EventDebouncer` class that tracks (event_type, path) tuples and enforces debounce_window_seconds (default 0.5s)
2. When a file matches a pattern subscribed to by any harness trigger node (type=trigger, kind=file-change with data.watch_pattern glob), emit a file-change event to the event bus
3. The event bus de-duplicates identical events within the debounce window, then enqueues harness runs with brief containing the file path and event timestamp
4. Reuse existing watcher loop; do NOT spawn a separate watcher

**Watch pattern storage:** HarnessNode with type=trigger, kind=file-change requires `data.watch_pattern` (e.g., `.cronos/tasks/*.md`, `.cronos/spaces/*/settings.yml`) and optional `data.debounce_seconds` (defaults to 0.5). Patterns are glob-style relative to space_dir.

**Fan-out:** When a single file event matches multiple harnesses, each is enqueued once per event (no additional de-duplication across harnesses). De-duplication is per-event, not per-harness.

### Event bus architecture (shared across all three trigger kinds)

**New module: `backend/app/harnesses/event_bus.py`**

Minimal interface to support debouncing and fan-out:

```python
class EventBusEvent(BaseModel):
    """An immutable event that can trigger harness runs."""
    event_id: str  # unique ID for dedup (uuid4)
    kind: str  # 'task-state-change' | 'webhook' | 'file-change'
    timestamp: str  # ISO-8601 UTC when event occurred
    space_id: str
    payload: dict  # kind-specific data (old_state, new_state, path, webhook_body, etc.)

class EventDebouncer:
    """In-memory debounce window tracker with thread-safe expiry."""
    def should_fire(self, event_id: str, debounce_seconds: float) -> bool:
        """Return True if event_id has not fired within debounce_seconds; record fire time."""
        ...

async def fan_out_to_harnesses(
    event: EventBusEvent,
    space_dir: Path,
    harness_store: HarnessStore,
    task_store: TaskStore,
    worker_pool: WorkerPool,
) -> list[str]:
    """Enumerate harnesses subscribed to event.kind, enqueue runs, return run_ids."""
    ...
```

Integration points:
- `_finalize()` in worker.py: after finalize_run succeeds, instantiate EventBusEvent and call fan_out_to_harnesses() (wrapped in try/except to avoid blocking finalize)
- `watch_spaces_dir()` in main.py: when a file event matches any harness watch_pattern, instantiate EventBusEvent and call fan_out_to_harnesses()
- New `/api/spaces/{space_id}/harnesses/{name}/webhook` endpoint: validate auth token, instantiate EventBusEvent, call fan_out_to_harnesses()

### Acceptance criteria mapping

1. **"Moving task to DONE fires subscribed harness"**: Task-state-change event emitted in _finalize() after state transition; fan_out_to_harnesses() queries for type=trigger, kind=task-state-change nodes and enqueues matching harnesses.

2. **"Webhook POST starts run"**: New endpoint validates Bearer token from data.auth_token, instantiates EventBusEvent(kind='webhook', payload=request.json), calls fan_out_to_harnesses().

3. **"Watched file change triggers harness"**: File event in watch_spaces_dir() matches against all harnesses' data.watch_pattern, emits EventBusEvent(kind='file-change', payload={path, mtime, size}), enqueues matches via fan_out_to_harnesses().

4. **"Duplicates within debounce window fire once"**: EventDebouncer.should_fire(event_id, debounce_seconds) gates fan_out_to_harnesses(); identical event_ids within window are dropped.

### Worker._publish() event hook (already in place for SSE)

Line 1339–1376 in worker.py shows that `_publish()` already:
- Appends to per-task `_run_buffer` (ring buffer, capped at _RUN_BUFFER_CAP)
- Distributes to per-task SSE subscribers via `_subscribers[task_id]`
- Forwards lifecycle events (run_start, run_end) to space-level subscribers

For harness event triggers, no SSE changes needed — events are enqueued as harness runs, not emitted as SSE streams.

### Harness model schema changes (minimal)

Current: HarnessNode has `type` (agent|trigger|decision|wait|aggregator) and `data` dict.

Additions to node model validation (validator.py):
- When `type=trigger`, require a `kind` field in `data` (cron|webhook|task-state|file-change)
- **Cron** (existing): data.expression, data.timezone
- **Webhook** (new): data.webhook_path, data.auth_token
- **Task-state** (new): data.watched_state ('DONE'|'WAITING'|etc.)
- **File-change** (new): data.watch_pattern, data.debounce_seconds

Existing cycle detection (validator.py) is unaffected; trigger nodes can be sources or targets in edges.

## Assumptions
- Webhook auth tokens are stored in plaintext in harness YAML (trade-off: simplicity vs. no secrets mgmt). If need arises, migrate to space-scoped secrets API later.
- Event de-duplication uses a simple in-memory dict with time.monotonic() expiry; no Redis or persistent queue. Restart clears the window (acceptable because debounce is sub-second).
- File-change events are scoped per space (space_id is mandatory in EventBusEvent); no global watchers.
- Task-state-change only fires for DONE transitions (not intermediate ACTIVE/WAITING/etc.) to minimize event volume; configurable in acceptance criteria if needed.
- Fan-out to harnesses happens immediately in the event emission context; no persistent event queue (acceptable because enqueue_harness_run is already idempotent and fast).

## Open questions
- None. Brief is clear; architecture is well-scoped; integration points are non-invasive.

## Next consumer brief

**pipeline-analyst** should read:
- `coverage_summary.searched` to understand which modules contain the integration points
- `## Findings` sections for **task-state-change**, **webhook**, and **file-change** to decompose into testable requirements
- `## Findings > Event bus architecture` for the debouncer and fan_out_to_harnesses API contract
- `## Assumptions` for scope boundaries (in-memory debounce, plaintext auth, DONE-only state change)

Key decision points for design phase:
1. Where to call fan_out_to_harnesses() from worker._finalize() — before or after goal_sync.propagate_to_parent() (line 865)?
2. Should webhook path be a harness-level property or per-trigger-node? (Currently proposed: per-node.)
3. Event bus module placement: separate harnesses/event_bus.py or fold into harnesses/__init__.py exports?
4. Should EventDebouncer be a singleton per space or created per event?

Unresolved architectural questions for design phase to refine:
- Should file-change watch_pattern support negation (e.g., `!.cronos/tmp/**`)? Design phase should assess based on anticipated use cases.
- Webhook payload validation schema: should it be configurable per harness or accept any JSON? Propose "accept any JSON" (validation deferred to harness node logic).
- Task-state-change trigger: should it support a condition field (e.g., "only fire if task title matches pattern X") or always fire on DONE?
