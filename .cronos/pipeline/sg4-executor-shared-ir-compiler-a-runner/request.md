Spec 4 — The executor: shared IR + Compiler A + runner (full harvest)

Fixes #3: delivery workflow routing edges (`needs_fix → implement`) are dead because the runner is a stub and the worker uses static depends_on instead.

### 4.1 Shared graph IR (package, app-free)

```
IRNode: id, kind, data, loop: LoopPolicy|None
  kind = union of delivery + Harness kinds:
    agent | gate | human | decision | wait | aggregator | trigger

IREdge: source, target, when (guard expr from lib/conditions), port (metadata only)

IRGraph: nodes, edges, variables, metadata
  entry_nodes: computed
  cycles: LEGAL (validation is structural only)
```

Design decisions:
- kind is the UNION of both formats (delivery: agent/gate/human; Harness: decision/wait/aggregator/trigger) — both compile in losslessly
- Edges route on when (delivery's when ≡ Harness's condition); ports are metadata only
- Cycles are legal — IR validation is structural, not topological
- decision nodes are pure routing (no dispatch)
- LoopPolicy is uniform: {until, stall[], max, on_exhaust}

Runtime state: package's WorkflowState (state_types.py) — per-node status/attempt/artifacts/telemetry

### 4.2 Compiler A

Input: validated spec dict from spec_loader.load_spec. Mostly 1:1 — each node (agent/gate/human) → IRNode; each edge (from/to/when) → IREdge; resolve defaults.models into concrete agent.model; fold defaults.budget into metadata. Lives in package. app-free.

### 4.3 Runner (cyclic work-list walker, full harvest)

Fixpoint work-list walker (NOT topological sort):
- Per-node state from WorkflowState for resume (NodeState.attempt present)
- Entry from trigger/root nodes; node runs when inputs satisfied
- Execute node → evaluate outgoing edges' when against scope enriched from node_status fields → enqueue chosen targets
- Back-edges = loop iterations; increments attempt counter; resets downstream
- Per-node loop {until, stall, max, on_exhaust}; on_exhaust:escalate → ExecutorInterface.escalate (HARVEST from _execute_agent_node)
- Gate nodes → ExecutorInterface.runGate (CronosAdapter → app.pipeline.gate)
- FULL HARVEST of all node kinds from HarnessExecutor → port to WorkflowState+ExecutorInterface:
    agent, gate, human, decision (HARVEST _execute_decision_node),
    wait with human+timed park/resume (HARVEST _execute_wait_node),
    aggregator any/all (HARVEST _execute_aggregator_node),
    trigger pass-through
- Events via ExecutorInterface events op (not lifted from HarnessExecutor._publish)
- Cancel-race guards at work-list boundaries (HARVEST)
- NullRuntime already exists in package

### 4.4 Cronos integration

Driver: construct CronosAdapter → runner.run(Compiler_A(spec_loader.load(...)), adapter). Worker in backend/app/worker.py: detect delivery-workflow-bound goal → route to driver instead of _topo_children. Runner tags dispatched child tasks (marker in task brief or metadata) for needs_fix→DONE bridge mapping.

### References
- `packages/delivery-workflow/` — the package; spec_loader.py, state_types.py, interface.py, null_runtime.py all exist
- `backend/app/harnesses/executor.py` — HarnessExecutor to harvest (BFS walker to replace with runner)
- `backend/app/worker.py` — _topo_children route to intercept for delivery goals
- `backend/app/harnesses/decision.py` — decision/aggregator/wait handlers to harvest
- `packages/delivery-workflow/.importlinter` — boundary enforced; runner must not import app

