---
cc_version: '1.0'
agent: pipeline-architect
slug: arc6-run-lifecycle
phase: design
status: done
confidence: 0.85
inputs_used:
- memory:project_arc6_board_setup
- memory:project_pipeline_foundation_merged
- memory:project_run_agent_pipe_eof_hang
- memory:project_trace_structure
- memory:project_architecture_key_modules
- .cronos/pipeline/arc6-run-lifecycle/analysis-report-arc6-run-lifecycle.md
- .cronos/pipeline/arc6-run-lifecycle/scout-report-arc6-run-lifecycle.md
- backend/app/api/harnesses.py
- backend/app/harnesses/run_state.py
- backend/app/harnesses/executor.py
- backend/app/worker.py
- backend/app/main.py
outputs_produced:
- .cronos/pipeline/arc6-run-lifecycle/design-report-arc6-run-lifecycle.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - backend/app/api/harnesses.py
  - backend/app/harnesses/run_state.py
  - backend/app/harnesses/executor.py
  - backend/app/worker.py
  - backend/app/main.py
  - backend/tests/
  - frontend/src/pages/
  - frontend/src/components/
  - frontend/src/hooks/
  excluded:
  - backend/app/storage.py: harness runs use HarnessExecutor + RunState, not TaskStore
      mutations beyond goal task creation
  - backend/app/agent.py: agent subprocess spawning unaffected by run-lifecycle API
      surface
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
  - glob_structural
iterations:
- id: I1
  type: data
  scope_files:
  - backend/app/harnesses/run_state.py
  - backend/tests/test_harness_run_state.py
  validation_command: cd backend && pytest tests/test_harness_run_state.py -v
  max_diff_lines: 250
  depends_on: []
- id: I2
  type: data
  scope_files:
  - backend/app/harnesses/run_index.py
  - backend/tests/test_harness_run_index.py
  validation_command: cd backend && pytest tests/test_harness_run_index.py -v
  max_diff_lines: 350
  depends_on: []
- id: I3
  type: backend
  scope_files:
  - backend/app/harnesses/executor.py
  - backend/tests/test_harness_executor.py
  validation_command: cd backend && pytest tests/test_harness_executor.py -v
  max_diff_lines: 400
  depends_on:
  - I1
  - I2
- id: I4
  type: backend
  scope_files:
  - backend/app/worker.py
  - backend/tests/test_harness_executor_e2e.py
  validation_command: cd backend && pytest tests/test_harness_executor_e2e.py -v
  max_diff_lines: 300
  depends_on:
  - I3
- id: I5
  type: backend
  scope_files:
  - backend/app/api/harnesses.py
  - backend/app/api/harness_runs.py
  - backend/app/main.py
  - backend/tests/test_api_harnesses.py
  - backend/tests/test_api_harness_runs.py
  validation_command: cd backend && pytest tests/test_api_harnesses.py tests/test_api_harness_runs.py
    -v
  max_diff_lines: 600
  depends_on:
  - I2
  - I4
- id: I6
  type: backend
  scope_files:
  - backend/app/api/harness_runs.py
  - backend/tests/test_api_harness_runs_sse.py
  validation_command: cd backend && pytest tests/test_api_harness_runs_sse.py -v
  max_diff_lines: 350
  depends_on:
  - I4
  - I5
- id: I7
  type: frontend
  scope_files:
  - frontend/src/api.ts
  - frontend/src/hooks/useHarnessRuns.ts
  - frontend/src/hooks/__tests__/useHarnessRuns.test.tsx
  validation_command: cd frontend && npm test -- src/hooks/__tests__/useHarnessRuns.test.tsx
  max_diff_lines: 350
  depends_on:
  - I5
  - I6
- id: I8
  type: frontend
  scope_files:
  - frontend/src/components/HarnessRunPanel.tsx
  - frontend/src/components/__tests__/HarnessRunPanel.test.tsx
  - frontend/src/pages/HarnessRunsPage.tsx
  - frontend/src/pages/__tests__/HarnessRunsPage.test.tsx
  - frontend/src/App.tsx
  validation_command: cd frontend && npm test -- src/components/__tests__/HarnessRunPanel.test.tsx
    src/pages/__tests__/HarnessRunsPage.test.tsx
  max_diff_lines: 500
  depends_on:
  - I7
risks:
- description: HarnessExecutor publishing events into Worker._run_buffer via _publish()
    may collide with the existing task-lifecycle events the Worker already buffers
    under the same task_id key (run_id == goal_task_id). Subscribers to the task SSE
    would then receive interleaved node_transition / edge_chosen frames they cannot
    parse.
  severity: high
  mitigation: 'I3 + I6 enforce a discriminated envelope: every harness event includes
    type in {node_transition, edge_chosen, run_status} on the data payload AND uses
    the SSE event: field to namespace it. Existing task SSE consumers ignore unknown
    event names. test_api_harness_runs_sse.py asserts both event names appear and
    that legacy task events (run_start/run_end) still pass through unchanged.'
- description: Atomic update of the per-harness index file under concurrent POST /run
    + status-change writes can corrupt JSON if two coroutines load-mutate-save_atomic
    in parallel.
  severity: medium
  mitigation: 'I2 introduces a per-index-file asyncio.Lock owned by a module-level
    _index_locks: dict[Path, asyncio.Lock]. All append_run() and update_run_status()
    calls acquire the lock before load and release after save_atomic. test_harness_run_index.py
    includes an asyncio.gather concurrency test that triggers 20 parallel appends
    and asserts all entries survive.'
- description: 'POST /api/harness-runs/{run_id}/cancel races against the executor
    mid-node: bulk-marking pending/in_progress nodes as failed while the executor
    is still writing save_atomic for a completing node can lose the cancellation OR
    resurrect a cancelled node.'
  severity: high
  mitigation: I3 makes the executor re-load RunState from disk at every node-transition
    boundary and check for status=cancelled at the run level (a new RunState.status
    field with default 'running'); if cancelled, it stops the BFS without further
    save_atomic writes. I6 cancel handler sets RunState.status=cancelled, calls worker.stop_current(run_id),
    then bulk-updates pending/in_progress nodes — in that order. The executor's next
    save_atomic merges by re-reading first.
- description: 'Backward-compatibility break: existing RunState JSON files lack started_at,
    ended_at, and the new run-level status field. Loading them after I1 could raise
    KeyError.'
  severity: medium
  mitigation: I1 keeps NodeState.from_dict() using ns.get(...) for all new fields
    (default None) and adds RunState.status with a default of 'running' when absent.
    test_harness_run_state.py adds a fixture loading a legacy JSON blob (no new fields)
    and asserts default values are populated without error.
- description: SSE late-joiner replay relies on Worker._run_buffer which is bounded
    at 2000 events; long-running harnesses with many node transitions plus child-agent
    run_start/run_end could overflow and silently drop early node_transition events
    for late subscribers.
  severity: low
  mitigation: I6 documents the 2000-event cap in the GET /stream docstring and emits
    a buffer_truncated synthetic event when the replay buffer was at capacity at subscribe
    time (worker tracks an _overflow flag per task_id, set when _run_buffer pops the
    oldest event). Frontend (I8) shows a 'history truncated' badge when buffer_truncated
    is observed. The cap is not raised in this iteration — that is a separate Arc
    6 sub-goal.
- description: DELETE harness 409 check reads the index file (per analysis assumption),
    but if the index file is missing for a harness that has never been run, the check
    could falsely 404 or block deletion.
  severity: low
  mitigation: I2's read_index() returns an empty list (not None) when the file does
    not exist. I5 DELETE handler computes any(s.status == 'running' for s in read_index(...))
    which is False for empty lists, allowing deletion to proceed normally. Covered
    by test_api_harnesses.py::test_delete_harness_with_no_runs.
metrics:
  tool_calls: 11
  files_read: 7
  memory_hits: 5
  iterations_planned: 8
---

## Summary

This design exposes harness-run lifecycle over HTTP and SSE by adding two parallel-startable data iterations (NodeState/RunState extensions and the per-harness append-only index file), three sequenced backend iterations (executor event publishing + timing capture, worker `_publish` protocol surface, and the new `harness_runs` router with REST + SSE endpoints), and two frontend iterations (typed client hooks + page/component). The DAG is intentionally wide at the data layer (I1 and I2 run in parallel) and narrows through I3 (executor + protocol) → I4 (worker bridge) before fanning out again into I5 (REST), I6 (SSE), and finally the UI tier. The non-obvious tradeoff is captured in the risk register: SSE reuses `Worker._run_buffer` (analysis assumption) which couples harness events to the task-event channel, mitigated by a discriminated event envelope and namespaced SSE `event:` field. Cancellation race against the executor is handled by introducing a run-level `RunState.status` that the executor checks at every BFS boundary, with the cancel handler writing status before mutating nodes.

## Components

### Data
- `RunState` (extend): add `status: Literal['running','done','failed','cancelled'] = 'running'` for run-level lifecycle and a cancel-race guard; nodes_executed remains the per-node map.
- `NodeState` (extend): add `started_at: str | None = None` and `ended_at: str | None = None` (ISO-8601 UTC), persisted via `to_dict()` / `from_dict()` with backward-compat defaults.
- `RunSummary` (new dataclass in `run_index.py`): `{run_id, harness_id, status, triggered_at, finished_at}` — the index-file entry shape.
- `run_index.py` (new module): `append_run(space_dir, harness_id, summary)`, `update_run_status(space_dir, harness_id, run_id, status, finished_at)`, `read_index(space_dir, harness_id) -> list[RunSummary]`, all atomic with per-file asyncio locks. Index path: `{CRONOS_DATA_DIR}/spaces/{space_id}/.cronos/harness-runs/{harness_id}-index.json`.

### Backend
- `HarnessExecutor.execute()` (modify): set `NodeState.started_at` on transition to `in_progress`; set `ended_at` on transition to `done`/`failed`/`skipped`; publish `node_transition`, `edge_chosen`, `run_status` events via `worker._publish(run_id, event)`; before each node iteration, reload `RunState` and abort if `status == 'cancelled'`; call `run_index.update_run_status()` on terminal run transitions.
- `WorkerProtocol` (extend in executor.py): add `_publish(self, task_id: str, event: dict) -> None` so tests can stub it; the real `Worker._publish` already exists.
- `POST /api/spaces/{space_id}/harnesses/{name}/run` (new, in `api/harnesses.py`): creates a goal task via TaskStore, calls `run_index.append_run` with status=running, enqueues via `worker_pool.enqueue`, returns 202 `{run_id, harness_id, triggered_at}`.
- `GET /api/spaces/{space_id}/harnesses/{name}/runs` (new, in `api/harnesses.py`): reads index file only, returns ordered `RunSummary[]` desc by `triggered_at`.
- `DELETE /api/spaces/{space_id}/harnesses/{name}` (modify): pre-check index for any `status=running`; 409 with active run_ids if present; else fall through to existing delete.
- `api/harness_runs.py` (new router, no space_id prefix): `GET /api/harness-runs/{run_id}` (single RunState read), `POST /api/harness-runs/{run_id}/cancel` (sets status=cancelled, calls worker.stop_current, bulk-marks pending/in_progress nodes failed/reason=cancelled, atomic save, updates index), `GET /api/harness-runs/{run_id}/stream` (SSE; reuses `Worker.subscribe` + `sse_events` keyed by run_id == task_id).
- `main.py` (modify): register `harness_runs_router`; DI for new router via existing `app.state.worker_pool` + `app.state.space_store` lookup of run_id → space_id (loaded by scanning `harness-runs/{run_id}.json` across spaces, cached in worker for fast reverse lookup).

### Frontend
- `frontend/src/api.ts` (modify): add typed clients `triggerHarnessRun`, `listHarnessRuns`, `getHarnessRun`, `cancelHarnessRun`, plus the SSE URL helper `harnessRunStreamUrl(runId)`.
- `frontend/src/hooks/useHarnessRuns.ts` (new): React Query hooks `useHarnessRuns(spaceId, name)`, `useHarnessRun(runId)`, `useTriggerHarnessRun()`, `useCancelHarnessRun()`, plus `useHarnessRunStream(runId)` reusing the `useLiveStream` pattern for SSE.
- `frontend/src/components/HarnessRunPanel.tsx` (new): per-node status badges (`pending`/`in_progress`/`done`/`failed`/`skipped`), live SSE indicator, Run button (calls trigger), Cancel button visible only when `status=running`. Reuses existing pill styles where practical.
- `frontend/src/pages/HarnessRunsPage.tsx` (new): route `/spaces/:spaceId/harnesses/:name/runs` listing history + embedded `HarnessRunPanel` for the focused `run_id`.
- `frontend/src/App.tsx` (modify): register the new route.

## Implementation plan

| ID  | Type     | Depends on | Scope files (abridged)                                                | Validation                                                                                          |
|-----|----------|------------|-----------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------|
| I1  | data     | -          | backend/app/harnesses/run_state.py, tests/test_harness_run_state.py    | cd backend && pytest tests/test_harness_run_state.py -v                                              |
| I2  | data     | -          | backend/app/harnesses/run_index.py, tests/test_harness_run_index.py    | cd backend && pytest tests/test_harness_run_index.py -v                                              |
| I3  | backend  | I1, I2     | backend/app/harnesses/executor.py, tests/test_harness_executor.py      | cd backend && pytest tests/test_harness_executor.py -v                                               |
| I4  | backend  | I3         | backend/app/worker.py, tests/test_harness_executor_e2e.py              | cd backend && pytest tests/test_harness_executor_e2e.py -v                                           |
| I5  | backend  | I2, I4     | backend/app/api/harnesses.py, api/harness_runs.py, main.py, tests/...  | cd backend && pytest tests/test_api_harnesses.py tests/test_api_harness_runs.py -v                   |
| I6  | backend  | I4, I5     | backend/app/api/harness_runs.py, tests/test_api_harness_runs_sse.py    | cd backend && pytest tests/test_api_harness_runs_sse.py -v                                           |
| I7  | frontend | I5, I6     | frontend/src/api.ts, hooks/useHarnessRuns.ts, hooks/__tests__/...      | cd frontend && npm test -- src/hooks/__tests__/useHarnessRuns.test.tsx                               |
| I8  | frontend | I7         | components/HarnessRunPanel.tsx, pages/HarnessRunsPage.tsx, App.tsx     | cd frontend && npm test -- src/components/__tests__/HarnessRunPanel.test.tsx src/pages/__tests__/HarnessRunsPage.test.tsx |

## Risks

| Risk                                                                                                   | Severity | Mitigation                                                                                                                                                                                                                                            |
|--------------------------------------------------------------------------------------------------------|----------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| HarnessExecutor events colliding with task-level events in Worker._run_buffer for the same task_id    | high     | Discriminated envelope `{type}` + SSE `event:` field namespace per I3/I6; SSE test asserts both event names plus legacy task events pass through unchanged.                                                                                            |
| Concurrent index file load-mutate-save corrupting JSON                                                  | medium   | Per-file asyncio.Lock in `_index_locks` (I2); test gathers 20 parallel appends and asserts no loss.                                                                                                                                                    |
| Cancel race against executor mid-node losing or resurrecting cancellation                              | high     | `RunState.status` (I1) + executor re-loads RunState at every BFS boundary (I3); cancel handler writes status → stop_current → bulk-mark nodes in that order (I6).                                                                                       |
| Backward-compat break loading old RunState JSON without new fields                                     | medium   | I1 uses `.get(...)` with defaults for `started_at`, `ended_at`, `status`; explicit legacy-fixture test case added.                                                                                                                                     |
| 2000-event Worker buffer overflow drops early node_transition events for late SSE subscribers          | low      | I6 emits a `buffer_truncated` synthetic event when overflow flag is set; I8 surfaces "history truncated" badge; cap not raised here (separate sub-goal).                                                                                               |
| DELETE harness 409 check fails for never-run harnesses with no index file                              | low      | I2 `read_index` returns `[]` when file is absent; covered by `test_delete_harness_with_no_runs`.                                                                                                                                                       |

## Assumptions

- The analysis report's six decision points are binding: run_id == goal_task_id, append-only per-harness index, SSE reuses Worker._run_buffer, cancellation is atomic-bulk-failure of pending/in_progress nodes, DELETE guard reads the index (not TaskStore), and the new harness-runs router is mounted without a space_id prefix.
- `Worker._publish(task_id, event)` already exists and is the single hook the executor needs; we extend WorkerProtocol's typing surface only (I3) to allow stubs in unit tests without importing the concrete Worker.
- The new `api/harness_runs.py` router can resolve `run_id → space_id` via a cache stored on `app.state.worker_pool` that is populated on `POST /run` (index append). This avoids scanning every space's `.cronos/harness-runs/` directory per request and gives O(1) lookups for `GET /harness-runs/{run_id}` and the SSE/cancel endpoints. Cache is rebuilt at startup by walking each space's index files (cheap: one file per harness).
- The frontend test stack (vitest + React Testing Library) and the `useLiveStream` SSE pattern observed in `frontend/src/hooks/useLiveStream.ts` are sufficient — no new SSE infrastructure is needed in I7.
- Iteration I4's edit to `worker.py` is small (publish method already exists; this iteration only adds the run_id → space_id cache surface plus a 1-line documentation note about the new event types in `_run_buffer`). The diff budget of 300 is generous to allow a docstring expansion.
- Test files in `scope_files[]` that already exist (test_harness_run_state.py, test_harness_executor.py, test_harness_executor_e2e.py, test_api_harnesses.py) are EXTENDED, not replaced; new files (test_harness_run_index.py, test_api_harness_runs.py, test_api_harness_runs_sse.py, the two frontend test files, useHarnessRuns.ts, HarnessRunPanel.tsx, HarnessRunsPage.tsx, api/harness_runs.py, harnesses/run_index.py) are CREATED.

## Open questions

- None. All six scout decision points and the analyst's Next-consumer-brief items are bound in Assumptions or in iteration scopes.

## Next consumer brief

Implementor: load `iterations[]` from this report's YAML and execute one entry at a time in DAG order. The orchestrator will fan I1+I2 in layer 0, I3 in layer 1, I4 in layer 2, I5 in layer 3, I6 in layer 4, I7 in layer 5, I8 in layer 6. Cross-iteration invariants not derivable from YAML: (a) the SSE event `type` literals MUST be exactly `"node_transition"`, `"edge_chosen"`, `"run_status"` — both the executor (I3) and the SSE serializer (I6) AND the frontend hook (I7) read these strings literally; (b) the index file path template is `{CRONOS_DATA_DIR}/spaces/{space_id}/.cronos/harness-runs/{harness_id}-index.json` — used identically in I2 (writer) and I5 (DELETE guard + GET /runs reader); (c) `RunState.status` defaults to `'running'` when absent from JSON, and the executor must NOT overwrite a `'cancelled'` value when persisting (load-merge-save discipline in I3). Reviewer: pay particular attention to the I3 executor edit — the load-merge-save discipline is the load-bearing piece of the cancellation race mitigation.
