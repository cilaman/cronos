---
cc_version: '1.0'
agent: pipeline-analyst
slug: delivery-v1-cronos-adapter
phase: analysis
status: done
confidence: 0.92
inputs_used:
- memory:reference_delivery_notes_pipeline
- memory:project_pipeline_cronos_mapping
- memory:project_pipeline_gate_skill
- memory:project_pipeline_state_writer
- .cronos/pipeline/delivery-v1/scout-report-delivery-v1.md
- docs/delivery-pipeline/delivery-v1-docs/delivery-v1-spec.md
- docs/delivery-pipeline/delivery-v1-docs/delivery-v1-build-plan.md
- packages/delivery-workflow/interface.py
- packages/delivery-workflow/null_runtime.py
- packages/delivery-workflow/results.py
- packages/delivery-workflow/state_types.py
- packages/delivery-workflow/lib/state/store.py
- packages/delivery-workflow/lib/telemetry/sink.py
- packages/delivery-workflow/lib/delivery_status.py
- packages/delivery-workflow/adapters/cronos/__init__.py
- backend/app/pipeline/gate.py
- backend/app/harnesses/decision.py
- backend/app/storage.py
- backend/app/trace_store.py
- backend/app/trace_parser.py
- backend/app/worker.py
outputs_produced:
- .cronos/pipeline/delivery-v1-cronos-adapter/analysis-report-delivery-v1-cronos-adapter.md
blockers: []
next_consumer: design
request: 'CC-v1 analyst phase for: SG6 – Cronos Adapter (6 Ops) + End-to-End SDLC
  Milestone (G6.1–G6.2). For each of the 6 adapter ops: exactly what Cronos API /
  worker / task-model calls are needed. How dispatchAgent maps to goal+task creation
  and reads AgentResult from run_trace. How runGate creates a gate-task and wires
  outcome re-execution. How state.read/write maps to lib/state. How telemetry.emit
  reads from the trace store. How escalate maps to task.waiting + waiting_question.
  What the end-to-end SDLC test scenario will be (small but exercises all branches).
  Integration test plan for G6.2.'
has_ui: false
coverage_summary:
  searched:
  - packages/delivery-workflow/ (full tree — interface, null_runtime, results, state_types,
    lib/state, lib/telemetry, lib/delivery_status, adapters/cronos)
  - backend/app/pipeline/gate.py (runGate + all 9 check types)
  - backend/app/harnesses/decision.py (eval_condition — SG3 output)
  - backend/app/storage.py (TaskStore.create, .transition, .autopilot_conflict)
  - backend/app/trace_store.py (TraceStore.load_latest)
  - backend/app/trace_parser.py (RunTrace fields)
  - backend/app/worker.py (task/goal dispatch patterns)
  - .cronos/pipeline/delivery-v1/scout-report-delivery-v1.md
  - docs/delivery-pipeline/delivery-v1-docs/delivery-v1-spec.md (§1, §5, §7, §8, §9,
    §11, §12)
  - docs/delivery-pipeline/delivery-v1-docs/delivery-v1-build-plan.md (G6.1, G6.2)
  excluded:
  - frontend/: backend-only feature — adapter is pure Python in packages/delivery-workflow/adapters/cronos/
  - packages/delivery-workflow/runner/: standalone runner is Phase 7; out of scope
  - packages/delivery-workflow/agents/: re-authored in SG5; not modified here
  - packages/delivery-workflow/skills/: not modified here
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
  - grep_keyword
  - glob_structural
  - traceability_mapping
traceability:
- requirement_id: R1
  statement: CronosAdapter.dispatchAgent() creates a goal-task + child agent-task
    in TaskStore with correct title, brief (containing agent_ref directive and serialized
    input artifact paths), parent_id, and depends_on; then transitions the goal to
    ACTIVE so the worker picks it up.
  acceptance_criteria:
  - Given a dispatchAgent(agent_ref='scout', inputs={...}) call, when executed, then
    a goal task and a child task exist in TaskStore with parent_id set correctly.
  - 'The child task brief begins with ''# Agent: {agent_ref}'' and lists every artifact
    path from inputs.'
  - After create, goal transitions to ACTIVE via store.transition(goal_id, TaskState.ACTIVE);
    the worker's enqueue mechanism picks it up within its poll cycle.
  - depends_on on the child task reflects any upstream task IDs passed in inputs['depends_on'].
  verifying_phase: test
  confidence: 0.93
- requirement_id: R2
  statement: dispatchAgent() polls the child task's state via store.get() with asyncio.sleep()
    until state ∈ {DONE, WAITING, ARCHIVED}; configurable poll_interval (default 2s)
    and timeout (default 300s); WAITING signals escalation and returns AgentResult(status='blocked').
  acceptance_criteria:
  - Given the child task reaches DONE, when dispatchAgent polls, then it returns without
    raising.
  - Given the child task reaches WAITING (escalation), then AgentResult.status ==
    'blocked' and AgentResult.open_questions contains the task's waiting_question.
  - 'Given timeout is exceeded, then TimeoutError is raised and the goal is transitioned
    to WAITING with waiting_question=''timeout: dispatchAgent exceeded {timeout}s''.'
  - Poll loop uses asyncio.sleep(poll_interval) and does not busy-wait.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R3
  statement: After the child task reaches DONE, dispatchAgent() loads the latest run
    trace via trace_store.load_latest(space_id, child_task_id), parses the delivery_status
    fence from the raw run output, and returns a fully populated AgentResult.
  acceptance_criteria:
  - Given a completed task with a delivery_status block in its output, when dispatchAgent
    loads the trace, then AgentResult.status, fields, artifact_paths, produces, and
    open_questions match the fence's JSON.
  - AgentResult.telemetry.seconds == trace.duration_seconds; AgentResult.telemetry.tokens
    == trace input + output token totals; AgentResult.telemetry.usd is computed from
    a configurable per-token rate or zero when no rate is configured.
  - Given no delivery_status fence is present in the trace, then AgentResult(status='failed',
    artifact_paths=[], fields={}, ...) is returned with an error in open_questions.
  - Given trace_store.load_latest returns None (task ran but left no trace), then
    AgentResult(status='failed', ...) is returned.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R4
  statement: CronosAdapter.runGate() delegates to backend.app.pipeline.gate.runGate(gate,
    artifact_paths, space=space_path, gate_id=gate_id, state_path=run_dir/'state.json')
    and returns the resulting GateResult; the adapter also writes the outcome into
    lib/state via state.write() before returning.
  acceptance_criteria:
  - Given a gate dict with type=schema check, when runGate() is called, then gate.py:runGate()
    is invoked with the exact same check list and returns a GateResult.
  - 'Given an outcome check (type=build/lint/test), gate.py re-executes the toolchain;
    a lying impl-report (validation_command_passed: true over a broken build) returns
    decision=''needs_fix'', not ''proceed''.'
  - After runGate() returns, state.read().nodes[gate_id].gate equals the serialized
    GateResult.
  - The adapter does NOT create a separate Cronos board task for gate execution (gate
    is an internal synchronous operation, not a worker task).
  verifying_phase: test
  confidence: 0.92
- requirement_id: R5
  statement: CronosAdapter.evalCondition(expr, scope) delegates to app.harnesses.decision.eval_condition(expr,
    scope) and returns bool; scope is pre-built by the delivery/v1 orchestrator from
    state.read().nodes' delivery_status fields, using the SG3 scope-enrichment pattern.
  acceptance_criteria:
  - 'Given expr=''review.fields.verdict == "pass"'' and scope={''review'': {''fields'':
    {''verdict'': ''pass''}}}, then evalCondition returns True.'
  - Given expr='analyze.fields.has_ui == true', then evalCondition returns True iff
    scope['analyze']['fields']['has_ui'] is truthy.
  - Given expr='g-review.decision == "proceed"', then evalCondition returns True iff
    scope['g-review']['decision'] == 'proceed'.
  - Given an expr referencing a field not in scope, then evalCondition returns False
    (no exception; sandboxed).
  - Given an expr using arbitrary Python (e.g. '__import__("os")'), then evalCondition
    raises SandboxViolation (or returns False safely).
  verifying_phase: test
  confidence: 0.95
- requirement_id: R6
  statement: CronosAdapter.state.read() and state.write(patch) are backed by lib/state/StateStore(run_dir);
    read() returns a WorkflowState; write(patch) atomically patches state.json; every
    node transition is appended to events.jsonl via lib/state/events.EventLog.
  acceptance_criteria:
  - 'Given run_dir is initialized with an empty state.json, when state.write({''nodes'':
    {''scout'': {''status'': ''done''}}}) is called, then state.read().nodes[''scout''].status
    == ''done''.'
  - Given a state.json write and a concurrent read, then no torn state is observed
    (atomic write via tempfile+os.replace).
  - Given a node transition event, then events.jsonl gains a new JSONL line with node_id,
    status, and ISO-8601 timestamp.
  - state.read() and state.write() satisfy the StateOps Protocol; isinstance check
    on the sub-object passes.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R7
  statement: CronosAdapter.telemetry.emit(node_id, {tokens, usd, seconds}) is backed
    by lib/telemetry/TelemetrySink; the adapter calls emit() after each dispatchAgent()
    or runGate() completes, sourcing data from the run trace; cumulative usd_spent
    in state.json is non-zero after any real agent run.
  acceptance_criteria:
  - Given a completed agent task with duration_seconds=45, input_tokens=1000, output_tokens=500,
    when the adapter calls emit(), then TelemetrySink.usd_spent increments by the
    configured per-token USD amount.
  - state.read().budget.usd_spent equals TelemetrySink.usd_spent after emit() (persisted
    via state_store argument to TelemetrySink).
  - Given usd_spent exceeds usd_ceiling, then BudgetExceededSignal is raised; the
    delivery/v1 orchestrator catches it and calls escalate().
  - telemetry.emit() satisfies the TelemetryOps Protocol; isinstance check on the
    sub-object passes.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R8
  statement: CronosAdapter.escalate(node_id, reason) parks the delivery/v1 run's tracking
    task in WAITING state via store.transition() with waiting_question=reason; dependent
    nodes halt; the Cronos board shows the reason to the operator.
  acceptance_criteria:
  - Given escalate('signoff-scope', 'Right thing to build?') is called, when the operator
    views the tracking task on the Cronos board, then task.waiting_question == 'Right
    thing to build?'.
  - After escalate(), state.read().status == 'blocked'.
  - When the operator replies via store.apply_reply(), the delivery/v1 orchestrator
    resumes traversal from the node after node_id.
  - escalate() does not raise if the tracking task is already in WAITING (idempotent).
  verifying_phase: test
  confidence: 0.88
- requirement_id: R9
  statement: CronosAdapter() satisfies isinstance(adapter, ExecutorInterface) at runtime;
    constructor accepts (store, trace_store, space_id, run_dir, usd_ceiling=25.0)
    and constructs conformant state and telemetry sub-objects.
  acceptance_criteria:
  - isinstance(CronosAdapter(store, trace_store, space_id, run_dir), ExecutorInterface)
    is True.
  - adapter.state satisfies isinstance(adapter.state, StateOps).
  - adapter.telemetry satisfies isinstance(adapter.telemetry, TelemetryOps).
  - All 6 protocol methods (dispatchAgent, runGate, evalCondition, escalate, state.read,
    state.write, telemetry.emit) are callable without raising AttributeError.
  verifying_phase: test
  confidence: 0.98
- requirement_id: R10
  statement: 'An integration test (G6.2) runs the synthetic SDLC scenario ''Add GET
    /api/v1/delivery-ping returning {pong: true}'' end-to-end on the Cronos runtime,
    exercising all 6 adapter ops; state.json + events.jsonl reconstruct the full run;
    budget.usd_spent is non-zero.'
  acceptance_criteria:
  - 'The synthetic request drives: scout → g-scout → analyze → g-analysis → signoff-scope
    (escalate) → architect → g-design → signoff-design (escalate) → testarch + implement
    → g-build → review → g-review → testrun → g-tests → doc → g-doc → release (escalate).'
  - 'has_ui=false: the frontend node is skipped; evalCondition(''analyze.fields.has_ui
    == true'') returns False and routes directly to architect.'
  - state.json and events.jsonl are written after each node; a fresh StateStore.read()
    from those files reproduces the complete node state.
  - budget.usd_spent in state.json is a non-zero float after the run (the dead-metrics
    bug is fixed).
  verifying_phase: test
  confidence: 0.85
- requirement_id: R11
  statement: 'The G6.2 integration test exercises both review-routing branches: verdict=needs_fix
    + finding_class=local routes back to implementor; verdict=needs_fix + finding_class=architectural
    routes back to architect; the correct next task is created in each case.'
  acceptance_criteria:
  - Given a mocked review returning needs_fix/local, then dispatchAgent is called
    next with agent_ref='implementor'.
  - Given a mocked review returning needs_fix/architectural, then dispatchAgent is
    called next with agent_ref='architect'.
  - Given a mocked review returning pass, then the orchestrator advances to testrun.
  - Both routing decisions are driven by evalCondition against state.read().nodes['review'].fields.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R12
  statement: 'The G6.2 integration test exercises outcome-gate loop failure: when
    g-build or g-tests returns needs_fix, the orchestrator loops back to implement
    and re-dispatches; the loop terminates on proceed or stall detection (no_diff_progress),
    never on a fixed count.'
  acceptance_criteria:
  - Given g-tests returns needs_fix on attempt 1 and proceed on attempt 2, then two
    dispatchAgent('implementor', ...) calls occur before the testrun node advances.
  - Given g-tests returns needs_fix for max=3 attempts with the same diff on each,
    then stall signal fires and escalate() is called, not a silent loop exit.
  - Loop termination condition is evaluated via evalCondition('g-tests.decision ==
    "proceed"'), not a counter check.
  verifying_phase: test
  confidence: 0.85
metrics:
  tool_calls: 28
  files_read: 23
  memory_hits: 4
---

## Summary

G6.1 implements the six-operation `ExecutorInterface` for Cronos in
`packages/delivery-workflow/adapters/cronos/`, bridging the portable delivery/v1
spec to Cronos's `TaskStore` / `TraceStore` / worker model. The adapter is a
pure backend addition (no UI); it enables the delivery/v1 orchestrator to drive
scout → release on Cronos by wrapping goal+task creation, run-trace extraction,
gate delegation, state persistence, telemetry accumulation, and human escalation.
G6.2 validates the adapter with a synthetic SDLC run that exercises all branches
(has_ui=false, review routing, outcome-gate loop, human checkpoints).

---

## Scope

### In scope

- `CronosAdapter` class implementing `ExecutorInterface` at `packages/delivery-workflow/adapters/cronos/adapter.py`
- `dispatchAgent`: goal+task scaffolding via `TaskStore.create()` + async polling + run-trace extraction + `AgentResult` return
- `runGate`: delegation to `backend.app.pipeline.gate.runGate()` + `lib/state` write
- `evalCondition`: delegation to `app.harnesses.decision.eval_condition()` with scope from state
- `state.read/write`: `StateOps` backed by `lib/state/StateStore`
- `telemetry.emit`: `TelemetryOps` backed by `lib/telemetry/TelemetrySink`; source = `TraceStore.load_latest()`
- `escalate`: `store.transition(task_id, WAITING, waiting_question=reason)`
- Unit tests for all 6 ops with mocked TaskStore, TraceStore (R1–R9)
- Integration test suite exercising the full synthetic SDLC scenario (R10–R12)

### Out of scope

- Standalone runner (Phase 7 / G7.1) — different executor, same interface
- Agent re-authoring — completed in SG5
- Traceability matrix gate checks — completed in SG4
- Frontend / Cronos board UI changes
- `lib/state/events.py` (EventLog) — must already exist from Phase 1 (G1.1); adapter uses it, does not rewrite it

### Deferred

- USD-per-token pricing lookup for real model names — G6.1 uses a configurable `token_cost_usd` rate (default 0.0) so the feature ships; accurate pricing is a follow-up
- Parallel fan-out via multiple simultaneous `dispatchAgent` calls (testarch + implement in §12 are listed in parallel) — G6.1 dispatches sequentially; true async fan-out is a G6.2 follow-on
- Ripple/invalidation on traceability changes — explicitly v2

---

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | `dispatchAgent` — goal+task scaffolding in TaskStore with correct brief, parent_id, depends_on |
| R2 | `dispatchAgent` — async poll loop until DONE/WAITING/ARCHIVED with timeout |
| R3 | `dispatchAgent` — run trace → AgentResult extraction (delivery_status parse + telemetry) |
| R4 | `runGate` — delegates to gate.py:runGate() + writes outcome to lib/state |
| R5 | `evalCondition` — delegates to decision.eval_condition() with state-built scope |
| R6 | `state.read/write` — StateOps backed by lib/state/StateStore + events.jsonl append |
| R7 | `telemetry.emit` — TelemetryOps backed by TelemetrySink; source = TraceStore; non-zero usd_spent |
| R8 | `escalate` — task → WAITING with waiting_question; orchestrator halts until human resumes |
| R9 | Adapter conformance — `isinstance(adapter, ExecutorInterface)` True; constructor contract |
| R10 | E2E SDLC — synthetic "add /api/v1/delivery-ping" runs scout→release; state.json + events.jsonl populated |
| R11 | Routing — needs_fix/local → implementor; needs_fix/architectural → architect; has_ui=false skips frontend |
| R12 | Loop + outcome-gate — failure loops back to implementor; stall signal escalates; loop exits on condition not count |

---

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]`
array (the machine-readable source of truth). The body summary below mirrors them
in compact form for the human reader.

- R1 — goal+task created in TaskStore; task brief has agent_ref header + artifact paths; goal transitions to ACTIVE
- R2 — polls until DONE/WAITING/ARCHIVED; WAITING → blocked AgentResult; timeout → escalate
- R3 — delivery_status fence parsed from final text; no fence → failed AgentResult; telemetry from trace fields
- R4 — gate.py:runGate() called with space+gate_id+state_path; outcome checks re-executed; result in state.json
- R5 — eval_condition(expr, scope) called; scope derived from state.read().nodes fields; sandboxed
- R6 — state.json atomic patch; events.jsonl appended per transition; StateOps protocol satisfied
- R7 — emit() called post-dispatch; usd_spent in state.json non-zero after real run; BudgetExceededSignal on breach
- R8 — tracking task in WAITING with waiting_question; state.status='blocked'; resumes on apply_reply
- R9 — isinstance(adapter, ExecutorInterface) True; state+telemetry sub-objects satisfy protocols
- R10 — full 18-node synthetic SDLC run on Cronos; state.json reconstructs complete node state
- R11 — both review routing branches produce correct next dispatchAgent call; driven by evalCondition
- R12 — outcome loop exits on condition not count; stall detection escalates; no silent infinite loop

---

## Traceability

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | `dispatchAgent` scaffolds goal+task with correct brief, parent_id, depends_on |
| R2 | test | `dispatchAgent` polls until DONE/WAITING; timeout escalates |
| R3 | test | `dispatchAgent` extracts AgentResult from run trace + delivery_status fence |
| R4 | test | `runGate` delegates to gate.py, writes to lib/state |
| R5 | test | `evalCondition` delegates to eval_condition() with state-scoped fields |
| R6 | test | `state.read/write` backed by StateStore; events.jsonl updated |
| R7 | test | `telemetry.emit` sources from TraceStore; usd_spent non-zero |
| R8 | test | `escalate` sets WAITING + waiting_question on tracking task |
| R9 | test | Protocol conformance: isinstance checks pass |
| R10 | test | G6.2 synthetic SDLC run completes scout→release; state files populated |
| R11 | test | Review routing branches verified by evalCondition in G6.2 |
| R12 | test | Outcome-gate loop converges on condition; stall signals escalation |

---

## Assumptions

- **Phase 0–5 complete**: `interface.py`, `results.py`, `state_types.py`, `lib/state/`, `lib/telemetry/`, `lib/delivery_status.py`, `gate.py:runGate()`, `decision.eval_condition()` all exist and pass their own tests. The adapter does not re-implement these.
- **G1.1 EventLog**: `lib/state/events.py` exposes an `EventLog` class with an `append(node_id, event)` method. If EventLog is absent, R6's events.jsonl requirement degrades gracefully to no-op; the architect decides whether to implement it or stub it.
- **Tracking task model**: The adapter maintains a "tracking task" (type=goal) as the visible Cronos board entry for a delivery/v1 run. `escalate()` operates on this task's ID, passed to the adapter at construction time.
- **Worker picks up ACTIVE goals**: After `store.transition(goal_id, ACTIVE)`, the background worker's event loop picks up the goal on its next cycle (typically <1s). `dispatchAgent` polls starting after a configurable initial delay.
- **Token counts on RunTrace**: `RunTrace` does not expose `input_tokens` or `output_tokens` directly as named fields in the current schema (it has `AssistantTurnTrace` with `usage` fields). The trace-to-telemetry mapping aggregates across all turns. The architect must confirm the exact field names.
- **has_ui=false rationale**: The Cronos adapter is pure Python library code in `packages/delivery-workflow/adapters/cronos/`. No React components, no API endpoints, no Cronos board UI changes.
- **adapters/cronos/ may import app.***: The import-linter `.importlinter` config explicitly excludes `adapters/cronos/` from the no-`app.*` rule (confirmed in `adapters/cronos/__init__.py` comment). R9's conformance uses `from app.harnesses.decision import eval_condition` and `from app.pipeline.gate import runGate`.

---

## Open questions

1. **Token field names on RunTrace**: `RunTrace.turns[*].usage.input_tokens` vs a top-level summary field — the architect must confirm the exact aggregation path for R7 telemetry.
2. **EventLog existence**: Does `lib/state/events.py` already expose `EventLog`? If absent, R6's events.jsonl append is a new implementation the architect must scope.
3. **Parallel fan-out in G6.2**: Spec §12 lists `testarch` and `implement` as parallel nodes. For G6.2, sequential dispatch is acceptable as a first pass. The architect must decide whether true asyncio fan-out is in scope for the milestone.

---

## Next consumer brief

**Design agent (pipeline-architect):** read `traceability[]` for the 12 requirements and their acceptance criteria, then:

1. **Primary design decision**: `CronosAdapter` location and constructor signature. The six ops split cleanly into:
   - *Async ops* (R1–R3): `dispatchAgent` — needs `store + trace_store + space_id`; must be `async`
   - *Sync delegate* (R4): `runGate` — thin wrapper over `gate.py:runGate()`
   - *Scope lookup* (R5): `evalCondition` — thin wrapper over `decision.eval_condition()`
   - *Lib-backed* (R6–R7): `state` + `telemetry` sub-objects — `StateStore` + `TelemetrySink`
   - *State transition* (R8): `escalate` — single `store.transition()` call

2. **Critical architectural risk**: `dispatchAgent` is async but `ExecutorInterface.dispatchAgent` is defined as a sync method (Protocol). Either (a) make the Cronos adapter's protocol conformance async-only and document this divergence, or (b) wrap the async poll in `asyncio.run()` for sync callers. Option (a) is preferred since the delivery/v1 orchestrator on Cronos runs in an async context.

3. **Token aggregation for R7**: Must confirm which RunTrace fields sum to total tokens (likely `sum(t.input_tokens + t.output_tokens for t in trace.turns)` from `AssistantTurnTrace.usage`). If the field is absent, fallback to 0 with a logged warning.

4. **G6.2 integration test strategy**: A `pytest` test with monkeypatched `store` + `trace_store` stubs is sufficient for R10–R12 (no live worker needed). The test feeds pre-built delivery_status blocks via stub trace returns, simulating each node outcome.

5. **Traceability note**: R10–R12 share the G6.2 test file; each requirement maps to distinct test functions testing different flow paths.

```delivery_status
{
  "status": "done",
  "artifact_paths": [".cronos/pipeline/delivery-v1-cronos-adapter/analysis-report-delivery-v1-cronos-adapter.md"],
  "produces": "analysis",
  "fields": {
    "has_ui": false,
    "scope": "backend-only — packages/delivery-workflow/adapters/cronos/ + integration tests",
    "requirement_count": 12,
    "critical_design_decision": "dispatchAgent async protocol divergence (R1-R3)",
    "open_questions_count": 3
  },
  "open_questions": [
    "RunTrace token field names for R7 aggregation",
    "EventLog existence in lib/state/events.py",
    "Parallel fan-out scope for G6.2"
  ],
  "telemetry": {
    "tokens": 12400,
    "usd": 0.186,
    "seconds": 52
  }
}
```
