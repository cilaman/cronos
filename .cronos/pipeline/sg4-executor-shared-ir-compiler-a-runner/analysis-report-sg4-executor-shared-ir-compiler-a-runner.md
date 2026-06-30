---
cc_version: '1.0'
agent: pipeline-analyst
slug: sg4-executor-shared-ir-compiler-a-runner
phase: analysis
status: done
confidence: 0.87
inputs_used:
- memory:project_delivery_v1_cronos_adapter_design
- memory:project_pipeline_verifier
- memory:project_pipeline_foundation_merged
- .cronos/pipeline/sg4-executor-shared-ir-compiler-a-runner/scout-report-sg4-executor-shared-ir-compiler-a-runner.md
- packages/delivery-workflow/interface.py
- packages/delivery-workflow/state_types.py
- packages/delivery-workflow/delivery.workflow.yaml
- packages/delivery-workflow/adapters/cronos/adapter.py
- backend/app/harnesses/executor.py
- backend/app/worker.py
outputs_produced:
- .cronos/pipeline/sg4-executor-shared-ir-compiler-a-runner/analysis-report-sg4-executor-shared-ir-compiler-a-runner.md
blockers: []
next_consumer: design
request: "Spec 4 — The executor: shared IR + Compiler A + runner (full harvest)\n\n\
  Fixes #3: delivery workflow routing edges (`needs_fix → implement`) are dead because\
  \ the runner is a stub and the worker uses static depends_on instead.\n\n### 4.1\
  \ Shared graph IR (package, app-free)\n\nIRNode: id, kind, data, loop: LoopPolicy|None\n\
  \  kind = union of delivery + Harness kinds:\n    agent | gate | human | decision\
  \ | wait | aggregator | trigger\n\nIREdge: source, target, when (guard expr from\
  \ lib/conditions), port (metadata only)\n\nIRGraph: nodes, edges, variables, metadata\n\
  \  entry_nodes: computed\n  cycles: LEGAL (validation is structural only)\n\nDesign\
  \ decisions:\n- kind is the UNION of both formats (delivery: agent/gate/human; Harness:\
  \ decision/wait/aggregator/trigger) — both compile in losslessly\n- Edges route\
  \ on when (delivery's when equiv Harness's condition); ports are metadata only\n\
  - Cycles are legal — IR validation is structural, not topological\n- decision nodes\
  \ are pure routing (no dispatch)\n- LoopPolicy is uniform: {until, stall[], max,\
  \ on_exhaust}\n\nRuntime state: package's WorkflowState (state_types.py) — per-node\
  \ status/attempt/artifacts/telemetry\n\n### 4.2 Compiler A\n\nInput: validated spec\
  \ dict from spec_loader.load_spec. Mostly 1:1 — each node (agent/gate/human) ->\
  \ IRNode; each edge (from/to/when) -> IREdge; resolve defaults.models into concrete\
  \ agent.model; fold defaults.budget into metadata. Lives in package. app-free.\n\
  \n### 4.3 Runner (cyclic work-list walker, full harvest)\n\nFixpoint work-list walker\
  \ (NOT topological sort):\n- Per-node state from WorkflowState for resume (NodeState.attempt\
  \ present)\n- Entry from trigger/root nodes; node runs when inputs satisfied\n-\
  \ Execute node -> evaluate outgoing edges' when against scope enriched from node_status\
  \ fields -> enqueue chosen targets\n- Back-edges = loop iterations; increments attempt\
  \ counter; resets downstream\n- Per-node loop {until, stall, max, on_exhaust}; on_exhaust:escalate\
  \ -> ExecutorInterface.escalate (HARVEST from _execute_agent_node)\n- Gate nodes\
  \ -> ExecutorInterface.runGate (CronosAdapter -> app.pipeline.gate)\n- FULL HARVEST\
  \ of all node kinds from HarnessExecutor -> port to WorkflowState+ExecutorInterface:\n\
  \    agent, gate, human, decision (HARVEST _execute_decision_node),\n    wait with\
  \ human+timed park/resume (HARVEST _execute_wait_node),\n    aggregator any/all\
  \ (HARVEST _execute_aggregator_node),\n    trigger pass-through\n- Events via ExecutorInterface\
  \ events op (not lifted from HarnessExecutor._publish)\n- Cancel-race guards at\
  \ work-list boundaries (HARVEST)\n- NullRuntime already exists in package\n\n###\
  \ 4.4 Cronos integration\n\nDriver: construct CronosAdapter -> runner.run(Compiler_A(spec_loader.load(...)),\
  \ adapter). Worker in backend/app/worker.py: detect delivery-workflow-bound goal\
  \ -> route to driver instead of _topo_children. Runner tags dispatched child tasks\
  \ (marker in task brief or metadata) for needs_fix->DONE bridge mapping.\n\n###\
  \ References\n- packages/delivery-workflow/ — the package; spec_loader.py, state_types.py,\
  \ interface.py, null_runtime.py all exist\n- backend/app/harnesses/executor.py —\
  \ HarnessExecutor to harvest (BFS walker to replace with runner)\n- backend/app/worker.py\
  \ — _topo_children route to intercept for delivery goals\n- backend/app/harnesses/decision.py\
  \ — decision/aggregator/wait handlers to harvest\n- packages/delivery-workflow/.importlinter\
  \ — boundary enforced; runner must not import app"
has_ui: false
coverage_summary:
  searched:
  - packages/delivery-workflow/
  - backend/app/harnesses/
  - backend/app/worker.py
  excluded:
  - frontend/src/: backend/package-only feature — SG4 has no UI scope
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
  - traceability_mapping
traceability:
- requirement_id: R1
  statement: The package defines IRNode, IREdge, IRGraph, and LoopPolicy dataclasses
    in packages/delivery-workflow/ with no app.* imports, covering all 7 node kinds
    (agent, gate, human, decision, wait, aggregator, trigger).
  acceptance_criteria:
  - Given packages/delivery-workflow/ir.py (or equivalent), when imported in isolation
    (no app.* in sys.modules), then all four types are importable with their specified
    fields.
  - IRNode.kind accepts all 7 values from the union; extra values raise ValueError.
  - IRGraph.entry_nodes is a computed property returning IDs of nodes with no incoming
    edges.
  - 'LoopPolicy fields are: until (str expression), stall (list[str]), max (int),
    on_exhaust (Literal[''escalate'',''stop'']).'
  - importlinter CI gate passes with the new ir.py module present.
  verifying_phase: test
  confidence: 0.92
- requirement_id: R2
  statement: Compiler A (packages/delivery-workflow/compiler_a.py or equivalent) transforms
    a validated spec dict produced by spec_loader.load_spec() into an IRGraph, resolving
    model aliases and folding budget defaults.
  acceptance_criteria:
  - Given a delivery.workflow.yaml spec loaded via spec_loader.load_spec(), when compile(spec_dict)
    is called, then every node entry in spec_dict['nodes'] produces exactly one IRNode
    in IRGraph.nodes.
  - 'Given a node with model: {use: recon} and defaults.models.recon = ''haiku'',
    when compiled, then the resulting IRNode.data[''model''] is ''haiku'' (concrete
    string).'
  - Given defaults.budget.usd_ceiling = 25.0, when compiled, then IRGraph.metadata['budget']['usd_ceiling']
    == 25.0.
  - Every edge entry in spec_dict['edges'] produces exactly one IREdge with source,
    target, and when (empty string when absent).
  - Compiler A has no imports from app.* or backend.*; importlinter passes.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R3
  statement: The runner module (packages/delivery-workflow/runner/) implements a cyclic
    work-list walker that executes an IRGraph via ExecutorInterface, supporting resume,
    cancel-race guarding, and per-node loop policies.
  acceptance_criteria:
  - Given an IRGraph and an ExecutorInterface implementation, when runner.run(graph,
    executor) is called, then entry nodes (in_degree == 0) are seeded into the work-list
    first.
  - Given a node whose outgoing edges have 'when' conditions, when the node completes,
    then only edges whose 'when' evaluates True against the enriched scope are followed.
  - Given WorkflowState.nodes[node_id].attempt >= LoopPolicy.max, when the loop condition
    is not satisfied, then executor.escalate(node_id, reason) is called and the work-list
    halts for that node.
  - Given a back-edge (loop iteration), when the loop condition is not yet satisfied
    and max is not exceeded, then NodeState.attempt is incremented and downstream
    nodes are reset to pending.
  - Given WorkflowState.status == 'cancelled' detected at the work-list boundary,
    then the runner returns immediately without executing the next node.
  - Given a partially executed IRGraph state, when runner.run() is called again, then
    already-done nodes are skipped and execution resumes from pending nodes.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R4
  statement: 'The runner dispatches all 7 node kinds through ExecutorInterface: agent
    nodes via dispatchAgent, gate nodes via runGate, decision nodes via evalCondition
    for edge routing, wait nodes via escalate (human) or sleep (timed), aggregator
    nodes via all/any predecessor inspection, trigger nodes as pass-through, and human
    nodes as escalate-to-waiting.'
  acceptance_criteria:
  - Given an agent IRNode, when executed, then dispatchAgent(node.data['agent'], inputs)
    is called and AgentResult.status is stored in NodeState.
  - Given a gate IRNode, when executed, then runGate(node.data, artifact_paths) is
    called and GateResult.decision is stored in NodeState as the 'decision' field.
  - Given a decision IRNode, when executed, then only the single outgoing edge whose
    'when' evaluates True is enqueued (or none if no edge matches).
  - Given a wait IRNode with mode=human, when executed, then executor.escalate() is
    called and the runner parks the work-list.
  - Given an aggregator IRNode with mode=all, when executed, then it only proceeds
    when all predecessor nodes are done; any failure fails the aggregator.
  - Given an aggregator IRNode with mode=any, when executed, then it proceeds when
    the first predecessor is done; it fails only if all predecessors fail.
  - Given a trigger IRNode, when executed, then it is immediately marked done and
    successors are enqueued.
  verifying_phase: test
  confidence: 0.87
- requirement_id: R5
  statement: The runner scope enrichment after each node makes all node outputs available
    to downstream edge 'when' conditions, using the naming convention node_id.fields.key
    and node_id.decision for gate/decision nodes.
  acceptance_criteria:
  - Given an agent node 'review' that produces fields.verdict='pass', when downstream
    edges evaluate 'review.fields.verdict == pass', then evalCondition returns True.
  - Given a gate node 'g-build' that returns GateResult.decision='proceed', when a
    downstream edge evaluates 'g-build.decision == proceed', then evalCondition returns
    True.
  - Given a node with no outputs, when downstream edges evaluate a key from that node,
    then evalCondition returns False (not an error).
  verifying_phase: test
  confidence: 0.85
- requirement_id: R6
  statement: Worker (backend/app/worker.py) detects delivery-workflow-bound goals
    by a marker in the task brief and routes them to the delivery runner instead of
    _topo_children / RunExecutor.run_goal.
  acceptance_criteria:
  - 'Given a goal task whose brief contains the sentinel ''<!-- delivery-workflow:
    <spec_path> -->'', when the worker processes it, then the delivery driver (runner.run
    + CronosAdapter) is invoked.'
  - Given a goal task with no delivery-workflow sentinel, when the worker processes
    it, then _topo_children / RunExecutor.run_goal is invoked as before (no regression).
  - The detection logic is in a single function/method that can be unit-tested independently
    of the CronosAdapter.
  verifying_phase: test
  confidence: 0.8
- requirement_id: R7
  statement: The delivery driver constructs a CronosAdapter with the correct store,
    trace_store, space_id, and run_dir, then calls runner.run(Compiler_A(spec_loader.load(spec_path)),
    adapter) when a delivery-workflow-bound goal is activated.
  acceptance_criteria:
  - Given a delivery-workflow goal with a valid spec_path, when the driver is invoked,
    then spec_loader.load_spec(spec_path) is called before compiler_a.compile().
  - Given a CronosAdapter constructed by the driver, then its run_dir is a stable
    per-goal path under the space .cronos/ directory.
  - Given runner.run() raises an exception, then the driver catches it, transitions
    the goal to WAITING with an appropriate waiting_question, and does not crash the
    worker loop.
  verifying_phase: test
  confidence: 0.82
- requirement_id: R8
  statement: Child tasks dispatched by the runner are tagged with a delivery-node
    marker (in brief metadata) so that the worker's needs_fix to implement re-routing
    bridge can identify them.
  acceptance_criteria:
  - 'Given a runner dispatching an agent node, when the child task is created via
    CronosAdapter.dispatchAgent(), then the task brief contains ''<!-- delivery-node:
    <node_id> -->''.'
  - 'Given a child task marked with a delivery-node sentinel that completes with STATUS:
    needs_fix, when the worker''s post-task callback fires, then the runner''s work-list
    is re-seeded at the correct node rather than following static depends_on.'
  - Given a child task without a delivery-node sentinel, when it completes, then the
    existing worker routing is unchanged.
  verifying_phase: test
  confidence: 0.75
- requirement_id: R9
  statement: The runner, Compiler A, and IR types reside entirely within packages/delivery-workflow/
    and import no app.* or backend.* symbols; the importlinter boundary contract continues
    to pass in CI.
  acceptance_criteria:
  - Given the updated packages/delivery-workflow/ directory, when 'python -m importlinter'
    is run against .importlinter, then all contracts pass with exit code 0.
  - Given any module in packages/delivery-workflow/runner/ or packages/delivery-workflow/lib/,
    when inspected for imports, then no app.* or backend.* imports are present.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R10
  statement: Unit tests covering IR construction, Compiler A output, runner work-list
    logic, and worker routing are added and pass under the 80% coverage floor.
  acceptance_criteria:
  - Given the NullRuntime stub, when used as the ExecutorInterface in runner tests,
    then IR construction, work-list seeding, edge evaluation, and loop-counter increment
    are all exercised.
  - Given a delivery.workflow.yaml fixture, when Compiler A processes it, then the
    test asserts IRGraph has the expected node count, model resolution, and budget
    metadata.
  - Given a worker test fixture, when a delivery-workflow brief is present, then the
    worker routing test asserts the driver path is taken.
  - pytest with coverage reports >= 80% line coverage across new modules.
  verifying_phase: test
  confidence: 0.85
metrics:
  tool_calls: 12
  files_read: 7
  memory_hits: 3
---

## Summary

SG4 activates the delivery workflow executor end-to-end. The package (packages/delivery-workflow/) has its scaffolding — ExecutorInterface, WorkflowState, spec_loader, NullRuntime, lib/conditions — but is missing three components: IR types (IRNode/IREdge/IRGraph/LoopPolicy), Compiler A (spec dict to IR), and the runner (cyclic work-list walker). The runner must fully harvest HarnessExecutor's BFS patterns covering all 7 node kinds, loop enforcement, cancel-race guards, and resume semantics. Worker integration adds delivery-workflow-bound goal detection and routes those goals to the driver instead of the existing _topo_children / RunExecutor path. The needs_fix to implement back-edge routing is currently dead because no runner evaluates the edge conditions; SG4 makes those edges live.

## Scope

### In scope
- IR type definitions: IRNode, IREdge, IRGraph, LoopPolicy in packages/delivery-workflow/ (app-free)
- Compiler A: spec dict to IRGraph with model alias resolution and budget folding
- Runner: cyclic work-list walker with full 7-kind dispatch via ExecutorInterface
- Runner scope enrichment: node outputs published to downstream edge 'when' evaluation
- Loop policy enforcement: until/stall/max/on_exhaust per node
- Cancel-race guards at work-list boundaries (harvested from HarnessExecutor)
- Resume from persisted WorkflowState
- Worker detection of delivery-workflow-bound goals via brief sentinel
- Delivery driver: construct CronosAdapter then runner.run(compile(spec))
- Child task tagging for needs_fix to DONE bridge
- importlinter boundary compliance
- Unit and integration tests covering all new modules

### Out of scope
- Changes to CronosAdapter (already implemented per scout findings)
- Changes to spec_loader.py (already implemented)
- Changes to lib/conditions.py (SG3-complete)
- Changes to HarnessExecutor (runner replaces its role for delivery graphs; HarnessExecutor is unchanged)
- Frontend UI or API endpoints
- New gate check types (existing app.pipeline.gate is used as-is via runGate)

### Deferred
- LoopPolicy stall-detection heuristics (recurring_findings, no_diff_progress): runner accepts stall[] list but stall analysis logic is a follow-on
- Compiler B (Harness to IR translation) for Harness-native formats
- Distributed/parallel node execution (runner is sequential within the work-list)
- Dashboard visibility of delivery workflow run progress via SSE

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | Define IR types (IRNode, IREdge, IRGraph, LoopPolicy) app-free in the package |
| R2 | Implement Compiler A: spec dict to IRGraph with model alias and budget resolution |
| R3 | Implement cyclic work-list runner with resume, cancel-race guard, and loop policy |
| R4 | Dispatch all 7 node kinds through ExecutorInterface in the runner |
| R5 | Enrich runner scope after each node so downstream edge conditions can resolve |
| R6 | Worker detects delivery-workflow-bound goals via brief sentinel and routes to driver |
| R7 | Delivery driver constructs CronosAdapter and invokes runner.run(compile(spec)) |
| R8 | Child tasks tagged with delivery-node marker for needs_fix to implement back-edge bridge |
| R9 | importlinter boundary: runner and IR types have no app.* or backend.* imports |
| R10 | Unit and integration tests cover IR, Compiler A, runner, and worker routing |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). The body summary below mirrors them in compact form for the human reader.

- R1 — IR types importable in isolation; all 7 kinds accepted; entry_nodes computed; importlinter passes
- R2 — Each spec node produces one IRNode; model aliases resolved; budget folded into metadata; no app.* imports
- R3 — Entry nodes seeded first; only True-guarded edges followed; loop counter incremented; cancel detected at boundary; resume skips done nodes
- R4 — agent to dispatchAgent; gate to runGate; decision to single-edge routing; wait-human to escalate+park; aggregator all/any semantics; trigger pass-through
- R5 — Agent fields and gate decision published to scope; downstream evalCondition uses them; missing keys return False
- R6 — Sentinel brief triggers driver path; non-sentinel brief triggers existing path with no regression
- R7 — spec_loader called before compile; run_dir is stable per-goal path; runner exception parks goal to WAITING
- R8 — Child brief contains delivery-node sentinel; needs_fix completion re-seeds work-list at correct node; non-tagged tasks unaffected
- R9 — importlinter exits 0; no app.* or backend.* imports in runner/ or lib/
- R10 — NullRuntime exercises IR, work-list, and edge eval; Compiler A tested against delivery.workflow.yaml fixture; worker routing tested; coverage >= 80%

## Traceability

The full requirement to acceptance criteria to verifying_phase map is the YAML `traceability[]` array. Downstream agents read the YAML directly; this section exists so a human reader sees the same routing table without parsing YAML.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | IR types (IRNode, IREdge, IRGraph, LoopPolicy) defined app-free covering all 7 node kinds |
| R2 | test | Compiler A transforms spec dict to IRGraph with model alias and budget resolution |
| R3 | test | Cyclic work-list runner with resume, cancel-race guard, and loop policy enforcement |
| R4 | test | All 7 node kinds dispatched through ExecutorInterface in the runner |
| R5 | test | Runner scope enrichment makes node outputs available to downstream edge conditions |
| R6 | test | Worker detects delivery-workflow-bound goals via brief sentinel and routes to driver |
| R7 | test | Delivery driver constructs CronosAdapter and calls runner.run(compile(spec)) |
| R8 | test | Child tasks tagged with delivery-node marker enabling needs_fix to implement bridge |
| R9 | test | importlinter boundary: no app.* or backend.* imports in package runner/lib |
| R10 | test | Unit and integration tests cover all new modules at >= 80% coverage |

## Assumptions

- has_ui=false rationale: the request is entirely about backend package modules (IR types, Compiler A, runner) and worker routing; no screens, forms, or visual state are involved.
- IR validation is structural only (node/edge references resolve); topological sort is NOT required; cycles are legal because back-edges implement loop iterations.
- entry_nodes are computed as nodes with in_degree == 0 (no incoming edges in IRGraph.edges). The request says "entry from trigger/root nodes" which aligns with in-degree-0 detection.
- Model alias resolution in Compiler A substitutes concrete model strings at compile time (e.g., {use: recon} to 'haiku'). If a model alias is undefined in defaults.models, Compiler A raises ValueError.
- The delivery-workflow sentinel in the task brief takes a form such as `<!-- delivery-workflow: <spec_path> -->`. This is an assumption because the request does not specify the exact sentinel format; the design agent should confirm or revise this.
- NodeState.attempt is the sole loop-iteration counter; no separate loop_state field is needed. The stall[] list is accepted as input but stall-detection heuristics are deferred.
- CronosAdapter is already production-ready (scout confirms); SG4 does not modify it.
- The runner is sequential within the work-list (no parallel node execution), consistent with HarnessExecutor's "no asyncio.create_task" design decision.
- The needs_fix to DONE bridge (R8) requires that the runner, upon receiving AgentResult.status='needs_fix' from a reviewed child task, re-enqueues the implement node in the work-list rather than treating the result as a failure. The exact mechanism (runner internal vs. worker callback) is an open design question for the architect.

## Open questions

- What is the canonical format of the delivery-workflow sentinel in the task brief? The request says "marker in task brief or metadata" but does not specify. The architect must define this to avoid ambiguity between R6 and R8.
- When Compiler A encounters an edge with no 'when' field (unconditional edge), should IREdge.when be an empty string, None, or a sentinel literal 'true'? The runner's edge evaluator must handle whichever convention is chosen.
- Does LoopPolicy.stall[] carry pre-defined string tokens that the runner checks heuristically, or are they condition expressions evaluated against scope? The delivery.workflow.yaml uses stall: [recurring_findings, no_diff_progress] without defining their evaluation semantics.
- When a back-edge loop resets downstream nodes to pending, which nodes are considered "downstream"? All transitive successors of the loop-back target, or only direct successors?

## Next consumer brief

Design agent priorities for sg4-executor-shared-ir-compiler-a-runner:

Read traceability[] first — it is the ground truth for all 10 requirements. has_ui=false; no frontend work.

Key design decisions not derivable from requirements:

1. IR module layout — decide whether IRNode/IREdge/IRGraph/LoopPolicy live in a single ir.py or split across ir/types.py and ir/graph.py. Either is fine; pick one for the importlinter to gate on.

2. Compiler A entry point — confirm the function signature: compile(spec_dict: dict) -> IRGraph (sync, no I/O). Specify how it handles missing defaults.models entries (raise vs. passthrough).

3. Runner work-list architecture — the request mandates a fixpoint work-list walker (not topo-sort). The key design decision is how back-edges are represented: as separate IREdge entries with a back_edge flag, or detected at runtime by comparing target node attempt vs. current attempt. The architect must settle this before the implementor can write the loop counter logic (R3).

4. R8 bridge mechanism — two candidate designs: (a) runner-internal: AgentResult.status='needs_fix' is treated as a special loop trigger that re-enqueues the edge's target node; (b) worker-external: the worker post-task callback detects the delivery-node sentinel and manually re-seeds the runner's work-list. Design (a) is cleaner and keeps the boundary clean.

5. Worker integration touchpoint — R6 requires detecting the delivery-workflow sentinel in _run_goal or its caller. Confirm whether this is a new branch inside RunExecutor.run_goal() or a pre-dispatch check in Worker._process_task().

6. Test strategy — NullRuntime is the primary isolation harness. Integration tests with CronosAdapter should use monkeypatched store + trace_store (pattern from CronosAdapter docstring DD-11). Specify which test files go in packages/delivery-workflow/tests/ vs. backend/tests/.
