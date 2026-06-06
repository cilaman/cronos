---
cc_version: '1.0'
agent: pipeline-analyst
slug: arc6-run-lifecycle
phase: analysis
status: done
confidence: 0.88
inputs_used:
- memory:project_arc6_board_setup
- memory:project_pipeline_foundation_merged
- memory:project_run_agent_pipe_eof_hang
- memory:project_trace_structure
- .cronos/pipeline/arc6-run-lifecycle/scout-report-arc6-run-lifecycle.md
- backend/app/api/harnesses.py
- backend/app/harnesses/run_state.py
- backend/app/harnesses/executor.py
- backend/app/worker.py
outputs_produced:
- .cronos/pipeline/arc6-run-lifecycle/analysis-report-arc6-run-lifecycle.md
blockers: []
next_consumer: design
request: 'Expose the runtime over HTTP and round out lifecycle in `backend/app/api/harnesses.py`.

  - `POST .../harnesses/<name>/run` — manual trigger, returns `run_id`. - `GET  .../harnesses/<name>/runs`
  — run-history list. - `GET  .../harness-runs/<run_id>` — status: per-node state,
  chosen edges, child ids, timings (snapshot; avoid N+1 trace reads). - `POST .../harness-runs/<run_id>/cancel`
  — stop the current child (`stop_current` / `_current_cancel`), abort the interpreter,
  mark the run failed atomically. `DELETE` a harness with active runs handled cleanly.
  - **Run-level SSE** `GET .../harness-runs/<run_id>/stream` emitting node/edge transitions,
  built on `subscribe`/`sse_events`/`_run_buffer` replay in worker.py (late joiners
  get the backlog).

  Acceptance: POST /run executes; GET status reflects live per-node state; cancel
  stops a mid-flight run; SSE replays prior transitions to a late subscriber.'
has_ui: true
coverage_summary:
  searched:
  - backend/app/api/harnesses.py
  - backend/app/harnesses/run_state.py
  - backend/app/harnesses/executor.py
  - backend/app/worker.py (lines 255-294)
  excluded:
  - frontend/: deferred to design phase per scout exclusion
  - backend/tests/: not re-read; coverage verified via memory
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
traceability:
- requirement_id: R1
  statement: POST /api/spaces/{space_id}/harnesses/{name}/run creates a goal task,
    enqueues it for Worker execution, and returns run_id (= goal task ID) plus harness_id
    and triggered_at in the response body.
  acceptance_criteria:
  - Given a valid harness name and space_id, when POST /run is called, then HTTP 202
    is returned with a JSON body containing run_id, harness_id, and triggered_at.
  - Given an unknown harness name, when POST /run is called, then HTTP 404 is returned.
  - Given a valid trigger, when the Worker picks up the task, then HarnessExecutor.execute()
    is invoked and RunState is persisted at {CRONOS_DATA_DIR}/spaces/{space_id}/.cronos/harness-runs/{run_id}.json.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R2
  statement: GET /api/spaces/{space_id}/harnesses/{name}/runs returns an ordered list
    of RunSummary objects (run_id, harness_id, status, triggered_at, finished_at)
    for all recorded runs of the named harness, derived from the run-index file without
    re-reading individual RunState blobs.
  acceptance_criteria:
  - Given runs exist for a harness, when GET /runs is called, then HTTP 200 is returned
    with a JSON array ordered by triggered_at descending.
  - Given no runs exist, when GET /runs is called, then HTTP 200 is returned with
    an empty array.
  - 'Each RunSummary entry must include: run_id, harness_id, status (one of running/done/failed/cancelled),
    triggered_at, and optionally finished_at.'
  - The endpoint must not read individual {run_id}.json files — it reads only the
    harness-level index (single file, O(1) I/O per harness).
  verifying_phase: test
  confidence: 0.85
- requirement_id: R3
  statement: The system maintains a per-harness append-only run index file at {CRONOS_DATA_DIR}/spaces/{space_id}/.cronos/harness-runs/{harness_id}-index.json
    that records a RunSummary entry for every run; entries are appended on trigger
    and updated atomically on status change.
  acceptance_criteria:
  - Given a POST /run succeeds, then a RunSummary entry with status=running is appended
    to the index file within the same request-response cycle.
  - Given a run transitions to done/failed/cancelled, then the index entry for that
    run_id is updated atomically (status + finished_at) without rewriting other entries.
  - Given a crash between trigger and first executor step, then re-reading the index
    still reflects the triggered run (no silent loss).
  verifying_phase: test
  confidence: 0.82
- requirement_id: R4
  statement: 'GET /api/harness-runs/{run_id} returns a snapshot of the full RunState
    for a single run: per-node status, child_task_id, reason, started_at/ended_at
    timings, chosen outgoing edges, and the waiting_node_id if applicable — all served
    from the {run_id}.json file without additional TraceStore reads.'
  acceptance_criteria:
  - Given a run_id that exists, when GET /harness-runs/{run_id} is called, then HTTP
    200 is returned with a body containing run_id, harness_id, goal_task_id, status,
    nodes_executed (map of node_id to NodeState), chosen_edges, waiting_node_id.
  - 'Each NodeState in the response includes: status, child_task_id (nullable), reason
    (nullable), started_at (nullable ISO-8601), ended_at (nullable ISO-8601).'
  - Given a run_id that does not exist, then HTTP 404 is returned.
  - The response is generated from a single RunState JSON read; no TraceStore or TaskStore
    reads are performed per node.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R5
  statement: NodeState gains started_at and ended_at fields (ISO-8601 UTC strings,
    nullable) recorded by HarnessExecutor immediately before and after each node execution,
    and persisted in the RunState JSON.
  acceptance_criteria:
  - Given an Agent node transitions to in_progress, then NodeState.started_at is set
    to the current UTC timestamp and persisted atomically.
  - Given a node transitions to done/failed/skipped, then NodeState.ended_at is set
    to the current UTC timestamp and persisted atomically.
  - Given a control-flow node (decision/wait/aggregator), then started_at and ended_at
    are similarly recorded.
  - Existing RunState JSON files without these fields load without error (fields default
    to None).
  verifying_phase: test
  confidence: 0.9
- requirement_id: R6
  statement: POST /api/harness-runs/{run_id}/cancel stops the currently-executing
    child task via Worker.stop_current(), marks all nodes that are in_progress or
    pending as failed with reason=cancelled, persists the updated RunState atomically,
    and updates the run index entry to status=cancelled.
  acceptance_criteria:
  - Given a run is actively executing, when POST /cancel is called, then Worker.stop_current(run_id)
    is invoked and returns True, and HTTP 202 is returned.
  - Given the cancellation succeeds, then all in_progress and pending nodes in the
    RunState are set to status=failed with reason=cancelled and the file is atomically
    overwritten.
  - Given a run that is already done/failed/cancelled, when POST /cancel is called,
    then HTTP 409 is returned with detail=run is not active.
  - Given a run_id that does not exist, then HTTP 404 is returned.
  verifying_phase: test
  confidence: 0.85
- requirement_id: R7
  statement: DELETE /api/spaces/{space_id}/harnesses/{name} returns HTTP 409 if any
    run for that harness has status=running; it proceeds with deletion only when no
    active runs exist.
  acceptance_criteria:
  - Given a harness with one or more runs in status=running, when DELETE is called,
    then HTTP 409 is returned with detail listing the active run_ids.
  - Given a harness with only done/failed/cancelled runs (or no runs), when DELETE
    is called, then HTTP 204 is returned and the harness is removed.
  - The active-run check reads the harness run index (O(1) file read), not TaskStore.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R8
  statement: 'GET /api/harness-runs/{run_id}/stream is an SSE endpoint that replays
    all buffered node/edge transition events for the run (late-joiner backlog via
    Worker.subscribe(run_id)) followed by live events; it emits event: end when the
    run terminates.'
  acceptance_criteria:
  - Given a late-joining client, when GET /stream is called on a run that has already
    emitted N events, then the client receives all N past events before any new live
    events.
  - Given a live run, when a node transitions, then a node_transition SSE event is
    emitted within one event loop tick to all connected subscribers.
  - 'Given the run completes (done/failed/cancelled), then event: end is sent and
    the connection closes.'
  - The endpoint reuses Worker.subscribe(run_id) / Worker.unsubscribe(run_id) for
    event delivery; no parallel buffer is introduced.
  - Given a run_id that does not exist, then HTTP 404 is returned before any SSE headers
    are written.
  verifying_phase: test
  confidence: 0.85
- requirement_id: R9
  statement: HarnessExecutor publishes node/edge transition events into Worker._run_buffer
    (keyed by run_id = goal_task_id) via Worker._publish() so that the SSE stream
    and late-joiner replay work without a separate buffer.
  acceptance_criteria:
  - 'Given a node transitions to in_progress, then a dict event {type: node_transition,
    node_id, status: in_progress, timestamp} is published via worker._publish(run_id,
    event).'
  - Given a node transitions to done/failed/skipped, then a matching node_transition
    event with the final status is published.
  - 'Given an edge is chosen (decision branch selected), then an edge_chosen event
    {type: edge_chosen, from_node_id, to_node_id, label} is published.'
  - HarnessExecutor accepts the Worker instance via its WorkerProtocol; no circular
    import is introduced.
  verifying_phase: test
  confidence: 0.82
- requirement_id: R10
  statement: 'The SSE event schema for harness runs defines three event types — node_transition,
    edge_chosen, and run_status — each as a JSON payload on the data: line, with a
    consistent envelope: {type, run_id, timestamp}.'
  acceptance_criteria:
  - 'node_transition payload: {type, run_id, node_id, status, child_task_id (nullable),
    reason (nullable), timestamp}.'
  - 'edge_chosen payload: {type, run_id, from_node_id, to_node_id, label (nullable),
    timestamp}.'
  - 'run_status payload: {type, run_id, status, timestamp} emitted when overall run
    status changes to done/failed/cancelled.'
  - All timestamps are ISO-8601 UTC strings.
  - 'The SSE event: field is set to the event type string (e.g. event: node_transition).'
  verifying_phase: review
  confidence: 0.88
- requirement_id: R11
  statement: The run trigger endpoint (POST /run) and run-status endpoint (GET /harness-runs/{run_id})
    are covered by a new frontend panel that shows per-node status and a live SSE
    indicator; this constitutes the UI surface for this feature.
  acceptance_criteria:
  - A run panel component renders per-node status badges (pending/in_progress/done/failed/skipped)
    sourced from GET /harness-runs/{run_id}.
  - The panel subscribes to GET /harness-runs/{run_id}/stream and updates node badges
    in real time without a full page reload.
  - A Run button in the harness detail view triggers POST /run and displays the returned
    run_id.
  - A Cancel button is visible when run status is running and triggers POST /cancel.
  verifying_phase: manual
  confidence: 0.75
metrics:
  tool_calls: 9
  files_read: 5
  memory_hits: 4
---

## Summary

This feature exposes harness run lifecycle over HTTP by adding five new endpoint groups to `backend/app/api/harnesses.py`: a manual trigger (POST /run), a run-history list (GET /runs), a per-run snapshot (GET /harness-runs/{run_id}), a cancellation endpoint (POST /cancel), and a run-level SSE stream (GET /stream). The key architectural decisions resolve to: run_id equals the goal task ID (aligning with Worker and TaskStore), SSE reuses Worker.subscribe() and _run_buffer with HarnessExecutor publishing events via _publish(), history is backed by a per-harness append-only index file (O(1) reads, no N+1 trace reads), and cancellation atomically marks all in_progress/pending nodes failed. Per-node timings (started_at/ended_at) are added to NodeState to eliminate TraceStore read chains. Frontend surfaces a run panel with live SSE node-status updates.

## Scope

### In scope
- POST /api/spaces/{space_id}/harnesses/{name}/run — trigger and return run_id
- GET /api/spaces/{space_id}/harnesses/{name}/runs — history list from index file
- GET /api/harness-runs/{run_id} — full RunState snapshot with per-node timings
- POST /api/harness-runs/{run_id}/cancel — atomic cancel + node bulk-failure
- GET /api/harness-runs/{run_id}/stream — SSE with late-joiner replay
- NodeState.started_at / NodeState.ended_at fields (executor populates, JSON persists)
- Per-harness run index file (append-only, single-file, used by GET /runs and DELETE guard)
- DELETE /harnesses/{name} guard — 409 when active runs exist
- HarnessExecutor event publishing into Worker._run_buffer (node_transition, edge_chosen, run_status)
- SSE event schema (three typed events with consistent envelope)
- Frontend run panel (per-node status badges, live SSE indicator, Run/Cancel buttons)

### Out of scope
- Pagination of GET /runs (deferred; MVP returns all entries)
- Run-level authentication / per-run access control
- Purging or archiving of stale run index entries
- Optimistic locking on run trigger (noted in existing router docstring as deferred)
- Human Wait node reply via HTTP (existing TaskState.WAITING flow unchanged)
- Parallel SSE fan-out across spaces (space-level subscriber not extended)

### Deferred
- Pagination and filtering for GET /runs (future phase)
- Per-run audit log with full stdout/stderr capture (requires separate trace channel)
- Run scheduling / cron triggers (Arc 6 cron sub-goal)
- Optimistic locking on concurrent POST /run calls for the same harness

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | POST /run triggers harness execution and returns run_id |
| R2 | GET /runs returns ordered history list from index without N+1 reads |
| R3 | Per-harness index file maintained atomically for all run lifecycle transitions |
| R4 | GET /harness-runs/{run_id} returns full RunState snapshot with timings and chosen edges |
| R5 | NodeState gains started_at/ended_at persisted by executor at each node transition |
| R6 | POST /cancel atomically marks active/pending nodes failed and updates the index |
| R7 | DELETE harness returns 409 when active runs exist |
| R8 | GET /stream SSE replays backlog for late joiners and streams live transitions |
| R9 | HarnessExecutor publishes node/edge events into Worker._run_buffer via _publish() |
| R10 | SSE event schema defines three typed event envelopes (node_transition, edge_chosen, run_status) |
| R11 | Frontend run panel surfaces per-node status with live SSE updates and Run/Cancel buttons |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). Compact mirrors:

- R1 — POST /run returns HTTP 202 with {run_id, harness_id, triggered_at}; 404 for unknown harness; executor picks up and persists RunState
- R2 — GET /runs returns array ordered by triggered_at desc; empty array when no runs; reads only index file (O(1) I/O)
- R3 — Index entry appended on trigger (status=running); updated atomically on done/failed/cancelled; survives crash between trigger and first executor step
- R4 — HTTP 200 with per-node status map including started_at/ended_at; chosen_edges; waiting_node_id; single-file read; 404 for missing run
- R5 — started_at set on in_progress transition; ended_at set on done/failed/skipped; all node types covered; backward-compat load for old JSON
- R6 — HTTP 202 when run is active; stop_current() called; all in_progress+pending nodes set to failed/cancelled; HTTP 409 when run not active; 404 for missing run
- R7 — HTTP 409 listing active run_ids when any run is running; HTTP 204 when no active runs; check reads index not TaskStore
- R8 — Late joiner receives all past events before live ones; node transitions emitted within one event loop tick; event: end on run termination; 404 before SSE headers if run missing
- R9 — node_transition events published on in_progress and final status; edge_chosen events on branch selection; no circular import
- R10 — Three event types with consistent {type, run_id, timestamp} envelope; SSE event: field matches type; ISO-8601 timestamps
- R11 — Node status badges, live SSE updates, Run button, Cancel button visible when running

## Traceability

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | POST /run creates a goal task, enqueues it, and returns run_id with harness_id and triggered_at |
| R2 | test | GET /runs returns ordered RunSummary list from index file without per-run blob reads |
| R3 | test | Per-harness index file maintained atomically for all run lifecycle transitions |
| R4 | test | GET /harness-runs/{run_id} returns full RunState snapshot with timings and chosen edges |
| R5 | test | NodeState gains started_at/ended_at persisted by executor at each node transition |
| R6 | test | POST /cancel atomically marks active/pending nodes failed and updates the index |
| R7 | test | DELETE harness returns 409 when active runs exist |
| R8 | test | GET /stream SSE replays backlog for late joiners and streams live transitions |
| R9 | test | HarnessExecutor publishes node/edge events into Worker._run_buffer via _publish() |
| R10 | review | SSE event schema defines three typed event envelopes with consistent envelope |
| R11 | manual | Frontend run panel surfaces per-node status with live SSE updates and Run/Cancel buttons |

## Assumptions

- run_id = goal_task_id rationale: The scout confirmed RunState is already keyed by task_id at the filesystem level; the Worker SSE machinery (subscribe, _run_buffer, _publish) is keyed by task_id; reusing this identity avoids a separate serial counter and a new persistence layer with no consumer benefit at MVP scale.
- Run history model: Append-only index file per harness (not overwrite-on-run) was chosen over the scout suggestion of snapshot-on-demand because GET /runs requires multiple run summaries without re-reading all RunState blobs. The index file stays O(1) per harness regardless of run count.
- SSE bridge: HarnessExecutor publishes into Worker._run_buffer via _publish() (not a parallel buffer). This reuses the proven subscribe/unsubscribe infrastructure and keeps late-joiner replay free; the coupling is acceptable because executor already accepts a WorkerProtocol and the publish call fits the protocol naturally.
- Cancellation atomicity: All in_progress and pending nodes are immediately marked failed with reason=cancelled on the cancel call (bulk NodeState update). This is simpler than leaving them pending and avoids dangling RunState that could confuse a resume attempt.
- DELETE guard reads the index file, not TaskStore: This avoids cross-domain coupling and is consistent with GET /runs using the same source of truth.
- has_ui=true rationale: The request explicitly scopes a frontend run panel (per-node status, SSE indicator, Run/Cancel buttons). The scout excluded frontend from recon but the requirement for UI is unambiguous in the request text.
- API path: /api/harness-runs/{run_id} (no space_id prefix) for the run-centric endpoints (GET status, GET stream, POST cancel); space-scoped paths remain for harness-centric endpoints (POST /run, GET /runs). This matches the task SSE pattern at /api/tasks/{task_id}/stream.
- WorkerProtocol extension: _publish() must be added to WorkerProtocol in executor.py so tests can stub it; this is a one-line protocol addition with no circular import risk.

## Open questions

- None. All six scout decision points are resolved in Assumptions above.

## Next consumer brief

Design agent: read `traceability[]` and `## Assumptions` first — all six scout decision points are resolved there.

**Critical design inputs:**
1. **R3 (index file)**: Design must define the exact JSON schema for {harness_id}-index.json and the atomic append/update strategy (recommend: load-mutate-save_atomic pattern matching run_state.py existing helper).
2. **R9 (WorkerProtocol)**: _publish(task_id, event) must be added to WorkerProtocol in executor.py. Design should confirm no circular import path: executor uses the protocol, not the concrete class.
3. **R5 (NodeState schema change)**: started_at/ended_at are new optional fields on NodeState dataclass. Design must ensure from_dict() handles absent keys (default None) for backward compat with existing run JSON files.
4. **R1 (POST /run trigger mechanism)**: Design must decide whether POST /run creates a Task via TaskStore (reusing Worker normal enqueue path) or calls executor directly. Creating a Task is strongly preferred — it gives the run_id a first-class lifecycle in the Worker queue and keeps cancellation semantics consistent.
5. **R8/R9 (SSE router registration)**: The /harness-runs/{run_id}/stream endpoint has no space_id in its path; it needs access to the Worker instance. Design must define DI injection (app.state.worker_pool or similar) for the new harness-runs router.
6. **has_ui=true**: Design phase should include a UI sub-track for the run panel (R11). Per-node status badges can reuse existing task status pill components; SSE subscription pattern mirrors the existing task stream hook in frontend/src/hooks/useTasks.ts.
