---
cc_version: "1.0"
agent: pipeline-scout
slug: sg4-executor-shared-ir-compiler-a-runner
phase: scout
status: done
confidence: 0.88
inputs_used:
  - memory:project_delivery_v1_cronos_adapter_design
  - memory:project_arc6_64_run_lifecycle_review
  - memory:project_sg3_conditions_impl
  - packages/delivery-workflow/interface.py
  - packages/delivery-workflow/state_types.py
  - packages/delivery-workflow/spec_loader.py
  - packages/delivery-workflow/null_runtime.py
  - packages/delivery-workflow/results.py
  - packages/delivery-workflow/lib/conditions.py
  - packages/delivery-workflow/adapters/cronos/adapter.py
  - packages/delivery-workflow/delivery.workflow.yaml
  - packages/delivery-workflow/.importlinter
  - backend/app/harnesses/executor.py
  - backend/app/harnesses/decision.py
  - backend/app/harnesses/wait.py
  - backend/app/worker.py
  - backend/app/harnesses/model.py
outputs_produced:
  - .cronos/pipeline/sg4-executor-shared-ir-compiler-a-runner/scout-report-sg4-executor-shared-ir-compiler-a-runner.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - packages/delivery-workflow/
    - backend/app/harnesses/
    - backend/app/worker.py
  excluded:
    - frontend/src/
  strategies:
    - memory_retrieval
    - glob_structural
    - grep_symbol
    - read_targeted
brief: "Conduct memory-first reconnaissance of: (1) shared IR package state (2) Compiler A status (3) HarnessExecutor patterns to harvest (4) worker integration points (5) importlinter boundary (6) testing baseline (7) traceability links"
metrics:
  tool_calls: 15
  files_read: 16
  memory_hits: 3
---

## Summary

The shared IR package (packages/delivery-workflow/) is foundational but incomplete. Core abstractions exist: ExecutorInterface protocol, WorkflowState dataclass, spec_loader.py validation, NullRuntime stub, and lib/conditions.py (SG3-complete). **Compiler A (spec → IR) is not implemented**—only spec_loader validates; no IR types, no defaults resolution. **Runner is stubbed** (empty runner/__init__.py). CronosAdapter wires the interface but awaits a functional runner. HarnessExecutor (backend) has complete BFS patterns ready to harvest: 7 node kinds, cancel-race guards, resume reconciliation, event publishing. **Key gap**: runner.py must implement work-list walking, loop enforcement, and bridge delivery_status → needs_fix/DONE routing for SG1 integration.

## Coverage

### Searched
- packages/delivery-workflow/ — interface.py, state_types.py, spec_loader.py, null_runtime.py, results.py, lib/conditions.py, adapters/cronos/adapter.py, delivery.workflow.yaml
- backend/app/harnesses/executor.py — BFS walker, node dispatch, cancel-race guards, resume reconciliation
- backend/app/harnesses/decision.py — decision.evaluate_decision(), 4-layer signal precedence
- backend/app/harnesses/wait.py — human (WaitOutcome) and timed (await_timed_wait) modes
- backend/app/harnesses/model.py — NodeType enum, node data conventions
- backend/app/worker.py — _topo_children route, _run_goal entry

### Excluded
- frontend/src/ — SG4 is executor/compiler, no UI scope
- backend/tests/ — covered by memory + focused file reads

### Strategies
- memory_retrieval: 3 entries (delivery_v1_cronos_adapter_design, arc6_64_run_lifecycle_review, sg3_conditions_impl)
- glob_structural: packages/delivery-workflow/ tree; runner/ stubbed; adapters/ has CronosAdapter
- grep_symbol: _topo_children, _run_goal, HarnessExecutor, WorkerProtocol, node_by_id, ready_queue
- read_targeted: 16 files read to depth; imports/signatures/key patterns extracted

## Findings

### 1. Shared IR Package — Current State

**Exists:**
- interface.py — ExecutorInterface protocol (dispatchAgent, runGate, evalCondition, escalate; state/telemetry sub-protocols); R9 compliance
- state_types.py — WorkflowState(spec, run_id, status, budget, nodes), NodeState(status, attempt, gate, artifact_paths, telemetry), BudgetState
- results.py — AgentResult(status, artifact_paths, produces, fields, open_questions, telemetry), GateResult(decision, errors, evidence), TelemetryData
- spec_loader.py — load_spec(path), loads_spec(str) → validate via jsonschema; raises ValueError on breach
- null_runtime.py — NullRuntime stub (all ops raise NotImplementedError); R5 test baseline
- lib/conditions.py — eval_condition(condition, scope) lifted from harnesses/decision.py; ==, !=, in, &&, || (OR-of-ANDs); byte-identical regex
- .importlinter — forbidden contract: lib + runner cannot import app.* or backend.*

**Missing (SG4 scope):**
- **No IRNode/IREdge/IRGraph types.** Request specifies: IRNode(id, kind, data, loop: LoopPolicy|None) where kind = union of delivery (agent/gate/human) + harness (decision/wait/aggregator/trigger); IREdge(source, target, when, port); IRGraph(nodes, edges, variables, metadata) with computed entry_nodes; LoopPolicy = {until, stall[], max, on_exhaust}
- **No Compiler A module.** spec_loader validates but does not compile to IR; no defaults.models resolution or defaults.budget folding

### 2. Compiler A Design Surface

**Input:** validated spec dict from spec_loader.load_spec() — nodes[], edges[], defaults.models, defaults.budget

**Output:** IR graph ready for runner — each node → IRNode; each edge → IREdge; resolve defaults.models (e.g., model.use="recon" → concrete haiku); fold defaults.budget into metadata

**Pattern:** 1:1 mostly lossless (per request 4.2); job is to reify defaults and structure into IR.

### 3. HarnessExecutor to Harvest — Full Patterns

**File:** backend/app/harnesses/executor.py (675+ LOC)

**BFS Runtime-Gated Walker (lines 459–630):**
- while ready_queue: node_id = ready_queue.popleft()
- Track in_queue: set[str] to avoid duplicate enqueues
- Per-node loop: cancel-race guard (reload RunState, check cancelled), skip already-done, fail-fast, node-type dispatch
- **Cancel-race pattern:** reload RunState from disk at BFS boundary; if status=='cancelled', stop and return
- **Resume reconciliation:** in_progress Agent nodes with child_task_id checked against store; if child DONE accept; else re-execute
- **Variable scope:** harness.variables merged; upstream node outputs override

**Node-Type Dispatch (lines 554–630):**
1. agent → _execute_agent_node() → (done, output, child_task_id, park); park flag = loop escalation
2. decision → _execute_decision_node() → chosen_edge_id | None; only enqueue chosen target
3. wait → _execute_wait_node() → park: bool; human (park=True), timed (await + park=False)
4. aggregator → _execute_aggregator_node() → (ready, failed); mode=all/any; pending stays out of queue
5. trigger → pass-through, mark done, enqueue successors
6. Unknown → skip with warning

**Event Publishing (lines 342–346, 514–520, etc.):**
- type: "node_transition" | "edge_chosen" | "run_status"
- Routed via self._worker._publish() if event_worker set; silent if None

### 4. Decision, Wait, Aggregator Handlers

**decision.py:**
- resolve_signal(predecessors_state, run_trace) → (layer, value) — 4-layer precedence: status > exit_reason > regex > variable
- edge_matches(edge, signal, scope) → bool — status/exit_reason direct match; regex via re.search; variable via eval_condition
- evaluate_decision(...) → edge_id | None — first matching edge or default-edge fallback

**wait.py:**
- enter_wait(node, run_state) → WaitOutcome — mutates run_state.waiting_node_id; returns WaitOutcome(action=park_waiting, waiting_node_id, waiting_question)
- await_timed_wait(node, run_state) — sleeps until wake_at (persisted on first entry); returns on resume

**aggregator.py (inferred):**
- aggregator_ready(node, predecessors_state) → (ready, failed) — mode=all (all preds done; any fail→fail) or mode=any (first pred done; fail if all fail)

### 5. Worker Integration Points

**File:** backend/app/worker.py

**Current route:**
- _topo_children(goal_id, store) → list[str] — Kahn's algorithm on sibling depends_on; manual_order tie-break
- _run_goal(goal_id, user_message) → delegates to RunExecutor.run_goal(); does NOT detect delivery-workflow-bound goals

**To harvest for SG4:**
- **Detection:** check if goal has metadata/brief field indicating delivery-workflow binding
- **Route:** if delivery-workflow-bound, call runner.run(compiler_A(...), CronosAdapter(...)) instead of RunExecutor.run_goal
- **Child task tagging:** runner tags dispatched child tasks with marker (in brief or metadata) for needs_fix→DONE bridge (SG1 dependency)

### 6. Testing Baseline — NullRuntime

**File:** packages/delivery-workflow/null_runtime.py

- NullRuntime class with state (_NullState), telemetry (_NullTelemetry), 5 exec methods
- All ops raise NotImplementedError (R5 stub for structure verification without real dispatch)
- **No runner tests yet** — runner not implemented; interface/spec_loader/conditions tests exist

### 7. Traceability Links

**SG1 (Sentinel Bridge — delivery_status marker):**
- agent outputs STATUS marker → decision.py status layer → edge routing → needs_fix edge → implement node → success → DONE
- Arch: delivery.workflow.yaml has when: status == needs_fix edges; runner must surface STATUS markers via scope

**SG3 (Conditions — complete):**
- lib/conditions.py shipped (commit c1b3a03); harnesses/decision.py now imports from lib.conditions (shim)
- eval_condition supports ==, !=, in, &&, || (OR-of-ANDs)

## Assumptions
- IR kind = union of delivery (agent/gate/human) + harness (decision/wait/aggregator/trigger) — 7 total; no format conversion
- LoopPolicy uniform across all node types: {until, stall[], max, on_exhaust}
- NullRuntime is test-only; never called in production
- Worker._topo_children unchanged; SG4 adds delivery-workflow detection route
- CronosAdapter is production-ready; already wired for state/telemetry/dispatch/eval/escalate
- importlinter enforced at CI; runner/lib cannot import app.*; adapters/cronos is exemption

## Open questions
- When node has model.use="recon", does Compiler A substitute concrete model string into IR, or leave as reference for runner resolution?
- Are entry_nodes = in_degree-0 nodes, or is there a separate trigger/root marker?
- Does LoopPolicy state (attempt, stall history, findings) live in NodeState.attempt only, or separate loop_state field?
- When agent outputs STATUS: needs_fix, is string stored in NodeState.output verbatim, or parsed into structured field?
- Do gate nodes produce artifact_paths? If so, merged into scope like agent outputs, or kept separate?

## Next consumer brief

**analysis** should expand on:

1. **IR schema completeness** — are all 7 node kinds required, or can some defer (e.g., trigger, human)?
2. **Compiler A iteration breakdown** — spec → IR is probably 2–3 iterations (I1 types/structs, I2 node compilation, I3 defaults). Estimate cycle count.
3. **Runner architecture** — work-list vs topological tradeoff; brief says cyclic work-list (back-edges allowed, loops via attempt counter). Confirm cycles legal.
4. **Worker detection strategy** — what metadata/brief field flags goal as delivery-workflow-bound? New Task field or inferred from agent/skill name?
5. **Bridge RFC** — SG1 needs_fix → DONE routing: does runner emit re-enqueue event, or does worker poll task.state post-gate-failure?
6. **Test strategy** — NullRuntime covers IR structure; what integration harness tests (with CronosAdapter) needed? Stub impl + e2e smoke?
