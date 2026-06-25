---
cc_version: '1.0'
agent: pipeline-architect
slug: delivery-v1-cronos-adapter
phase: design
status: done
confidence: 0.86
inputs_used:
- .cronos/pipeline/delivery-v1-cronos-adapter/analysis-report-delivery-v1-cronos-adapter.md
- docs/delivery-pipeline/delivery-v1-docs/delivery-v1-spec.md
- packages/delivery-workflow/interface.py
- packages/delivery-workflow/results.py
- packages/delivery-workflow/null_runtime.py
- packages/delivery-workflow/state_types.py
- packages/delivery-workflow/lib/state/store.py
- packages/delivery-workflow/lib/state/events.py
- packages/delivery-workflow/lib/telemetry/sink.py
- packages/delivery-workflow/lib/delivery_status.py
- packages/delivery-workflow/adapters/cronos/__init__.py
- packages/delivery-workflow/tests/test_import_boundary.py
- backend/app/pipeline/gate.py
- backend/app/harnesses/decision.py
- backend/app/storage.py
- backend/app/trace_store.py
- backend/app/trace_parser.py
outputs_produced:
- .cronos/pipeline/delivery-v1-cronos-adapter/design-report-delivery-v1-cronos-adapter.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - packages/delivery-workflow/ (interface, results, null_runtime, state_types, lib/state, lib/telemetry, lib/delivery_status, adapters/cronos, import boundary)
  - backend/app/pipeline/gate.py
  - backend/app/harnesses/decision.py
  - backend/app/storage.py (create_task, transition, post_run_update)
  - backend/app/trace_store.py (load_latest/load_run)
  - backend/app/trace_parser.py (RunTrace + AssistantTurnTrace token fields)
  excluded:
  - 'frontend/: has_ui=false — adapter is pure Python in packages/delivery-workflow/adapters/cronos/'
  - 'packages/delivery-workflow/runner/: standalone CC-plugin runner is Phase 7 (deferred, spec §11)'
  - 'packages/delivery-workflow/agents+skills: authored in SG5, not modified here'
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
  - grep_keyword
iterations:
- id: I1
  type: backend
  scope_files:
  - packages/delivery-workflow/adapters/cronos/adapter.py
  - backend/tests/test_cronos_adapter_state_telemetry.py
  validation_command: cd backend && PYTHONPATH=../packages/delivery-workflow python -m pytest tests/test_cronos_adapter_state_telemetry.py --override-ini="addopts=" -v
  max_diff_lines: 320
  depends_on: []
- id: I2
  type: backend
  scope_files:
  - packages/delivery-workflow/adapters/cronos/adapter.py
  - backend/tests/test_cronos_adapter_dispatch.py
  validation_command: cd backend && PYTHONPATH=../packages/delivery-workflow python -m pytest tests/test_cronos_adapter_dispatch.py --override-ini="addopts=" -v
  max_diff_lines: 400
  depends_on:
  - I1
- id: I3
  type: backend
  scope_files:
  - packages/delivery-workflow/adapters/cronos/adapter.py
  - backend/tests/test_cronos_adapter_gate.py
  validation_command: cd backend && PYTHONPATH=../packages/delivery-workflow python -m pytest tests/test_cronos_adapter_gate.py --override-ini="addopts=" -v
  max_diff_lines: 240
  depends_on:
  - I1
- id: I4
  type: backend
  scope_files:
  - packages/delivery-workflow/adapters/cronos/adapter.py
  - backend/tests/test_cronos_adapter_condition.py
  validation_command: cd backend && PYTHONPATH=../packages/delivery-workflow python -m pytest tests/test_cronos_adapter_condition.py --override-ini="addopts=" -v
  max_diff_lines: 200
  depends_on:
  - I1
- id: I5
  type: backend
  scope_files:
  - packages/delivery-workflow/adapters/cronos/adapter.py
  - backend/tests/test_cronos_adapter_escalate.py
  - backend/tests/test_cronos_adapter_integration.py
  validation_command: cd backend && PYTHONPATH=../packages/delivery-workflow python -m pytest tests/test_cronos_adapter_escalate.py tests/test_cronos_adapter_integration.py --override-ini="addopts=" -v
  max_diff_lines: 320
  depends_on:
  - I1
  - I2
  - I3
  - I4
- id: I6
  type: backend
  scope_files:
  - packages/delivery-workflow/adapters/cronos/fixtures/sdlc_ping.yaml
  - backend/tests/test_cronos_adapter_e2e_sdlc.py
  validation_command: cd backend && PYTHONPATH=../packages/delivery-workflow python -m pytest tests/test_cronos_adapter_e2e_sdlc.py --override-ini="addopts=" -v
  max_diff_lines: 520
  depends_on:
  - I5
risks:
- description: 'Async/sync Protocol divergence (R1–R3 vs R9): `ExecutorInterface.dispatchAgent`
    is a SYNC method in the Protocol, but the Cronos op must poll task state with
    `asyncio.sleep` (R2), so it has to be `async def`. A naive reading fears this breaks
    `isinstance(adapter, ExecutorInterface)` (R9 ac-1).'
  severity: high
  mitigation: 'DD-02: `dispatchAgent` is `async def`; the other five ops stay sync.
    `ExecutorInterface` is `@runtime_checkable`, so `isinstance` only verifies METHOD
    PRESENCE (`hasattr`), never signature or coroutine-ness — an async `dispatchAgent`
    still satisfies R9. The divergence is documented in the adapter docstring; the
    delivery/v1 Cronos orchestrator already runs in an async context. I1 asserts the
    isinstance checks pass with the async method present.'
- description: 'delivery_status truncation (R3): `dispatchAgent` reads the agent return
    via `trace_store.load_latest`, but `RunTrace.final_text_snippet` is truncated to
    500 chars (`trace_parser._truncate`). A terminal `delivery_status` JSON fence longer
    than 500 chars is clipped and `parse_delivery_status` returns None — yielding a
    spurious `status="failed"` AgentResult and breaking has_ui/verdict routing.'
  severity: high
  mitigation: 'DD-05: parse the fence with `lib/delivery_status.parse_delivery_status`
    from `final_text_snippet`; the §8 terminal return is intentionally compact
    (status/produces/artifact_paths/short fields) and fits. Defence in depth: when the
    snippet yields no fence, fall back to scanning the trailing ```delivery_status block
    of the newest artifact under `.cronos/pipeline/<slug>/` (CC-v1 reports end with that
    fence — see the analysis report). I3 of any future trace work may widen the trace to
    carry full final text; that is a noted follow-up, NOT in SG6 scope. I2 adds a
    >500-char-block regression test proving the fallback path.'
- description: 'Token aggregation (R7/R3): `RunTrace` exposes NO top-level token total;
    tokens live per-turn on `AssistantTurnTrace.{input_tokens,output_tokens}`. An adapter
    that reads a non-existent `trace.tokens` field emits zero telemetry, re-introducing
    the dead-metrics bug R10 ac-4 explicitly guards against.'
  severity: medium
  mitigation: 'DD-04: telemetry tokens = `sum(t.input_tokens + t.output_tokens for t in
    trace.turns)`; `seconds = trace.duration_seconds`; `usd = tokens * token_cost_usd`
    (constructor rate, default 0.0 so the feature ships without a pricing table). I1
    tests a stub trace with known per-turn usage and asserts non-zero accumulation;
    the e2e (I6) asserts `state.json.budget.usd_spent` is a non-zero float (needs a
    non-zero rate in the test).'
- description: 'EventLog signature mismatch (R6): the analyst assumed
    `EventLog.append(node_id, event)`, but the shipped `lib/state/events.py` exposes
    `append(event: dict)` (single dict; auto-injects `ts`). Calling the assumed
    two-arg form raises `TypeError` and no event line is written.'
  severity: medium
  mitigation: 'DD-08: the adapter calls `EventLog(run_dir).append({"node_id": …,
    "status": …, "type": "node_transition"})` — node_id goes INSIDE the dict; `ts` is
    auto-injected. EventLog already exists (open-question 2 resolved: present), so R6
    needs no new EventLog code. I1 asserts events.jsonl gains one ISO-8601-stamped line
    per `state.write` transition.'
- description: 'E2E flakiness & parallel fan-out (R10–R12 milestone): the §12 graph
    chains ~18 nodes with a review convergence loop, two human checkpoints, and a
    has_ui branch; spec §12 lists `testarch` + `implement` as parallel. Driving live
    agents — or true asyncio fan-out — would make the milestone gate slow and
    non-deterministic.'
  severity: high
  mitigation: 'DD-11: I6 drives the scenario with monkeypatched `store` + `trace_store`
    stubs returning scripted `delivery_status` per node (analyst next-brief item 4) — no
    live worker. Dispatch is SEQUENTIAL (parallel fan-out explicitly deferred per analyst
    "Deferred"); `testarch` then `implement` run in order. Assertions pin the realised
    node path, the has_ui=false skip, both review routes, one outcome-gate loop
    (convergence via `evalCondition`, not a counter), and state.json+events.jsonl
    reconstruction.'
- description: 'Import-boundary regression: the portable core (`lib`, `runner`) must
    never import `app.*`. The adapter deliberately imports `app.pipeline.gate` and
    `app.harnesses.decision`; a helper mistakenly placed in `lib/` would break the
    `no-app-imports` contract and `test_import_boundary.py`.'
  severity: medium
  mitigation: 'DD-01: ALL `app.*`-touching code stays in
    `packages/delivery-workflow/adapters/cronos/adapter.py` — the subtree
    `.importlinter`/`test_import_boundary.py` explicitly exempts (ALLOWED_PATHS). `app.*`
    is imported lazily inside methods so importing the bundle core never pulls in the
    backend. No `lib/` change is made; the existing boundary test is the guard.'
metrics:
  tool_calls: 27
  files_read: 24
  memory_hits: 1
  iterations_planned: 6
---

## Summary

SG6 builds the **Cronos adapter** (`CronosAdapter`) — the first concrete implementation
of the portable `ExecutorInterface` (spec §1/§11) — and validates it end-to-end with the
§12 synthetic SDLC run (the **G6.2 milestone**). Per the analyst's twelve requirements
(R1–R12), the adapter is a single backend module
`packages/delivery-workflow/adapters/cronos/adapter.py` that **bridges, not re-implements**:
it wraps Cronos's `TaskStore` / `TraceStore` / worker model and delegates gates, conditions,
state, and telemetry to machinery the earlier subgoals already shipped.

The six ops split by mechanism exactly as the analyst's next-consumer brief framed them:

- **async `dispatchAgent`** (R1–R3): scaffold goal + child agent-task in `TaskStore`,
  transition the goal `ACTIVE`, poll until `DONE/WAITING/ARCHIVED`, then load the run trace
  and parse `delivery_status` into a `results.AgentResult` — **DD-02/DD-03/DD-04/DD-05**.
- **`runGate`** (R4): delegate to `app.pipeline.gate.runGate` (contract checks + outcome
  re-execution, SG2) and write the result into `lib/state` — **DD-06**.
- **`evalCondition`** (R5): delegate to `app.harnesses.decision.eval_condition` (SG3,
  sandboxed) against an orchestrator-built scope — **DD-07**.
- **`state.read/write`** (R6): `StateOps` backed by `lib/state.StateStore` + `EventLog` — **DD-08**.
- **`telemetry.emit`** (R7): `TelemetryOps` backed by `lib/telemetry.TelemetrySink`, sourced
  from the run trace — **DD-04/DD-09**.
- **`escalate`** (R8): transition the run's tracking task to `WAITING` + `waiting_question` — **DD-10**.

The decomposition is six backend iterations: a foundation iteration (**I1**: the
`CronosAdapter` skeleton + the two lib-backed sub-objects `state`/`telemetry` + Protocol
conformance, R6/R7/R9) that the three independent op iterations fan out from (**I2**
dispatchAgent, **I3** runGate, **I4** evalCondition), a join iteration that adds `escalate`
and the all-six-ops integration test (**I5**, R8/R9), and the milestone e2e scenario
(**I6**, R10–R12). This design **resolves all three analyst open questions** (token field
names, EventLog existence/signature, parallel-fan-out scope) and the **critical async/sync
Protocol divergence** — see Open questions and the risk register.

## Components

### Backend — `packages/delivery-workflow/adapters/cronos/adapter.py`

- **`CronosAdapter`** (implements `ExecutorInterface`, R9): constructor
  `(store, trace_store, space_id, run_dir, *, tracking_task_id=None, usd_ceiling=25.0,
  token_cost_usd=0.0, poll_interval=2.0, timeout=300.0)`. Builds `.state` (`CronosStateOps`)
  and `.telemetry` (`CronosTelemetryOps`) sub-objects in `__init__`. All `app.*` imports are
  lazy/in-method (**DD-01**).
- **`CronosStateOps`** (`StateOps`, R6): `read() -> WorkflowState` and `write(patch) -> None`
  over `lib/state.StateStore(run_dir)` (atomic tempfile+replace, already implemented); each
  `write` that changes a node status appends a line to `events.jsonl` via
  `lib/state.events.EventLog(run_dir).append({"node_id":…, "status":…, "type":"node_transition"})`
  (single-dict signature; `ts` auto-injected) — **DD-08**.
- **`CronosTelemetryOps`** (`TelemetryOps`, R7): wraps
  `lib/telemetry.TelemetrySink(usd_ceiling=…, state_store=…)`; `emit(node_id, data)` persists
  per-node telemetry + cumulative `usd_spent` to `state.json` and raises `BudgetExceededSignal`
  on ceiling breach (orchestrator catches → `escalate`). Helper
  `_telemetry_from_trace(trace) -> {tokens, usd, seconds}` sums per-turn tokens — **DD-04/DD-09**.
- **`async dispatchAgent(agent_ref, inputs) -> results.AgentResult`** (R1–R3): (1) `store.create_task`
  a child agent-task — brief begins `# Agent: {agent_ref}` and lists every `inputs` artifact
  path; `parent_id` = the run goal; `depends_on` = `inputs.get("depends_on", [])`; (2)
  transition the goal `ACTIVE`; (3) poll `store.get(child_id)` every `poll_interval` (no busy-wait)
  until `DONE/WAITING/ARCHIVED` or `timeout` (→ escalate + `TimeoutError`); WAITING → `AgentResult(status="blocked", open_questions=[waiting_question])`; (4) on DONE,
  `trace_store.load_latest(space_id, child_id)`, parse `delivery_status`, build `AgentResult`;
  missing fence / `None` trace → `AgentResult(status="failed", …)` with an error note — **DD-02/03/04/05**.
- **`runGate(gate, artifact_paths) -> results.GateResult`** (R4): call
  `app.pipeline.gate.runGate(gate, artifact_paths, space=space_path, gate_id=gate["id"],
  state_path=run_dir/"state.json")`; map decision/errors/evidence into `results.GateResult`
  and `state.write` the gate node. No Cronos board task is created (gate is synchronous) — **DD-06**.
- **`evalCondition(expr, scope) -> bool`** (R5): delegate to
  `app.harnesses.decision.eval_condition(expr, flatten(scope))`; the orchestrator pre-builds
  `scope` from `state.read().nodes` delivery_status fields (SG3 dotted-key convention); unknown
  field → False, arbitrary code → False/raise (sandboxed) — **DD-07**.
- **`escalate(node_id, reason) -> None`** (R8): resolve the run's tracking task
  (`tracking_task_id`); `store.post_run_update`/`transition` it to `TaskState.WAITING` with
  `waiting_question=reason`; `state.write({"status": "blocked"})`; idempotent if already WAITING — **DD-10**.

### Fixtures / tests

- **`adapters/cronos/fixtures/sdlc_ping.yaml`**: the synthetic "Add `GET /api/v1/delivery-ping`
  returning `{pong: true}`" feature + scripted per-node `delivery_status` returns for the §12
  graph (`has_ui=false`, one review `needs_fix·local` loop, one `g-tests` outcome loop) — **DD-11**.
- **`backend/tests/test_cronos_adapter_*.py`**: per-op tests (I1–I5) + the milestone e2e (I6),
  run from the backend env with `PYTHONPATH=../packages/delivery-workflow` so both `app.*` and
  the bundle (`adapters`, `lib`, `results`) resolve.

## Implementation plan

| ID  | Type    | Reqs        | Depends on       | Scope files (abridged)                                              | Validation |
|-----|---------|-------------|------------------|---------------------------------------------------------------------|------------|
| I1  | backend | R6,R7,R9    | -                | adapters/cronos/adapter.py, test_cronos_adapter_state_telemetry.py   | `cd backend && PYTHONPATH=../packages/delivery-workflow pytest tests/test_cronos_adapter_state_telemetry.py --override-ini="addopts=" -v` |
| I2  | backend | R1,R2,R3    | I1               | adapters/cronos/adapter.py, test_cronos_adapter_dispatch.py          | `… pytest tests/test_cronos_adapter_dispatch.py …` |
| I3  | backend | R4          | I1               | adapters/cronos/adapter.py, test_cronos_adapter_gate.py              | `… pytest tests/test_cronos_adapter_gate.py …` |
| I4  | backend | R5          | I1               | adapters/cronos/adapter.py, test_cronos_adapter_condition.py         | `… pytest tests/test_cronos_adapter_condition.py …` |
| I5  | backend | R8,R9       | I1,I2,I3,I4      | adapters/cronos/adapter.py, test_cronos_adapter_{escalate,integration}.py | `… pytest tests/test_cronos_adapter_escalate.py tests/test_cronos_adapter_integration.py …` |
| I6  | backend | R10,R11,R12 | I5               | adapters/cronos/fixtures/sdlc_ping.yaml, test_cronos_adapter_e2e_sdlc.py | `… pytest tests/test_cronos_adapter_e2e_sdlc.py …` |

**Critical path:** I1 → {I2,I3,I4} → I5 → I6. I2/I3/I4 are independent and may land in any
order once I1 fixes the constructor, the `.state`/`.telemetry` sub-objects, and conformance.
I5 is the join (escalate + the integration test exercising all six ops on one `CronosAdapter`);
I6 is the milestone, gated on I5. All six iterations edit the single `adapter.py` (the analyst's
chosen location); the per-iteration `scope_files` overlap on `adapter.py` is intentional and the
DAG serialises the conflicting edits (I2–I4 each add a distinct method; I5 wires them).

### Design decisions (DD — traceability targets for g-design)

- **DD-01** `CronosAdapter` lives in one module `adapters/cronos/adapter.py` (analyst primary
  decision); the import-boundary-exempt seam (spec §11); `app.*` imported lazily in-method.
- **DD-02** `dispatchAgent` is `async def` (poll loop, R2); other ops sync. `@runtime_checkable`
  `ExecutorInterface` checks method presence only, so `isinstance` (R9) still passes — divergence
  documented, orchestrator is async.
- **DD-03** dispatch flow: `create_task` child (brief `# Agent: {ref}` + artifact paths,
  `parent_id`, `depends_on`) → goal `ACTIVE` → poll `store.get` until `DONE/WAITING/ARCHIVED`
  (timeout → escalate) → `trace_store.load_latest` → `delivery_status` → `AgentResult`.
- **DD-04** telemetry from trace: `tokens = sum(t.input_tokens + t.output_tokens for t in
  trace.turns)`; `seconds = trace.duration_seconds`; `usd = tokens * token_cost_usd` (rate
  constructor arg, default 0.0). (Resolves analyst OQ-1/OQ-3 token aggregation.)
- **DD-05** parse `delivery_status` via `lib/delivery_status.parse_delivery_status` from
  `trace.final_text_snippet`; fallback to the trailing fence of the newest pipeline artifact when
  the 500-char snippet yields nothing; no fence/`None` trace → `AgentResult(status="failed")`.
- **DD-06** `runGate` delegates to `app.pipeline.gate.runGate(gate, paths, space, gate_id,
  state_path)` (outcome re-execution already in SG2) → map to `results.GateResult` + `state.write`.
- **DD-07** `evalCondition` delegates to `app.harnesses.decision.eval_condition`; scope built by the
  orchestrator from `state.read().nodes` delivery_status fields (SG3 enrichment); sandboxed.
- **DD-08** `state.read/write` via `lib/state.StateStore`; node transitions appended to
  `events.jsonl` via `EventLog.append({…})` (single-dict signature — corrects analyst OQ-2).
- **DD-09** `telemetry.emit` via `lib/telemetry.TelemetrySink(usd_ceiling, state_store)` → persists
  `usd_spent`; `BudgetExceededSignal` on breach → orchestrator escalates.
- **DD-10** `escalate(node_id, reason)` parks the run's tracking task → `WAITING` +
  `waiting_question=reason`; `state.status="blocked"`; idempotent.
- **DD-11** G6.2 e2e: monkeypatched `store` + `trace_store` feeding scripted `delivery_status` per
  node; SEQUENTIAL dispatch (parallel fan-out deferred — analyst OQ-3); asserts path, has_ui skip,
  both review routes, outcome-gate loop convergence, state/event reconstruction, `usd_spent > 0`.

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Async `dispatchAgent` vs sync Protocol (R1–R3 vs R9) | high | DD-02 async method; runtime_checkable checks presence → isinstance passes; documented |
| `final_text_snippet` truncated to 500 clips `delivery_status` (R3) | high | DD-05 compact terminal block + artifact-trailing-fence fallback; >500-char regression test |
| `RunTrace` has no token total → zero telemetry (R7) | medium | DD-04 sum per-turn `input_tokens+output_tokens`; usd via rate; e2e asserts usd_spent>0 |
| EventLog signature is `append(event)` not `append(node_id, event)` (R6) | medium | DD-08 node_id inside the dict; EventLog already exists; events.jsonl line-per-transition test |
| E2E flakiness / parallel fan-out (R10–R12) | high | DD-11 stub store+trace_store, sequential dispatch, scripted node outcomes |
| Import-boundary regression (`lib`/`runner` ⊄ `app.*`) | medium | DD-01 all app.* code in adapters/cronos (exempt) + lazy imports; boundary test guard |

## Assumptions

- **Requirements are the analyst's R1–R12 verbatim** (`traceability[]` of
  `analysis-report-delivery-v1-cronos-adapter.md`); all twelve verify in the `test` phase. No
  requirement is invented or dropped; iterations_planned = 6 covers all twelve (see the Reqs column).
- **Phases 0–5 are complete and green**: `interface.py`, `results.py`, `state_types.py`,
  `lib/state/{store,events}.py`, `lib/telemetry/sink.py`, `lib/delivery_status.py`,
  `app.pipeline.gate.runGate`, `app.harnesses.decision.eval_condition` exist and pass their own
  tests; the adapter only wraps them.
- **Tracking-task model** (analyst assumption): one `type=goal` tracking task is the visible Cronos
  board entry per delivery/v1 run; its id is supplied to the adapter (constructor `tracking_task_id`
  or set per run). `escalate` parks THAT task — this is why `escalate(node_id, …)` needs no
  per-node→task registry; node_id is only a `state.json` key.
- **Scope is pre-built by the orchestrator**, not the adapter (R5): `evalCondition` receives a ready
  `scope` and only delegates; building scope from `state.read().nodes` fields is the orchestrator's
  job (the standalone runner / delivery/v1 driver), consistent with SG3.
- **Token rate ships at 0.0** by default (`token_cost_usd`): the feature works without a pricing
  table; the e2e test sets a non-zero rate to satisfy R10 ac-4 (`usd_spent` non-zero). Real
  per-model pricing is a deferred follow-up (analyst "Deferred").
- **Tests live in `backend/tests/`** with `PYTHONPATH=../packages/delivery-workflow`: the only
  environment where both `app.*` and the bundle resolve; the implementor should also
  `pip install -e packages/delivery-workflow` to refresh the editable .pth (currently pointing at a
  stale sibling workspace), but the PYTHONPATH guard makes the runs correct regardless.
- **Per-iteration `--override-ini="addopts="`** keeps the narrow per-file run from tripping the repo
  `--cov-fail-under=80` floor (the `pipeline-narrow-k-coverage` memory); full-suite coverage is
  enforced at `/goal-finalize`.

## Open questions

- **None blocking — the analyst's three open questions are resolved:** (1) **token field names** —
  `AssistantTurnTrace.{input_tokens,output_tokens}` summed across `trace.turns`; no top-level total
  exists (DD-04). (2) **EventLog existence/signature** — present at `lib/state/events.py` with
  `append(event: dict)` (single dict, auto-`ts`), NOT the assumed `append(node_id, event)` (DD-08).
  (3) **parallel fan-out** — out of scope for G6.2; dispatch sequentially (DD-11). The **critical
  async/sync Protocol divergence** the analyst flagged is decided in favour of option (a): async
  `dispatchAgent`, conformance preserved by `runtime_checkable` semantics (DD-02). One non-blocking
  follow-up for the **standalone runner** (Phase 7): whether to thread full agent final-text into
  `RunTrace` so adapters never depend on the 500-char snippet — noted, not in SG6.

## Next consumer brief

Read the analyst `traceability[]` (R1–R12 + acceptance criteria), this `iterations[]`, and the DD
list first. Build order is **I1 → {I2,I3,I4} → I5 → I6**; do not start I5 until I1–I4 are green
(the integration test wires all six ops through one `CronosAdapter`). Cross-iteration invariants
NOT derivable from the YAML:

- **Single module, lazy app imports (all iterations):** everything lands in
  `packages/delivery-workflow/adapters/cronos/adapter.py`; import `app.pipeline.gate` /
  `app.harnesses.decision` / `app.storage` / `app.trace_store` LAZILY inside methods, never at
  module top level. Do not add `app.*` imports to `lib/` or `runner/` (breaks
  `test_import_boundary.py`). Always RETURN bundle types: `results.AgentResult`,
  `results.GateResult`, `state_types.WorkflowState`.
- **Conformance (I1, R9):** `@runtime_checkable` Protocol checks presence only — keep all six method
  names exact (`dispatchAgent`, `runGate`, `evalCondition`, `escalate`, `state.read`, `state.write`,
  `telemetry.emit`); `async def dispatchAgent` is fine and intended.
- **Dispatch (I2, R1–R3):** child brief MUST start `# Agent: {agent_ref}` and list every artifact
  path in `inputs`; goal → `ACTIVE`; poll with `asyncio.sleep(poll_interval)` (no busy-wait);
  WAITING → `status="blocked"` with the `waiting_question` in `open_questions`; timeout →
  `escalate` + `TimeoutError`. Parse `delivery_status` from `trace.final_text_snippet` (full-text
  follow-up noted); add the >500-char regression test.
- **Telemetry (I1, R7):** tokens = `sum(t.input_tokens + t.output_tokens for t in trace.turns)`;
  `seconds = trace.duration_seconds`; `usd = tokens * token_cost_usd`. There is NO `trace.tokens`.
- **Gate (I3, R4):** pass `gate_id` + `state_path` through to `app.pipeline.gate.runGate` so the SG2
  state-write happens; do NOT re-run checks — only map decision/errors/evidence to
  `results.GateResult`. A lying impl-report over a broken build must surface `needs_fix`, not `proceed`.
- **EventLog (I1, R6):** `EventLog.append({"node_id":…, "status":…, "type":"node_transition"})` —
  single dict, node_id inside; `ts` auto-injected.
- **Escalate (I5, R8):** operate on the run's tracking task id; idempotent if already WAITING;
  `state.status` becomes `"blocked"`.
- **E2E (I6, R10–R12):** assert (a) realised path scout→g-scout→analyze→g-analysis→signoff-scope→
  architect→g-design→signoff-design→testarch→implement→g-build→review→g-review→testrun→g-tests→doc→
  g-doc→release; (b) `has_ui=false` skips `frontend` (`evalCondition("analyze.fields.has_ui == true")`
  is False → route to `architect`); (c) review routing — `needs_fix·local`→`implement`,
  `needs_fix·architectural`→`architect`, `pass`→`testrun`; (d) one `g-tests`/`g-build` outcome loop
  (needs_fix attempt 1, proceed attempt 2 → two `implement` dispatches; loop exits on
  `evalCondition`, not a counter; same-diff stall → `escalate`); (e) a fresh `StateStore.read()` +
  `EventLog.read_all()` reconstruct every node state; `budget.usd_spent` is a non-zero float. Mark
  the milestone in the final assertion message: `=== delivery/v1 done on Cronos ===`.
