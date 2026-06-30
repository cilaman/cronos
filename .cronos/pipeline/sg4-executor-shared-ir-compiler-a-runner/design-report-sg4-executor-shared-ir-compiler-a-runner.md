---
cc_version: '1.0'
agent: pipeline-architect
slug: sg4-executor-shared-ir-compiler-a-runner
phase: design
status: done
confidence: 0.86
inputs_used:
- memory:project_delivery_v1_cronos_adapter_design
- memory:project_pipeline_foundation_merged
- memory:project_pipeline_verifier
- memory:project_arc6_64_run_lifecycle_review
- memory:project_sg3_conditions_impl
- .cronos/pipeline/sg4-executor-shared-ir-compiler-a-runner/analysis-report-sg4-executor-shared-ir-compiler-a-runner.md
- .cronos/pipeline/sg4-executor-shared-ir-compiler-a-runner/scout-report-sg4-executor-shared-ir-compiler-a-runner.md
- packages/delivery-workflow/interface.py
- packages/delivery-workflow/state_types.py
- packages/delivery-workflow/results.py
- packages/delivery-workflow/spec_loader.py
- packages/delivery-workflow/null_runtime.py
- packages/delivery-workflow/lib/conditions.py
- packages/delivery-workflow/adapters/cronos/adapter.py
- packages/delivery-workflow/delivery.workflow.yaml
- packages/delivery-workflow/.importlinter
- packages/delivery-workflow/schemas/delivery.workflow.schema.yaml
- backend/app/harnesses/executor.py
- backend/app/worker.py
- backend/app/run_executor.py
outputs_produced:
- .cronos/pipeline/sg4-executor-shared-ir-compiler-a-runner/design-report-sg4-executor-shared-ir-compiler-a-runner.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - packages/delivery-workflow/
  - backend/app/harnesses/
  - backend/app/worker.py
  - backend/app/run_executor.py
  excluded:
  - frontend/src/: has_ui=false; backend/package-only feature
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
iterations:
- id: I1
  type: data
  scope_files:
  - packages/delivery-workflow/ir.py
  - packages/delivery-workflow/tests/test_ir_types.py
  validation_command: cd packages/delivery-workflow && pytest tests/test_ir_types.py
    -v
  max_diff_lines: 350
  depends_on: []
- id: I2
  type: backend
  scope_files:
  - packages/delivery-workflow/compiler_a.py
  - packages/delivery-workflow/tests/test_compiler_a.py
  - packages/delivery-workflow/tests/fixtures/compiler_a_minimal.yaml
  validation_command: cd packages/delivery-workflow && pytest tests/test_compiler_a.py
    -v
  max_diff_lines: 400
  depends_on:
  - I1
- id: I3
  type: backend
  scope_files:
  - packages/delivery-workflow/runner/__init__.py
  - packages/delivery-workflow/runner/core.py
  - packages/delivery-workflow/runner/scope.py
  - packages/delivery-workflow/tests/test_runner_core.py
  - packages/delivery-workflow/tests/test_runner_scope.py
  validation_command: cd packages/delivery-workflow && pytest tests/test_runner_core.py
    tests/test_runner_scope.py -v
  max_diff_lines: 600
  depends_on:
  - I1
- id: I4
  type: backend
  scope_files:
  - packages/delivery-workflow/runner/dispatch.py
  - packages/delivery-workflow/tests/test_runner_dispatch.py
  validation_command: cd packages/delivery-workflow && pytest tests/test_runner_dispatch.py
    -v
  max_diff_lines: 600
  depends_on:
  - I3
- id: I5
  type: backend
  scope_files:
  - packages/delivery-workflow/runner/loop.py
  - packages/delivery-workflow/tests/test_runner_loop.py
  validation_command: cd packages/delivery-workflow && pytest tests/test_runner_loop.py
    -v
  max_diff_lines: 400
  depends_on:
  - I1
  - I3
- id: I6
  type: backend
  scope_files:
  - backend/app/delivery_driver.py
  - backend/tests/test_delivery_driver.py
  validation_command: cd backend && pytest tests/test_delivery_driver.py -v
  max_diff_lines: 500
  depends_on:
  - I2
  - I3
  - I4
  - I5
- id: I7
  type: backend
  scope_files:
  - backend/app/worker.py
  - backend/app/run_executor.py
  - backend/tests/test_worker_delivery_routing.py
  validation_command: cd backend && pytest tests/test_worker_delivery_routing.py -v
  max_diff_lines: 400
  depends_on:
  - I6
- id: I8
  type: infra
  scope_files:
  - packages/delivery-workflow/tests/test_runner_e2e_needs_fix.py
  - backend/tests/test_delivery_e2e_needs_fix_loopback.py
  validation_command: cd packages/delivery-workflow && pytest tests/test_runner_e2e_needs_fix.py
    -v && cd .. && python -m importlinter --config packages/delivery-workflow/.importlinter
    && cd backend && pytest tests/test_delivery_e2e_needs_fix_loopback.py -v
  max_diff_lines: 500
  depends_on:
  - I4
  - I7
risks:
- description: Runner work-list walker may deadlock on a node whose loop-back target
    is itself (self-loop) or on a cycle where no edge condition ever becomes True;
    the runner could spin indefinitely incrementing attempt counters without progress.
  severity: high
  mitigation: I5 LoopPolicy.max is enforced as a hard ceiling per node; the work-list
    also enforces a global iteration cap (e.g. sum(LoopPolicy.max for all nodes) *
    2) and calls executor.escalate(node_id, 'global_iteration_cap_exceeded') if exceeded.
    I3 tests include a self-loop fixture asserting the cap fires before resource exhaustion.
- description: 'Resume semantics from a persisted WorkflowState can produce stale-scope
    bugs: when the runner resumes after a back-edge reset, downstream NodeState entries
    marked ''pending'' may still have stale artifact_paths or fields from a previous
    attempt; scope enrichment could then surface old outputs to fresh edge evaluations.'
  severity: high
  mitigation: I3 scope.py rebuilds the scope dict from scratch on each node entry
    by iterating WorkflowState.nodes, reading only entries whose status == 'done'
    AND attempt == NodeState.attempt of the predecessor's last successful run. I5
    back-edge reset explicitly zeroes artifact_paths/fields on reset nodes. Test asserted
    in test_runner_scope.py::test_resume_after_back_edge_clears_stale_scope.
- description: 'Worker routing (I7) introduces a fork in _run_goal: a regression in
    non-delivery goals would break every existing goal in production. The detection
    sentinel must not match incidentally (e.g. an HTML comment in arbitrary user briefs).'
  severity: high
  mitigation: 'Sentinel uses the strict compiled regex `^<!--\s*delivery-workflow:\s*([^\s>]+)\s*-->$`
    parsed only against full lines of the goal brief (never substring). Detection
    is in a single pure function `_detect_delivery_workflow_spec(brief: str) -> str
    | None` (R6 acceptance) testable in isolation. Worker routing test asserts (a)
    sentinel-present goals call delivery_driver and (b) non-sentinel goals call RunExecutor.run_goal
    unchanged (regression guard).'
- description: 'Child-task needs_fix to implement back-edge bridge (R8) requires the
    runner to re-enqueue the implement node when a downstream review returns AgentResult.status=''needs_fix''.
    If the bridge is implemented as a worker post-task callback (option b in analysis
    OQ), it creates a circular ownership: worker knows runner internals.'
  severity: medium
  mitigation: 'Chosen design is option (a) runner-internal — the runner''s edge-evaluation
    loop maps AgentResult.status into the scope as `{node_id}.fields.verdict` and
    `{node_id}.status`, and existing delivery.workflow.yaml edges (`when: review.fields.verdict
    == ''needs_fix'' && ...`) route back to implement naturally. The runner needs
    NO needs_fix-specific code path; the bridge falls out of generic scope enrichment
    + cyclic work-list. Child task tagging exists only for human-visible board correlation,
    not for routing. test_runner_e2e_needs_fix.py asserts the loop-back fires via
    standard edge evaluation.'
- description: 'Compiler A''s model alias resolution (`model: {use: recon}` to concrete
    string) requires defaults.models lookups; an undefined alias raises ValueError
    per Assumption #3 in analysis. If the spec defines an alias only locally on a
    node but the global defaults.models lacks the key, the compiler must produce a
    clear error pointing at the offending node id.'
  severity: medium
  mitigation: 'I2 compiler_a.compile() validates aliases up-front, gathers all unresolved
    (node_id, alias) tuples, and raises a single ValueError listing them all. Test
    `test_compiler_a.py::test_undefined_alias_lists_all_offenders` asserts the message
    format. Bare-string models (no {use: ...}) pass through verbatim.'
- description: importlinter contract (R9) currently forbids app.* imports from `lib`
    and `runner` root packages. New runner submodules must be added to the source_modules
    list explicitly; missing this would let the CI gate silently pass while runner
    internals smuggle in app.* via runner.dispatch or runner.loop.
  severity: medium
  mitigation: I3 introduces the runner subpackage with three submodules (core.py,
    scope.py, dispatch.py via I4, loop.py via I5); .importlinter remains source_modules
    = lib runner adapters (recursive). I8 validation_command explicitly runs `python
    -m importlinter --config packages/delivery-workflow/.importlinter` against the
    final tree to verify no submodule leaks. Test test_import_boundary.py grep-asserts
    no `from app` / `import app` / `from backend` / `import backend` lines in any
    runner/*.py.
- description: delivery.workflow.yaml currently lacks `decision`, `wait`, `aggregator`,
    and `trigger` node entries (only agent/gate/human ship today), but R4 mandates
    the runner support all 7 kinds. Tests for the four missing kinds must use synthetic
    IRGraph fixtures, not the production spec, or the runner will appear to pass coverage
    while actually being dead.
  severity: medium
  mitigation: I4 test_runner_dispatch.py builds IRGraph instances programmatically
    (one per node kind) and asserts the dispatch path executes via NullRuntime subclasses
    that record calls. The schema is NOT extended in SG4 — the runner accepts the
    kinds at the IR layer; spec_loader/schema additions are deferred to a follow-on.
    I1 IRNode.kind Literal['agent','gate','human','decision','wait','aggregator','trigger']
    enforces structural validation.
- description: Cancel-race guards harvested from HarnessExecutor depend on a run-state
    file on disk reloaded between work-list iterations; the delivery runner uses WorkflowState
    (in-memory) plus StateOps.read(). If StateOps.read() does not reload from persistent
    storage, the cancel-from-board signal never reaches the runner.
  severity: medium
  mitigation: I3 runner.core checks `state_ops.read().status == 'cancelled'` at the
    top of every work-list iteration (before dispatch). CronosStateOps.read() already
    calls StateStore.read() which reloads from state.json (see adapter.py:54). NullRuntime
    in tests can flip a flag between work-list ticks to assert the guard fires. Test
    test_runner_core.py::test_cancel_race_at_worklist_boundary.
metrics:
  tool_calls: 16
  files_read: 16
  memory_hits: 5
  iterations_planned: 8
---

## Summary

SG4 turns the dormant `packages/delivery-workflow/` package into a live workflow executor by adding three missing layers (IR types, Compiler A, runner) and wiring them into the Cronos worker via a new delivery driver. The runner is a cyclic work-list walker that harvests all 7 node-kind dispatch patterns from `backend/app/harnesses/executor.py` (agent/gate/human/decision/wait/aggregator/trigger), enforces per-node LoopPolicy, surfaces node outputs into a scope dict for downstream edge evaluation, and uses `lib.conditions.eval_condition` for guards. The DAG fans out into two parallel branches at layer 1 (Compiler A + runner-core), converges at I6 (Cronos driver), then I7 inserts a single-function sentinel route in the worker and I8 closes with an e2e repro of bug #3 (needs_fix loop-back fires naturally via generic scope-enrichment + cyclic edges — no needs_fix-specific code path needed). The key non-obvious tradeoff captured in the risk register: the R8 bridge is option-(a) runner-internal, not worker-external, eliminating circular ownership between worker and runner.

## Components

### Data
- `packages/delivery-workflow/ir.py` — IRNode (id, kind: Literal[7], data: dict, loop: LoopPolicy | None), IREdge (source, target, when, port), IRGraph (nodes: list[IRNode], edges: list[IREdge], variables: dict, metadata: dict, computed `entry_nodes` property = in_degree-0 node ids), LoopPolicy (until: str, stall: list[str], max: int, on_exhaust: Literal['escalate', 'stop']). All dataclasses, no app.* imports.

### Backend
- `packages/delivery-workflow/compiler_a.py` — `compile(spec_dict: dict) -> IRGraph` (sync, no I/O); resolves `model: {use: alias}` against `defaults.models`; folds `defaults.budget` into `IRGraph.metadata['budget']`; emits one IRNode per spec node, one IREdge per spec edge; raises ValueError listing all undefined aliases.
- `packages/delivery-workflow/runner/__init__.py` — exports `run(graph: IRGraph, executor: ExecutorInterface, state_ops: StateOps | None = None) -> WorkflowState`.
- `packages/delivery-workflow/runner/core.py` — cyclic work-list walker; seeds entry_nodes; per-iteration cancel-race guard (state_ops.read().status check); resume reconciliation (skip done nodes); global iteration cap; terminal state write.
- `packages/delivery-workflow/runner/scope.py` — `build_scope(state: WorkflowState, graph: IRGraph) -> dict[str, str]` rebuilt from scratch per work-list iteration; surfaces `{node_id}.fields.{key}`, `{node_id}.status`, `{node_id}.decision` for gate nodes; missing keys absent (eval_condition returns False naturally).
- `packages/delivery-workflow/runner/dispatch.py` — `dispatch_node(node: IRNode, ...) -> NodeOutcome` switches on node.kind: agent->dispatchAgent, gate->runGate, human->escalate-and-park, decision->edge-routing-only (no dispatch), wait->escalate (human) or sleep (timed), aggregator->all/any predecessor inspection from WorkflowState, trigger->immediate done.
- `packages/delivery-workflow/runner/loop.py` — `should_loop_back(node, state, executor) -> bool` evaluates LoopPolicy.until against scope; back-edge handling increments NodeState.attempt and zeroes transitive-successor NodeState fields; LoopPolicy.max enforcement calls escalate when exhausted.
- `backend/app/delivery_driver.py` — `async def run_delivery_goal(goal_id: str, spec_path: str, store, trace_store, space_id, run_dir) -> None`: calls `spec_loader.load_spec(spec_path)` → `compiler_a.compile(spec)` → constructs CronosAdapter → `runner.run(graph, adapter)`; catches runner exceptions and parks goal to WAITING with waiting_question. Tags child-task briefs with `<!-- delivery-node: {node_id} -->` (R8).
- `backend/app/worker.py` / `backend/app/run_executor.py` — `_detect_delivery_workflow_spec(brief: str) -> str | None` (strict regex; pure; unit-testable) inserted into `RunExecutor.run_goal` as a pre-dispatch branch; if sentinel present, delegates to `delivery_driver.run_delivery_goal` instead of `_topo_children_local`; non-sentinel path unchanged.

## Implementation plan

| ID  | Type     | Depends on    | Scope files (abridged)                                                 | Validation                                                                                          |
|-----|----------|---------------|------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------|
| I1  | data     | -             | packages/delivery-workflow/ir.py, tests/test_ir_types.py               | cd packages/delivery-workflow && pytest tests/test_ir_types.py -v                                   |
| I2  | backend  | I1            | packages/delivery-workflow/compiler_a.py, tests/test_compiler_a.py     | cd packages/delivery-workflow && pytest tests/test_compiler_a.py -v                                 |
| I3  | backend  | I1            | runner/{__init__,core,scope}.py, tests/test_runner_core.py, …scope.py  | cd packages/delivery-workflow && pytest tests/test_runner_core.py tests/test_runner_scope.py -v     |
| I4  | backend  | I3            | runner/dispatch.py, tests/test_runner_dispatch.py                      | cd packages/delivery-workflow && pytest tests/test_runner_dispatch.py -v                            |
| I5  | backend  | I1, I3        | runner/loop.py, tests/test_runner_loop.py                              | cd packages/delivery-workflow && pytest tests/test_runner_loop.py -v                                |
| I6  | backend  | I2, I3, I4, I5| backend/app/delivery_driver.py, backend/tests/test_delivery_driver.py  | cd backend && pytest tests/test_delivery_driver.py -v                                               |
| I7  | backend  | I6            | backend/app/worker.py, run_executor.py, tests/test_worker_delivery_…  | cd backend && pytest tests/test_worker_delivery_routing.py -v                                       |
| I8  | infra    | I4, I7        | tests/test_runner_e2e_needs_fix.py, tests/test_delivery_e2e_…loopback | full chain: pytest + importlinter + backend e2e (see iterations[].validation_command)               |

DAG layers (Kahn's algorithm groups for parallel implementor fan-out):
- Layer 0: I1
- Layer 1: I2, I3 (parallel)
- Layer 2: I4, I5 (parallel; both unblocked once I3 done — I5 also needs I1 which is older)
- Layer 3: I6
- Layer 4: I7
- Layer 5: I8

## Risks

| Risk                                                                                                  | Severity | Mitigation                                                                                                                  |
|-------------------------------------------------------------------------------------------------------|----------|-----------------------------------------------------------------------------------------------------------------------------|
| Runner work-list could spin on self-loop or never-True edge condition.                                | high     | LoopPolicy.max + global iteration cap + escalate; self-loop fixture in I3 test asserts cap fires.                          |
| Stale-scope bug after back-edge reset; pending NodeState may surface old fields/artifact_paths.       | high     | Rebuild scope per iteration from `status=done` nodes only; back-edge reset zeroes downstream NodeState fields explicitly.   |
| Worker routing fork could regress every non-delivery goal in production if sentinel false-matches.    | high     | Strict line-anchored regex; isolated pure detection fn; regression test asserts non-sentinel path unchanged.                 |
| needs_fix to implement bridge mis-designed as worker-external creates circular ownership.             | medium   | Runner-internal option (a): generic scope enrichment + cyclic edges; no needs_fix-specific code path; child tagging is UI-only. |
| Compiler A model alias resolution error must point at offending node id.                              | medium   | I2 collects all unresolved aliases and raises a single ValueError listing each (node_id, alias) tuple.                       |
| importlinter could silently pass while runner submodules leak app.* imports.                          | medium   | `source_modules = lib runner adapters` is recursive; I8 explicitly invokes importlinter; grep-test asserts no app/backend imports. |
| 4 of 7 node kinds (decision/wait/aggregator/trigger) absent from production spec; tests must use synthetic fixtures. | medium   | I4 builds IRGraphs programmatically per kind; spec_loader/schema unchanged in SG4; deferred to follow-on.                    |
| Cancel-race guards require StateOps.read() to reload from persistent storage, not return in-memory cache. | medium   | CronosStateOps.read() already calls StateStore.read() (verified in adapter.py:54); NullRuntime test flips a flag mid-walk.   |

## Assumptions

- IR module layout: single `packages/delivery-workflow/ir.py` (not split into `ir/types.py` + `ir/graph.py`). Justification: 4 dataclasses + 1 computed property fits comfortably in <300 lines; one file makes the importlinter target obvious and avoids `from ir import IRNode, IREdge, …` churn on every consumer.
- IRGraph.entry_nodes = nodes with in_degree == 0 (no incoming edges). Aligns with the analysis report Assumption #2 and request §4.3 ("entry from trigger/root nodes").
- IREdge.when uses empty string `""` for unconditional edges (matches the YAML where `when:` is absent). Runner's edge evaluator treats `""` as True (no condition).
- LoopPolicy.stall[] is accepted verbatim as input but stall-detection heuristics (`recurring_findings`, `no_diff_progress`) are deferred — runner stores the list on NodeState but does not evaluate it. Analysis report deferred-scope item.
- Delivery-workflow sentinel format: `<!-- delivery-workflow: {spec_path} -->` on its own line in the goal brief. {spec_path} is resolved relative to the space root.
- Child-task delivery-node sentinel: `<!-- delivery-node: {node_id} -->` appended to the brief in CronosAdapter.dispatchAgent (or via a new helper called by the runner before dispatch). Used for board correlation; the runner does NOT depend on it for routing — routing is via the runner's internal NodeState attempt counter + cyclic IRGraph edges.
- Worker integration touchpoint: pre-dispatch branch inside `RunExecutor.run_goal` (around line 635, before `_topo_children_local(goal_id, self.store)` call). Keeps the worker entry surface unchanged.
- `defaults.budget.usd_ceiling` folded into `IRGraph.metadata['budget']['usd_ceiling']` verbatim; CronosAdapter reads it via constructor parameter (driver wires it through).
- Sequential dispatch within the work-list (no asyncio.create_task fan-out per node). Matches HarnessExecutor's documented design decision and analysis report Assumption #7.

## Open questions

- The delivery-workflow sentinel format above is an assumption; the architect's choice. If user testing later shows a different convention is preferred (e.g. a structured Task.metadata field rather than brief comment), I7 can switch to that with minimal blast radius because detection is a single pure function.
- LoopPolicy.stall[] semantics are deferred. When stall-analysis is later implemented, the runner will need to inspect AgentResult.fields history; the I3 design already stores per-attempt outputs on NodeState (via WorkflowState.nodes mutation in StateOps.write), so the data is available.
- IREdge.port (request §4.1: "ports are metadata only") — kept on IREdge as `port: str | None = None` but the runner ignores it. Reserved for future visualizer use.

## Next consumer brief

Implementor entry points (read in this order):
1. `iterations[]` — your assignment per implementor invocation; `scope_files` is a hard diff boundary; `validation_command` is the verbatim shell command the tester will run.
2. `risks[]` — read mitigations for the iteration you are working; each mitigation names the specific test that must exist.
3. `## Components` for the iteration's module purpose; `## Assumptions` for design decisions not in the YAML.

Cross-iteration invariants that the YAML cannot express:
- Scope key naming convention is **load-bearing**: I3 (scope.py) emits keys `{node_id}.fields.{key}`, `{node_id}.status`, `{node_id}.decision` exactly. I4 (dispatch.py) writes results into NodeState in a form that scope.py can read. I5 (loop.py) reads the same keys from scope when evaluating LoopPolicy.until. The existing `lib.conditions.eval_condition` regex accepts dotted paths verbatim — do not change the regex.
- Delivery-workflow sentinel format `<!-- delivery-workflow: {spec_path} -->` and delivery-node sentinel `<!-- delivery-node: {node_id} -->` must be used **byte-identical** across I6 (driver writes child tags), I7 (worker detects parent sentinel), and any test fixture. Define one module-level constant per sentinel; do not inline the string.
- I7 must NOT modify any existing worker test path semantics. Use a single new branch in `RunExecutor.run_goal` that delegates to `delivery_driver.run_delivery_goal` when `_detect_delivery_workflow_spec(brief)` returns non-None. The non-delivery path runs unchanged through `_topo_children_local`.

Open question: confirm the sentinel format with downstream (R6 acceptance does not specify) before I6 begins. If different, update both I6 and I7 in lockstep.

```delivery_status
status: done
produces: design
fields:
  iterations_planned: 8
  has_ui: false
  risks_high: 3
  risks_medium: 5
artifact_paths:
  - .cronos/pipeline/sg4-executor-shared-ir-compiler-a-runner/design-report-sg4-executor-shared-ir-compiler-a-runner.md
open_questions:
  - Confirm delivery-workflow sentinel format `<!-- delivery-workflow: {spec_path} -->` before I6 implementation; analysis R6 leaves the exact form open.
```
