---
cc_version: '1.0'
agent: pipeline-analyst
slug: sg5-retarget-harnessexecutor-onto-the-ru
phase: analysis
status: done
confidence: 0.88
inputs_used:
- .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/scout-report-sg5-retarget-harnessexecutor-onto-the-ru.md
- backend/app/harnesses/model.py
- backend/app/harnesses/run_state.py
- backend/app/harnesses/executor.py
- backend/app/harnesses/adapter.py
- backend/app/run_executor.py
- packages/delivery-workflow/ir.py
- packages/delivery-workflow/interface.py
- packages/delivery-workflow/state_types.py
- packages/delivery-workflow/adapters/cronos/adapter.py
- packages/delivery-workflow/runner/core.py
- packages/delivery-workflow/.importlinter
- backend/app/pipeline/CONTRACT.md
outputs_produced:
- .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/analysis-report-sg5-retarget-harnessexecutor-onto-the-ru.md
blockers: []
next_consumer: design
request: "Spec 5 — Retarget HarnessExecutor onto the runner\n\nThe unification. End-state:\
  \ HarnessExecutor.execute = load harness → Compiler B → runner.run(ir, CronosAdapter).\
  \ The runner is the substrate; the Harness visual editor becomes a consumer.\n\n\
  ### 5.1 Compiler B — Harness → IR (Cronos-side)\n\nInput: Harness (backend/app/harnesses/model.py).\
  \ Map:\n- HarnessNode.type → IRNode.kind (1:1 mapping)\n- HarnessEdge{source:NodeRef,\
  \ target:NodeRef, condition} → IREdge{source.node_id, target.node_id, when=condition,\
  \ port=(source.port_id,target.port_id)}\n- node.data.loop → IRNode.loop\n\nBoundary:\
  \ Compiler B imports the Harness model → lives in backend/app/harnesses/, NOT the\
  \ package. IR types are the shared currency in the package. .importlinter stays\
  \ green.\n\n### 5.2 Runtime-state reconciliation\n\nHarnessExecutor persists runs\
  \ as RunState (harnesses/run_state.py); portable runner uses WorkflowState (package).\
  \ Pick WorkflowState (app-free). Provide RunState→WorkflowState mapping in Cronos\
  \ driver. Drain in-flight harness runs before cutover OR ship one-shot migration.\n\
  \n### 5.3 Migration (parity-gated)\n\n1. (prereq) SG4 shipped — runner walks the\
  \ IR, full harvest, proven on delivery\n2. Compiler B; unit-test every .cronos/harnesses/*.yml\
  \ fixture compiles to valid IR\n3. PARITY HARNESS (the gate): run representative\
  \ harnesses through both old BFS and runner(Compiler_B(harness)); assert identical\
  \ RunStateâ\x86\x94WorkflowState, event stream, and outcome. Cover: human-wait park/resume\
  \ AND any/all aggregator\n4. Events op reconciliation: runner emits via events op;\
  \ CronosAdapter forwards to bus (replaces _publish)\n5. Adapter reconciliation:\
  \ HarnessExecutor WorkerProtocol (run_agent/finalize_child/_publish) maps onto ExecutorInterface.\
  \ CronosAdapter.dispatchAgent already creates+polls child tasks — reconciliation,\
  \ not new behaviour\n6. Cut over behind CRONOS_HARNESS_RUNNER; parity/shadow in\
  \ prod; remove old BFS\n\n### 5.4 No-regression argument\n\nExisting harnesses are\
  \ acyclic (current executor rejects cycles via _topo_sort). Dropping cycle-rejection\
  \ ONLY ADDS capability — no regression by construction.\n\n### References\n- backend/app/harnesses/executor.py\
  \ — HarnessExecutor to retarget\n- backend/app/harnesses/model.py — Harness, HarnessNode,\
  \ HarnessEdge types (Compiler B input)\n- backend/app/harnesses/run_state.py — RunState\
  \ (to reconcile with WorkflowState)\n- packages/delivery-workflow/ — runner (SG4),\
  \ WorkflowState, ExecutorInterface\n- .cronos/harnesses/*.yml — existing harness\
  \ fixtures to test Compiler B"
has_ui: false
coverage_summary:
  searched:
  - backend/app/harnesses/
  - backend/app/run_executor.py
  - packages/delivery-workflow/
  - packages/delivery-workflow/.importlinter
  - .cronos/harnesses/
  excluded:
  - frontend/: harness visualization is a consumer of the runner, not part of unification
  - deploy/: not relevant to execution architecture
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
  - traceability_mapping
traceability:
- requirement_id: R1
  statement: 'Compiler B (backend/app/harnesses/compiler.py) maps a Harness instance
    to an IRGraph with 1:1 node kind, edge, and variable mappings: HarnessNode.type->IRNode.kind
    (5 types, wait disambiguated by mode), HarnessEdge->IREdge (source.node_id, target.node_id,
    when=condition or '''', port=source.port_id), Harness.variables->IRGraph.variables,
    Harness.name/description->IRGraph.metadata.'
  acceptance_criteria:
  - Given a Harness with nodes of types agent, trigger, decision, wait, aggregator
    and edges with and without conditions, when compile(harness) is called, then the
    returned IRGraph has one IRNode per HarnessNode with matching id and kind, one
    IREdge per HarnessEdge with source=edge.source.node_id, target=edge.target.node_id,
    when=edge.condition or '', and port=edge.source.port_id.
  - 'Given a Harness with variables={k: v}, when compile(harness) is called, then
    IRGraph.variables == {k: v} and IRGraph.metadata contains ''name'' and ''description''
    from the Harness.'
  - Given a Harness with no edges, when compile(harness) is called, then IRGraph.edges
    == [] and all nodes are present.
  verifying_phase: test
  confidence: 0.92
- requirement_id: R2
  statement: 'Compiler B disambiguates Wait node IR kind based on data.mode: HarnessNode.type=''wait''
    with data.mode=''human'' compiles to IRNode.kind=''human''; data.mode=''timed''
    compiles to IRNode.kind=''wait''; absent mode defaults to ''wait'' with a logged
    warning.'
  acceptance_criteria:
  - 'Given a wait node with data={''mode'': ''human''}, when compiled, then IRNode.kind
    == ''human''.'
  - 'Given a wait node with data={''mode'': ''timed''}, when compiled, then IRNode.kind
    == ''wait''.'
  - Given a wait node with no mode field, when compiled, then IRNode.kind == 'wait'
    and a warning is logged.
  verifying_phase: test
  confidence: 0.85
- requirement_id: R3
  statement: 'Compiler B constructs a LoopPolicy from a HarnessNode''s data.loop sub-object
    when present: loop.until, loop.stall, loop.max (default 10 per Harness semantics,
    not IR default 5), and loop.on_exhaust map to LoopPolicy fields; IRNode.loop is
    None when data.loop is absent.'
  acceptance_criteria:
  - 'Given a HarnessNode with data={''loop'': {''until'': ''cond'', ''stall'': [''recurring_findings''],
    ''max'': 8, ''on_exhaust'': ''escalate''}}, when compiled, then IRNode.loop ==
    LoopPolicy(until=''cond'', stall=[''recurring_findings''], max=8, on_exhaust=''escalate'').'
  - 'Given a HarnessNode with data={''loop'': {''until'': ''cond''}} and no max field,
    when compiled, then IRNode.loop.max == 10.'
  - Given a HarnessNode with no loop key in data, when compiled, then IRNode.loop
    is None.
  verifying_phase: test
  confidence: 0.87
- requirement_id: R4
  statement: Compiler B successfully compiles all 10 YAML harness fixtures from .cronos/harnesses/*.yml
    to IRGraph instances that satisfy IRGraph structural invariants (valid node kinds,
    all IREdge source/target reference existing node ids, entry_nodes non-empty for
    connected graphs).
  acceptance_criteria:
  - Given each of the 10 YAML files in .cronos/harnesses/, when loaded as Harness
    and passed to compile(), then no exception is raised and the returned IRGraph
    has all IRNode.kind values in the allowed literal set.
  - Given any fixture with at least one edge, when compiled, then all IREdge.source
    and IREdge.target values match ids present in IRGraph.nodes.
  - Given any fixture with at least one edge, when compiled, then IRGraph.entry_nodes
    is non-empty.
  verifying_phase: test
  confidence: 0.82
- requirement_id: R5
  statement: 'A RunState-to-WorkflowState mapping function converts RunState snapshots
    to WorkflowState for runner initialisation: RunState.status ''cancelled'' maps
    to WorkflowState.status ''blocked'', ''in_progress'' node status maps to ''pending'',
    loop bookkeeping (attempt, prior_finding_ids) is preserved in WorkflowState.nodes[id].attempt
    and .fields, and waiting_node_id is represented by resetting that node''s WorkflowState
    status to ''pending''.'
  acceptance_criteria:
  - Given a RunState with status='cancelled', when mapped to WorkflowState, then WorkflowState.status
    == 'blocked'.
  - Given a RunState with nodes_executed[id].status='in_progress', when mapped, then
    WorkflowState.nodes[id].status == 'pending'.
  - Given a RunState with nodes_executed[id].attempt=3 and prior_finding_ids=['f1','f2'],
    when mapped, then WorkflowState.nodes[id].attempt == 3 and WorkflowState.nodes[id].fields['prior_finding_ids']
    == ['f1','f2'].
  - Given a RunState with waiting_node_id='node-42', when mapped, then WorkflowState.nodes['node-42'].status
    == 'pending' so the runner re-executes from that node.
  verifying_phase: test
  confidence: 0.8
- requirement_id: R6
  statement: 'A HarnessExecutorAdapter class in backend/app/harnesses/ implements
    ExecutorInterface: dispatchAgent maps agent_ref+inputs to WorkerAdapter.run_agent
    then finalize_child; evalCondition delegates to harnesses.decision.eval_condition;
    escalate transitions the run goal to TaskState.WAITING and sets WorkflowState.status=''blocked'';
    state ops wrap atomic RunState/WorkflowState persistence; telemetry.emit forwards
    to worker._bus.publish.'
  acceptance_criteria:
  - Given a HarnessExecutorAdapter wired to a stubbed WorkerAdapter, when dispatchAgent('agent-a',
    inputs) is called, then WorkerAdapter.run_agent is called with a child task id
    and WorkerAdapter.finalize_child is called with the resulting RunTrace.
  - 'Given HarnessExecutorAdapter.evalCondition(''x == y'', {''x'': ''y''}), when
    called, then it returns True without raising.'
  - Given HarnessExecutorAdapter.escalate('node-1', 'loop exhausted'), when called,
    then the run goal task is transitioned to TaskState.WAITING with waiting_question='loop
    exhausted' and state.status becomes 'blocked'.
  - 'Given telemetry.emit(''node-1'', {''tokens'': 100.0}), when called, then worker._bus.publish
    is called with an event payload containing node_id and data.'
  verifying_phase: test
  confidence: 0.82
- requirement_id: R7
  statement: HarnessExecutorAdapter.telemetry.emit events are forwarded to the existing
    SSE bus via worker._bus.publish using the existing event schema (node_transition,
    edge_chosen, run_status event types) so that HarnessRunPanel live updates continue
    to function without any frontend change.
  acceptance_criteria:
  - Given a runner run that transitions a node, when telemetry.emit is called by the
    runner, then worker._bus.publish receives an event dict with at minimum 'type'
    and 'node_id' fields consistent with the existing schema.
  - Given a run_status event published when the run completes, when received by a
    frontend SSE subscriber, then no frontend file modifications are required to display
    it correctly.
  verifying_phase: test
  confidence: 0.78
- requirement_id: R8
  statement: 'Human-wait park and resume is handled via HarnessExecutorAdapter.escalate():
    on human Wait node dispatch, escalate is called with the wait node id and waiting_question,
    sets RunState.waiting_node_id, and transitions the run goal to TaskState.WAITING;
    on resume, the driver initialises WorkflowState from RunState with the wait node
    reset to pending so the runner traverses its outgoing edges.'
  acceptance_criteria:
  - Given a harness with a Wait(human) node, when executed via runner+HarnessExecutorAdapter,
    then escalate('wait-node-id', question) is called, the run goal transitions to
    TaskState.WAITING, and RunState.waiting_node_id == 'wait-node-id'.
  - Given a resumed run where RunState.waiting_node_id == 'wait-node-id', when the
    WorkflowState is initialised from RunState, then WorkflowState.nodes['wait-node-id'].status
    == 'pending'.
  - Given the resumed runner.run, when it completes successfully, then the run goal
    transitions to TaskState.DONE and RunState.waiting_node_id is cleared.
  verifying_phase: test
  confidence: 0.8
- requirement_id: R9
  statement: A parity test suite runs representative harnesses through both old BFS
    HarnessExecutor and new runner(CompilerB, HarnessExecutorAdapter) and asserts
    identical final verdict (done/failed), equivalent event streams (same node_transition
    events covering same node ids), and identical behaviour for human-wait park/resume
    and any/all aggregator node types.
  acceptance_criteria:
  - Given a trigger+agent harness, when run through both BFS and runner paths, then
    final status is identical and node_transition events cover the same node ids.
  - Given a decision+aggregator(all) harness where one predecessor fails, when run
    through both paths, then both produce final status 'failed'.
  - Given a decision+aggregator(any) harness where one predecessor succeeds, when
    run through both paths, then both produce final status 'done'.
  - Given a human-wait harness on initial run, when run through both paths, then both
    park at the wait node; when resumed, both produce final status 'done'.
  verifying_phase: test
  confidence: 0.83
- requirement_id: R10
  statement: 'A CRONOS_HARNESS_RUNNER environment variable (truthy when ''1'') gates
    the execution path in run_executor.py: when unset or ''0'', the existing BFS HarnessExecutor
    path executes; when ''1'', the Compiler B + runner path executes; both paths produce
    a result compatible with the goal finalisation logic (waiting_node_id or None,
    terminal status).'
  acceptance_criteria:
  - Given CRONOS_HARNESS_RUNNER unset, when execute_harness_run_body is called, then
    HarnessExecutor.execute (BFS) is invoked.
  - Given CRONOS_HARNESS_RUNNER=1, when execute_harness_run_body is called, then compiler.compile
    and runner.run are invoked instead.
  - Given the same harness with both flag values, when run on fresh start, then goal
    finalisation (DONE or WAITING) is identical.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R11
  statement: 'run_executor.py execute_harness_run_body is refactored so the CRONOS_HARNESS_RUNNER=1
    path calls: (1) harness_store.get to load Harness, (2) compiler.compile(harness)
    to obtain IRGraph, (3) HarnessExecutorAdapter(worker, run_goal_id) to construct
    the adapter, (4) runner.run(ir_graph, adapter) to execute, (5) maps returned WorkflowState
    to finalise the goal task (DONE or WAITING with waiting_question).'
  acceptance_criteria:
  - Given CRONOS_HARNESS_RUNNER=1 and a harness loaded from harness_store, when execute_harness_run_body
    runs, then compiler.compile is called exactly once with that Harness.
  - Given a successful runner.run returning WorkflowState(status='done'), when processed,
    then store.finalize_run is called with new_state=TaskState.DONE.
  - Given runner.run returning WorkflowState(status='blocked'), when processed, then
    store.finalize_run is called with new_state=TaskState.WAITING and waiting_question
    is populated from the blocked node's reason.
  verifying_phase: test
  confidence: 0.85
- requirement_id: R12
  statement: When CRONOS_HARNESS_RUNNER=1, the old BFS HarnessExecutor code path in
    run_executor.py is bypassed (not invoked) but not deleted; HarnessExecutor remains
    importable and its existing test suite passes in both flag states.
  acceptance_criteria:
  - Given CRONOS_HARNESS_RUNNER=1, when execute_harness_run_body is called, then HarnessExecutor.execute
    is not called.
  - Given CRONOS_HARNESS_RUNNER unset, when execute_harness_run_body is called, then
    compiler.compile is not called.
  - The 20 existing test_harness*.py files collect and pass with CRONOS_HARNESS_RUNNER
    unset and with CRONOS_HARNESS_RUNNER=1.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R13
  statement: Compiler B (backend/app/harnesses/compiler.py) imports only from backend/app/harnesses/model.py
    and packages/delivery-workflow/ir.py; it contains no import from runner/, lib/,
    adapters/, or any other app.* path, preserving the .importlinter no-app-imports
    boundary for the portable package core.
  acceptance_criteria:
  - 'Given the .importlinter configuration (source_modules: lib, runner; forbidden_modules:
    app, backend), when lint-imports is run after adding compiler.py, then it exits
    0 with no violations.'
  - Given compiler.py, when its imports are inspected, then no import path begins
    with 'runner', 'lib', 'adapters', or 'app' beyond the harnesses package itself.
  verifying_phase: test
  confidence: 0.93
- requirement_id: R14
  statement: All 20 existing test_harness*.py test files pass without modification
    in both CRONOS_HARNESS_RUNNER=0 (default) and CRONOS_HARNESS_RUNNER=1 states,
    and the backend test suite continues to meet the >=60% coverage floor.
  acceptance_criteria:
  - Given the full backend pytest suite with CRONOS_HARNESS_RUNNER unset, when all
    20 test_harness*.py files are collected and run, then all pass and overall coverage
    >= 60%.
  - Given the full backend pytest suite with CRONOS_HARNESS_RUNNER=1, when the same
    20 files are collected and run, then all pass and coverage >= 60%.
  - No existing test_harness*.py file is modified as part of this SG implementation.
  verifying_phase: test
  confidence: 0.88
metrics:
  tool_calls: 14
  files_read: 13
  memory_hits: 0
---

## Summary

SG5 unifies the HarnessExecutor (a 1440-LOC BFS harness interpreter) onto the portable delivery-workflow runner from SG4. The end-state is a three-step pipeline in run_executor.py: load Harness from store, compile to IRGraph via Compiler B, execute via runner.run(ir, HarnessExecutorAdapter). Compiler B is a pure Harness-to-IRGraph function in backend/app/harnesses/ that preserves the .importlinter boundary. The impedance mismatch between RunState (Cronos-native, atomic JSON) and WorkflowState (runner-native, in-memory dataclass) is resolved by a bidirectional mapping layer in the Cronos driver. Cutover is gated behind CRONOS_HARNESS_RUNNER and guarded by a parity test asserting behavioural equivalence of the old BFS path and the new runner path across all node types including human-wait and aggregator.

## Scope

### In scope
- Compiler B: pure function Harness→IRGraph in backend/app/harnesses/compiler.py
- Wait node kind disambiguation (mode='human'→IRNode.kind='human', mode='timed'→'wait')
- LoopPolicy construction from HarnessNode.data.loop (default max=10 per Harness semantics)
- IRGraph variable and metadata pass-through from Harness
- RunState→WorkflowState bidirectional mapping in the Cronos driver
- HarnessExecutorAdapter implementing ExecutorInterface (dispatchAgent, evalCondition, escalate, state ops, telemetry ops)
- Events op reconciliation: runner telemetry.emit forwarded to worker._bus.publish
- Human-wait park via escalate() with waiting_node_id routing; resume re-enters runner from waiting node
- Parity test covering trigger+agent, decision+aggregator(any/all), human-wait park/resume
- CRONOS_HARNESS_RUNNER feature flag in run_executor.py
- Fixture compilation tests for all 10 .cronos/harnesses/*.yml YAML files
- No-regression: all 20 existing test_harness*.py files pass in both flag states
- .importlinter boundary preservation

### Out of scope
- Frontend harness editor changes (remains a Harness-model consumer; no IR exposure)
- Compiler A (delivery-workflow spec→IR pipeline); Compiler B is Cronos-side only
- Removing the BFS HarnessExecutor before production parity is confirmed
- New harness YAML fixture backfill for decision/aggregator/wait/loop diversity
- The existing CronosAdapter in packages/delivery-workflow/adapters/cronos/adapter.py is unchanged

### Deferred
- Hard deletion of BFS HarnessExecutor code after flag is permanently flipped in production
- New harness YAML fixtures covering decision, aggregator, wait(human+timed), loop for richer acceptance testing
- Shadow-mode dual-run logging for production parity monitoring beyond the feature flag

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | Compiler B maps Harness nodes, edges, variables, and metadata to IRGraph with 1:1 structural fidelity |
| R2 | Wait node kind disambiguation: mode='human'→IRNode.kind='human', mode='timed'→'wait' |
| R3 | LoopPolicy constructed from data.loop with Harness default max=10 (not IR default 5) |
| R4 | All 10 .cronos/harnesses/*.yml fixtures compile to valid IRGraph without exception |
| R5 | RunState→WorkflowState mapping preserves loop bookkeeping, wait routing, and cancelled→blocked |
| R6 | HarnessExecutorAdapter implements ExecutorInterface: dispatchAgent, evalCondition, escalate, state, telemetry |
| R7 | Events op reconciliation: runner telemetry.emit forwarded to worker._bus.publish with existing schema |
| R8 | Human-wait park via escalate() sets waiting_node_id; resume re-enters runner from waiting node |
| R9 | Parity test asserts identical verdict, event stream, and outcome vs old BFS across all node types |
| R10 | CRONOS_HARNESS_RUNNER env flag gates BFS vs runner path in run_executor.py |
| R11 | execute_harness_run_body refactored: flag=1 path calls compile→runner.run→goal finalise |
| R12 | Old BFS code path bypassed (not deleted) when flag=1; both paths pass existing tests |
| R13 | Compiler B imports only harnesses/model.py + ir.py; .importlinter exits 0 |
| R14 | All 20 existing test_harness*.py files pass unchanged in both flag states; coverage >=60% |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). The body summary below mirrors them in compact form for the human reader.

- R1 — compile(harness) returns one IRNode per HarnessNode (matching id/kind) and one IREdge per HarnessEdge (source.node_id, target.node_id, when=condition or '', port=source.port_id); variables and metadata pass through
- R2 — wait+mode='human'→kind='human'; wait+mode='timed'→kind='wait'; missing mode→'wait' with warning
- R3 — data.loop maps to LoopPolicy; absent loop→None; absent max in data.loop→LoopPolicy.max=10
- R4 — all 10 YAML fixtures compile without exception; all IREdge references valid node ids; entry_nodes non-empty for connected graphs
- R5 — 'cancelled'→'blocked'; 'in_progress'→'pending'; attempt and prior_finding_ids preserved; waiting_node_id resets target node to pending
- R6 — dispatchAgent calls run_agent+finalize_child; evalCondition delegates to decision.eval_condition; escalate→WAITING+blocked; telemetry→_bus.publish
- R7 — telemetry.emit produces event with 'type' and 'node_id' matching existing schema; no frontend changes required
- R8 — Wait(human): escalate sets waiting_node_id; resume init WorkflowState with wait node pending; final state clears waiting_node_id
- R9 — trigger+agent, decision+aggregator(all/any), human-wait park+resume produce identical verdict and equivalent event streams on both paths
- R10 — unset→BFS; CRONOS_HARNESS_RUNNER=1→compile+runner; same finalisation outcome for same harness
- R11 — flag=1: compile called once; done→DONE; blocked→WAITING with waiting_question
- R12 — HarnessExecutor.execute not called when flag=1; compiler.compile not called when flag unset; existing tests pass both ways
- R13 — no forbidden imports in compiler.py; lint-imports exits 0
- R14 — 20 test_harness*.py files pass unchanged; coverage >=60% in both flag states

## Traceability

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | Compiler B maps Harness nodes, edges, variables, and metadata to IRGraph with 1:1 structural fidelity |
| R2 | test | Wait node kind disambiguation: mode='human'->IRNode.kind='human', mode='timed'->'wait' |
| R3 | test | LoopPolicy constructed from data.loop with Harness default max=10 (not IR default 5) |
| R4 | test | All 10 .cronos/harnesses/*.yml fixtures compile to valid IRGraph without exception |
| R5 | test | RunState->WorkflowState mapping preserves loop bookkeeping, wait routing, and cancelled->blocked |
| R6 | test | HarnessExecutorAdapter implements ExecutorInterface: dispatchAgent, evalCondition, escalate, state, telemetry |
| R7 | test | Events op reconciliation: runner telemetry.emit forwarded to worker._bus.publish with existing schema |
| R8 | test | Human-wait park via escalate() sets waiting_node_id; resume re-enters runner from waiting node |
| R9 | test | Parity test asserts identical verdict, event stream, and outcome vs old BFS across all node types |
| R10 | test | CRONOS_HARNESS_RUNNER env flag gates BFS vs runner path in run_executor.py |
| R11 | test | execute_harness_run_body refactored: flag=1 path calls compile->runner.run->goal finalise |
| R12 | test | Old BFS code path bypassed (not deleted) when flag=1; both paths pass existing tests |
| R13 | test | Compiler B imports only harnesses/model.py + ir.py; .importlinter exits 0 |
| R14 | test | All 20 existing test_harness*.py files pass unchanged in both flag states; coverage >=60% |

## Assumptions

- has_ui=false rationale: The request is a pure backend execution-layer unification. Compiler B, RunState mapping, HarnessExecutorAdapter, feature flag, and runner.run invocation all live in backend/app/harnesses/ and run_executor.py. The frontend harness editor is explicitly a downstream consumer; no frontend changes are required.
- Wait node kind disambiguation is resolved: IRNode.kind has both 'human' and 'wait' as legal literals (confirmed in ir.py); the runner dispatches on kind. Compiler B must inspect data.mode for wait nodes to select the correct kind.
- LoopPolicy.max default divergence: model.py line 96 states Harness default max=10; ir.py line 39 defines LoopPolicy default max=5. Compiler B must explicitly set max=10 when data.loop.max is absent rather than relying on LoopPolicy's Python dataclass default.
- The existing CronosAdapter (packages/delivery-workflow/adapters/cronos/adapter.py) is unchanged. The new HarnessExecutorAdapter is a separate Cronos-side adapter in backend/app/harnesses/ that bridges WorkerProtocol to ExecutorInterface. These serve different runners (delivery pipeline vs harness execution).
- RunState.waiting_node_id must survive the WorkflowState round-trip. The runner has no native waiting_node_id concept; the mapping layer encodes it as a node-status reset in WorkflowState so the runner re-executes from that node on resume.
- Parity tests use in-process fake WorkerAdapter stubs; they do not spawn real Claude Code CLI processes. The parity scope is executor control-flow logic, not agent execution fidelity.
- In-flight harness runs at flag-flip time: the flag should gate only initial execution starts, not resume paths (resume always uses the persisted RunState path that started the run). This defers the in-flight migration problem to a follow-up goal.

## Open questions

- OQ-1: IREdge.port encoding — the spec says port=(source.port_id, target.port_id) but IREdge.port is str|None. Should Compiler B encode both as "source_port:target_port" or just source_port_id? The runner ignores port (visualization-only hint); recommend encoding only source_port_id.
- OQ-2: In-flight run resume policy — for runs parked at TaskState.WAITING when CRONOS_HARNESS_RUNNER is flipped, should resume use the old BFS path (flag-insensitive resume) or migrate RunState to WorkflowState on-the-fly? Recommend: flag only affects initial starts; resume always follows the path used at run creation time.
- OQ-3: Parity harness fixture strategy — the 10 existing YAML fixtures lack decision/aggregator/wait/loop diversity. Should the parity test construct synthetic Harness objects in-process or backfill .cronos/harnesses/ YAMLs? The design agent must decide.

## Next consumer brief

Design agent: read traceability[] as the full requirement ground truth. Key decision points:

1. Compiler B module (R1, R2, R3, R13): lives at backend/app/harnesses/compiler.py. May import Harness from .model and IR types from packages/delivery-workflow/ir.py. The .importlinter no-app-imports rule applies to lib/ and runner/ only — compiler.py is inside app/ which is exempt. Verify the import path to ir.py is on sys.path in the backend Docker image.

2. HarnessExecutorAdapter (R6, R7, R8): This is NOT the existing CronosAdapter in the delivery-workflow package. It is a new class in backend/app/harnesses/ that adapts WorkerProtocol (run_agent, finalize_child, _publish) to ExecutorInterface (dispatchAgent, evalCondition, escalate, state, telemetry). dispatchAgent reuses WorkerAdapter.run_agent+finalize_child; escalate sets RunState.waiting_node_id + WorkflowState.status='blocked' atomically. This is the highest implementation risk area (scout Risk R1).

3. RunState<->WorkflowState mapping (R5): The mapping function should be a standalone helper (not inside HarnessExecutorAdapter) so it can be tested independently. Key mappings: cancelled->blocked, in_progress->pending, attempt and prior_finding_ids->fields dict, waiting_node_id->reset target node to pending.

4. Parity test design (R9, OQ-3): Parity tests are the migration gate. Synthetic Harness construction in conftest is cleaner than backfilling YAML files. Cover 4 scenarios: trigger+agent, decision+aggregator(all), decision+aggregator(any), human-wait(park+resume). Both paths must use the same fake WorkerAdapter stubs.

5. Feature flag wiring (R10, R11): CRONOS_HARNESS_RUNNER is read from os.environ in run_executor.py execute_harness_run_body. The flag check must happen after harness loading (both paths load the harness) but before execution dispatch.

6. IREdge.port (OQ-1): Recommend encoding only source.port_id as a single string. The runner ignores port; decision routing uses IREdge.when, not port.

7. In-flight resume (OQ-2): Recommend flag gates start only; resume reads the RunState path and always follows the path that created the run. Add a 'runner_version' field to RunState in a future iteration to make this explicit.
