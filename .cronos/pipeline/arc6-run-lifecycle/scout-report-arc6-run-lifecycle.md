---
cc_version: "1.0"
agent: pipeline-scout
slug: arc6-run-lifecycle
phase: scout
status: done
confidence: 0.90
inputs_used:
  - memory:project_pipeline_foundation_merged
  - memory:project_arc6_board_setup
  - memory:project_run_agent_pipe_eof_hang
  - memory:project_trace_structure
  - backend/app/worker.py
  - backend/app/harnesses/executor.py
  - backend/app/harnesses/run_state.py
  - backend/app/api/tasks.py
  - backend/app/api/harnesses.py
outputs_produced:
  - .cronos/pipeline/arc6-run-lifecycle/scout-report-arc6-run-lifecycle.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - backend/app/worker.py (SSE + lifecycle patterns)
    - backend/app/harnesses/ (run state + executor)
    - backend/app/api/ (task/harness CRUD routes)
  excluded:
    - frontend/: UI implementation deferred to design phase
  strategies:
    - memory_retrieval
    - glob_structural
    - grep_symbol
    - read_targeted
brief: "Research the existing harness infrastructure, run lifecycle tracking, and SSE patterns in the codebase to scope the feature request for exposing runtime state over HTTP with live status updates and cancellation."
metrics:
  tool_calls: 14
  files_read: 5
  memory_hits: 4
---

## Summary

The codebase has mature run lifecycle tracking and SSE infrastructure in `worker.py` for tasks, 
but no harness-run-level HTTP API exists yet. Harness execution is managed by `HarnessExecutor` 
which persists `RunState` (node-by-node progress) as JSON; runs are keyed by goal task IDs. 
The Worker class already implements `subscribe()` / `sse_events()` for task-level streaming with 
event buffering (`_run_buffer`, 2000-event cap) supporting late-joiner replay. To expose 
harness-run state via HTTP, the feature must bridge the executor's JSON-based `RunState` 
model to the Worker's SSE machinery while handling task-to-run mapping and cancellation.

## Coverage

### Searched
- **backend/app/worker.py** — Worker class with SSE subscription model, `_run_buffer`, 
  `subscribe()` / `sse_events()` generator, and lifecycle event publishing
- **backend/app/harnesses/executor.py** — HarnessExecutor.execute() with runtime-gated BFS, 
  RunState persistence, fail-fast semantics, and resume reconciliation
- **backend/app/harnesses/run_state.py** — RunState / NodeState dataclasses, atomic JSON 
  persistence, waiting_node_id routing for human Wait nodes
- **backend/app/api/tasks.py** — Task CRUD routes, `GET /{task_id}/stream` SSE endpoint 
  (lines 584–595), WorkerPool integration
- **backend/app/api/harnesses.py** — Harness CRUD routes (GET list, POST create, PUT update, 
  DELETE); no run-level endpoints

### Excluded
- frontend/: UI layer out of scope for reconnaissance phase
- backend/app/agent.py: agent spawning (not directly relevant to run exposure)
- Test suites: coverage verified in memory, not reread

### Strategies
- **memory_retrieval**: 4 relevant entries (pipeline foundation, arc6 setup, run lifecycle 
  fix, trace structure)
- **glob_structural**: targeted file discovery (harnesses/, api/, worker.py)
- **grep_symbol**: pattern searches (subscribe, sse_events, RunState, run_id)
- **read_targeted**: focused reads of executor, worker, and API modules to depth needed

## Findings

### 1. Worker SSE Infrastructure (Production-Ready)

**Location**: `backend/app/worker.py:266–277`, `1237–1258`

The Worker class provides:
- `subscribe(task_id) → (replay, queue)`: returns buffered past events + live async.Queue
- `_run_buffer: dict[task_id → list[dict]]`: circular buffer (2000-event cap) of published 
  events per task
- `_publish(task_id, event)` broadcasts to all subscribers + appends to buffer (FIFO overflow)
- `sse_events(task_id, worker) → AsyncIterator[str]`: async generator yielding SSE lines
  - Flushes replay first (lines already in buffer)
  - Streams live events from queue
  - Sends `event: end` sentinel on queue termination
  - Handles slow subscribers via backpressure (drop oldest if queue full)

**Event types emitted**: `run_start`, `run_end`, `goal_child_start`, `goal_child_end`, 
`goal_child_skipped`, `pr_opened`, `run_error` (task-level); space-level subscribers 
receive only `run_start`/`run_end` (lines 1192–1204).

### 2. RunState Model (Harness-Specific Lifecycle)

**Location**: `backend/app/harnesses/run_state.py`

- **RunState**: keyed by `run_id` (typically goal task ID), tracks `harness_id`, `goal_task_id`, 
  `nodes_executed: dict[node_id → NodeState]`, and `waiting_node_id` (for human Wait resume).
- **NodeState**: status ∈ {pending, in_progress, done, failed, skipped}, plus optional 
  `child_task_id` (populated when a node spawns a task), `output` (for aggregator results), 
  and `reason` (skip/fail cause).
- **Persistence**: atomic JSON at `{CRONOS_DATA_DIR}/spaces/{space_id}/.cronos/harness-runs/{run_id}.json`
- **Resume reconciliation**: executor reconciles `in_progress` nodes against TaskStore before 
  resuming (lines 298–320 executor.py); if child task is DONE, node accepted as done; 
  otherwise re-executed.

### 3. HarnessExecutor Lifecycle

**Location**: `backend/app/harnesses/executor.py:249–296`

The executor's `execute(run_goal_id, harness, space) → RunState`:
- Loads existing RunState if present (resume), else initializes fresh
- Walks harness graph via runtime-gated BFS (in-degree based, not static Kahn)
- For each node: calls `worker.run_agent()` (Agent nodes) or dispatches to 
  `decision.evaluate_decision()`, `wait.enter_wait()`, `aggregator.aggregator_ready()`
- On non-DONE child outcome: marks remaining un-executed nodes `skipped` with 
  `reason='upstream_failed'` and halts (fail-fast)
- Persists RunState to JSON after each node transition
- On human Wait: sets `waiting_node_id`, returns RunState, goal transitioned to WAITING; 
  resume re-enters executor which checks `waiting_node_id` and resumes from Wait node's edges

### 4. Task-to-Run Mapping

**Location**: `backend/app/worker.py:346–464` (_resume_harness_run)

Worker detects a WAITING harness run by:
1. Checking if run-state JSON exists at 
   `{CRONOS_DATA_DIR}/spaces/{task.space_id}/.cronos/harness-runs/{task_id}.json`
2. If found and `waiting_node_id` is set: delegates to `executor.execute(task_id, harness, space)`
3. RunState is persisted; next worker resumption checks for file existence again

**Implication**: Run identity is **task identity** (goal task ID). Multiple runs of the same 
harness reuse the same run-state file (overwrite). History/audit requires external tracking.

### 5. Cancellation Patterns

**Location**: `backend/app/worker.py:255–264`, `486–488`, `964–965`

- Worker tracks `_current_cancel: asyncio.Event` per task
- `stop_current(task_id) → bool`: sets cancel event if task is actively running
- On cancel: agent subprocess is terminated (line 512); result.stopped flag propagates 
  to finalization logic (lines 597–598, 900–901)
- For harness runs: cancellation hits the current child task via same mechanism 
  (cancel event passed to run_agent)

**Gap**: No mechanism to atomically abort harness mid-execution and mark run failed; 
cancel only works on currently-executing child. Remaining unexecuted nodes would stay 
pending if harness goal is re-triggered.

### 6. Existing API Routes

**Harness CRUD** (`backend/app/api/harnesses.py`):
- `GET /api/spaces/{space_id}/harnesses` — list all harnesses
- `POST /api/spaces/{space_id}/harnesses` — create harness (HTTP 201)
- `GET /api/spaces/{space_id}/harnesses/{name}` — fetch by name
- `PUT /api/spaces/{space_id}/harnesses/{name}` — replace harness
- `DELETE /api/spaces/{space_id}/harnesses/{name}` — delete (HTTP 204)

**Task SSE** (`backend/app/api/tasks.py:584–595`):
- `GET /api/tasks/{task_id}/stream` — SSE stream for task lifecycle (no run_id parameter)

**Task run history** (`backend/app/api/tasks.py`):
- No dedicated run-history list endpoint; runs tracked via TaskStore + stats_store 
  (backward-compatible per-task aggregation)

### 7. Scope Implications

**Request asks for**:
- `POST .../harnesses/<name>/run` → manual trigger, returns `run_id`
  - **Blocker**: No separate run ID scheme; run_id = goal_task_id. Need to define 
    how to trigger (create task + enqueue, or direct executor call?)
- `GET .../harnesses/<name>/runs` — run-history list
  - **Gap**: No history store; RunState is overwritten on each run. Need audit trail 
    (e.g., append-only log or timestamped snapshots)
- `GET .../harness-runs/<run_id>` — per-node state + edges + timings
  - **Available**: RunState JSON has node states; edges stored in Harness model; 
    need to synthesize snapshot response schema
- `POST .../harness-runs/<run_id>/cancel` — stop child, abort interpreter, mark failed
  - **Partial**: Worker.stop_current() exists; need atomic failure mark + unexecuted-node 
    cleanup
- **Run-level SSE** `GET .../harness-runs/<run_id>/stream` — node/edge transitions
  - **Design choice**: Either inject executor events into Worker._run_buffer (requires 
    coupling), or build parallel buffer in harness module (isolation). Former easier 
    if run_id = task_id.

## Assumptions

- Run identity is **goal task ID** (not a separate serial run counter). This aligns executor 
  persistence (run-state keyed by task_id) with Worker's task-centric model.
- Harness runs are **not transactional**; cancellation mid-node leaves task orphaned and 
  requires manual recovery.
- SSE buffering strategy (2000-event limit) is adequate for harness traces; executor node 
  events + child agent events fit within one run.
- History is **not** required for MVP; first run always overwrites prior (acceptable for 
  Arc 6 scope).

## Open questions

- **Run ID scheme**: Should manual trigger create a new Goal task, or should runs be tracked 
  without task overhead? (impacts how SSE maps to Worker infrastructure)
- **Run history**: Is append-only log (e.g., run-{timestamp}.json) required, or 
  snapshot-on-demand (one .json per harness)?
- **Failure atomicity**: When cancel is issued, should all unexecuted nodes be marked failed, 
  or left pending for manual re-trigger?

## Next consumer brief

**Analysis agent** should focus on:

1. **Run ID strategy**: Decide whether run_id = task_id or introduce separate serial counter. 
   First choice couples to Worker + TaskStore; second requires new persistence layer.

2. **SSE bridge design**: Executor runs either in Worker context (task-level events bubble 
   to _run_buffer) or independently (new buffer, new /stream endpoint). Former reuses 
   proven code; latter cleaner isolation.

3. **History model**: Define whether history is required for MVP or can ship 
   single-snapshot (one RunState JSON per harness). Append-only log vs. indexed snapshots.

4. **Cancellation semantics**: Clarify whether cancel should atomically mark remaining nodes 
   failed or leave pending. First option simpler (bulk update NodeState); second requires 
   recovery procedures.

5. **API path design**: Settle on `/harnesses/{name}/run`, `/harnesses/{name}/runs`, 
   `/harness-runs/{run_id}` vs. `/spaces/{space_id}/harnesses/{name}/runs/{run_id}` (path 
   consistency with task routes).

6. **Per-node timings**: RunState has no started_at/ended_at per node. Need to add to 
   NodeState or derive from task run traces (the latter requires N+1 TraceStore reads — 
   request says avoid).

Key decision deps: RunState scope (1.2 → design), SSE bridge (2.0 → design), history 
(3.0 → design). Proceed to analysis phase.
