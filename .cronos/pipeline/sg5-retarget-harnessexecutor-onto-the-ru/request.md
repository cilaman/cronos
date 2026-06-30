Spec 5 — Retarget HarnessExecutor onto the runner

The unification. End-state: HarnessExecutor.execute = load harness → Compiler B → runner.run(ir, CronosAdapter). The runner is the substrate; the Harness visual editor becomes a consumer.

### 5.1 Compiler B — Harness → IR (Cronos-side)

Input: Harness (backend/app/harnesses/model.py). Map:
- HarnessNode.type → IRNode.kind (1:1 mapping)
- HarnessEdge{source:NodeRef, target:NodeRef, condition} → IREdge{source.node_id, target.node_id, when=condition, port=(source.port_id,target.port_id)}
- node.data.loop → IRNode.loop

Boundary: Compiler B imports the Harness model → lives in backend/app/harnesses/, NOT the package. IR types are the shared currency in the package. .importlinter stays green.

### 5.2 Runtime-state reconciliation

HarnessExecutor persists runs as RunState (harnesses/run_state.py); portable runner uses WorkflowState (package). Pick WorkflowState (app-free). Provide RunState→WorkflowState mapping in Cronos driver. Drain in-flight harness runs before cutover OR ship one-shot migration.

### 5.3 Migration (parity-gated)

1. (prereq) SG4 shipped — runner walks the IR, full harvest, proven on delivery
2. Compiler B; unit-test every .cronos/harnesses/*.yml fixture compiles to valid IR
3. PARITY HARNESS (the gate): run representative harnesses through both old BFS and runner(Compiler_B(harness)); assert identical RunState↔WorkflowState, event stream, and outcome. Cover: human-wait park/resume AND any/all aggregator
4. Events op reconciliation: runner emits via events op; CronosAdapter forwards to bus (replaces _publish)
5. Adapter reconciliation: HarnessExecutor's WorkerProtocol (run_agent/finalize_child/_publish) maps onto ExecutorInterface. CronosAdapter.dispatchAgent already creates+polls child tasks — reconciliation, not new behaviour
6. Cut over behind CRONOS_HARNESS_RUNNER; parity/shadow in prod; remove old BFS

### 5.4 No-regression argument

Existing harnesses are acyclic (current executor rejects cycles via _topo_sort). Dropping cycle-rejection ONLY ADDS capability — no regression by construction.

### References
- backend/app/harnesses/executor.py — HarnessExecutor to retarget
- backend/app/harnesses/model.py — Harness, HarnessNode, HarnessEdge types (Compiler B input)
- backend/app/harnesses/run_state.py — RunState (to reconcile with WorkflowState)
- packages/delivery-workflow/ — runner (SG4), WorkflowState, ExecutorInterface
- .cronos/harnesses/*.yml — existing harness fixtures to test Compiler B

