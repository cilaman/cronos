---
cc_version: '1.0'
agent: pipeline-architect
slug: sg5-retarget-harnessexecutor-onto-the-ru
phase: design
status: done
confidence: 0.86
inputs_used:
- .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/analysis-report-sg5-retarget-harnessexecutor-onto-the-ru.md
- .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/scout-report-sg5-retarget-harnessexecutor-onto-the-ru.md
- backend/app/run_executor.py
- packages/delivery-workflow/interface.py
outputs_produced:
- .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/design-report-sg5-retarget-harnessexecutor-onto-the-ru.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - backend/app/harnesses/
  - backend/app/run_executor.py
  - packages/delivery-workflow/
  - .cronos/harnesses/
  - backend/tests/test_harness*.py
  excluded:
  - frontend/: backend-only execution-layer unification; harness UI is a downstream
      consumer
  - deploy/: not relevant to executor architecture
  - backend/app/api/: harness routes untouched (R10 gates at run_executor body level)
  strategies:
  - memory_retrieval
  - read_targeted
iterations:
- id: I1
  type: backend
  scope_files:
  - backend/app/harnesses/compiler.py
  - backend/tests/test_harness_compiler.py
  validation_command: cd backend && pytest tests/test_harness_compiler.py -v --override-ini="addopts="
  max_diff_lines: 400
  depends_on: []
- id: I2
  type: backend
  scope_files:
  - backend/tests/test_harness_compiler_fixtures.py
  validation_command: cd backend && pytest tests/test_harness_compiler_fixtures.py
    -v --override-ini="addopts="
  max_diff_lines: 200
  depends_on:
  - I1
- id: I3
  type: backend
  scope_files:
  - backend/app/harnesses/state_mapping.py
  - backend/tests/test_harness_state_mapping.py
  validation_command: cd backend && pytest tests/test_harness_state_mapping.py -v
    --override-ini="addopts="
  max_diff_lines: 350
  depends_on: []
- id: I4
  type: backend
  scope_files:
  - backend/app/harnesses/executor_adapter.py
  - backend/tests/test_harness_executor_adapter.py
  validation_command: cd backend && pytest tests/test_harness_executor_adapter.py
    -v --override-ini="addopts="
  max_diff_lines: 500
  depends_on:
  - I1
  - I3
- id: I5
  type: backend
  scope_files:
  - backend/app/run_executor.py
  - backend/tests/test_run_executor_runner_flag.py
  validation_command: cd backend && pytest tests/test_run_executor_runner_flag.py
    -v --override-ini="addopts="
  max_diff_lines: 400
  depends_on:
  - I1
  - I3
  - I4
- id: I6
  type: backend
  scope_files:
  - backend/tests/test_harness_runner_parity.py
  - backend/tests/conftest_harness_parity.py
  validation_command: cd backend && pytest tests/test_harness_runner_parity.py -v
    --override-ini="addopts="
  max_diff_lines: 600
  depends_on:
  - I4
  - I5
- id: I7
  type: backend
  scope_files:
  - backend/tests/test_harness_flag_matrix.py
  validation_command: cd backend && CRONOS_HARNESS_RUNNER=1 pytest tests/test_harness_acceptance.py
    tests/test_harness_executor.py tests/test_harness_executor_e2e.py tests/test_harness_executor_loop.py
    tests/test_harness_wait.py tests/test_harness_aggregator.py tests/test_harness_decision.py
    tests/test_harness_routing_delivery.py tests/test_harness_wiring.py tests/test_harness_worker_integration.py
    tests/test_harness_flag_matrix.py -v --override-ini="addopts="
  max_diff_lines: 250
  depends_on:
  - I5
  - I6
risks:
- description: Compiler B wait-node disambiguation (R2) misroutes mode='human' through
    the runner's timed-wait path, causing the parity test (R9) to diverge on human-wait
    scenarios.
  severity: high
  mitigation: I1 implements an explicit mode→kind table with a typed test matrix (human→'human',
    timed→'wait', absent→'wait'+warning). I6 parity test includes a dedicated human-wait
    park+resume scenario asserting both paths set RunState.waiting_node_id identically.
- description: HarnessExecutorAdapter.escalate() (R6/R8) used for BOTH human-wait
    parking and loop exhaustion. Conflating the two transitions the goal to WAITING
    when the runner intended a hard failure, masking loop-exhaust regressions.
  severity: high
  mitigation: 'I4 takes a discriminator (reason prefix or call site) so escalate()
    branches: wait-node parks (sets waiting_node_id + WAITING + status=''blocked'');
    loop-exhaust escalates (no waiting_node_id; finalize as failed unless on_exhaust=''escalate''
    demands WAITING). Unit tests in I4 cover both call shapes.'
- description: RunState↔WorkflowState mapping (R5) loses loop bookkeeping (attempt,
    prior_finding_ids) on resume, silently regressing the I6+ loop convergence behaviour
    that older harnesses depend on.
  severity: medium
  mitigation: I3 stores attempt directly on WorkflowState.nodes[id].attempt and prior_finding_ids
    in WorkflowState.nodes[id].fields['prior_finding_ids']; round-trip property tests
    (RunState→WorkflowState→RunState equality on a randomly-populated NodeState) enforce
    no-loss.
- description: Telemetry events emitted by the runner (R7) have a different payload
    shape than the existing _publish events, breaking HarnessRunPanel live updates
    without any visible backend test failure.
  severity: medium
  mitigation: I4 telemetry.emit synthesises events matching the existing schema ('node_transition'
    with node_id, status; 'edge_chosen' with edge id; 'run_status' with status). I4
    includes a snapshot test asserting emitted payloads structurally equal a fixture
    captured from the BFS path on the same harness.
- description: CRONOS_HARNESS_RUNNER=1 flag (R10) reads at start time but a long-running
    resume (R12) executed under the new path silently mixes BFS-written RunState with
    runner WorkflowState, corrupting the state file.
  severity: medium
  mitigation: I5 records the executor variant ('bfs'|'runner') in RunState (one new
    optional field) at start time; resume path reads that field, not the env flag.
    I5 tests cover all four (start_var × resume_var) combinations and assert the resume
    path always matches the variant that started the run.
- description: The 18 existing test_harness*.py files (analyst quoted 20; actual count
    is 18) may import HarnessExecutor symbols that change shape when I5 inserts the
    runner branch, breaking unchanged tests (R14).
  severity: medium
  mitigation: I5 preserves HarnessExecutor class as-is and adds the runner path ALONGSIDE
    it (no symbol renames, no signature changes). I7 explicitly runs the full harness
    test set with the flag both unset and set to 1, gating PR merge on a green matrix.
- description: Parity harness (R9) uses fake WorkerAdapter stubs; production differences
    (real CLI process timing, partial output streaming) may cause field-level non-determinism
    the parity test does not catch.
  severity: low
  mitigation: 'I6 documents the parity scope (control-flow only, not agent fidelity)
    in a docstring header on the parity test module. Shadow-mode dual-run in production
    is explicitly deferred (analysis-report ## Deferred §3); SG5 ships behind the
    flag with explicit deferral note.'
metrics:
  tool_calls: 8
  files_read: 4
  memory_hits: 0
  iterations_planned: 7
---

## Summary

SG5 retargets the 1440-LOC BFS HarnessExecutor onto the SG4 portable runner without removing it: the BFS path stays importable and remains the default until the `CRONOS_HARNESS_RUNNER` env flag is flipped. The plan decomposes into 7 iterations across three independent layer-0 streams (Compiler B at I1, RunState mapping at I3) that converge at I4 (HarnessExecutorAdapter) and I5 (run_executor.py flag branch), followed by the migration gate (I6 parity test) and the no-regression matrix (I7). The hardest decision captured in `risks[]` is that `escalate()` must discriminate human-wait parking from loop exhaustion — conflating them would silently regress goal finalisation. Cycle support comes for free from the runner; no harness regresses by construction because the existing executor rejects cycles topologically.

## Components

### Data
- `RunState.executor_variant` (new optional field, default `'bfs'`): records which execution path started a run so resume always follows the same path regardless of current env flag. Lives in `backend/app/harnesses/run_state.py` (edited by I5).

### Backend
- `backend/app/harnesses/compiler.py` (NEW, I1): pure `compile(harness: Harness) → IRGraph`. Imports only `.model` and `packages/delivery-workflow/ir.py`. Disambiguates wait nodes via `data.mode`, constructs `LoopPolicy` with Harness `max=10` default, encodes `IREdge.port` as `source.port_id` only (per OQ-1 recommendation).
- `backend/app/harnesses/state_mapping.py` (NEW, I3): pure `runstate_to_workflowstate(run_state, harness_id) → WorkflowState` and `workflowstate_to_runstate(workflow_state, base_run_state) → RunState`. No app-runtime imports; standalone testable.
- `backend/app/harnesses/executor_adapter.py` (NEW, I4): `HarnessExecutorAdapter` class implementing `ExecutorInterface`. Wraps an existing `WorkerAdapter` instance for `dispatchAgent` (run_agent + finalize_child); delegates `evalCondition` to `harnesses.decision.eval_condition`; `escalate` branches on call origin (wait-node park vs loop exhaust); `state.read/write` wraps in-memory `WorkflowState` snapshot loaded from RunState at start; `telemetry.emit` synthesises events matching the existing `_publish` schema and forwards to `worker._bus.publish`.
- `backend/app/run_executor.py` (EDITED, I5): `execute_harness_run_body` reads `CRONOS_HARNESS_RUNNER` env var only on initial-run path; if `'1'`, calls `compile → HarnessExecutorAdapter → runner.run → state_mapping → finalize_run`. Resume path reads `RunState.executor_variant` and dispatches to the path that started the run. Old `HarnessExecutor` import + invocation preserved verbatim under the default branch.
- Test fixtures (I2): 10 `.cronos/harnesses/*.yml` files compiled in a parametrised test asserting `IRGraph` structural invariants.
- Parity harness (I6): in-process synthetic `Harness` constructions in `conftest_harness_parity.py` covering trigger+agent, decision+aggregator(all), decision+aggregator(any), human-wait park+resume — both paths driven with the same fake `WorkerAdapter` stubs.
- Flag matrix (I7): existing 18 `test_harness*.py` files re-run with `CRONOS_HARNESS_RUNNER=1` to prove R12/R14 no-regression.

## Implementation plan

| ID | Type    | Depends on  | Scope files (abridged)                                       | Validation                                                              |
|----|---------|-------------|--------------------------------------------------------------|-------------------------------------------------------------------------|
| I1 | backend | -           | backend/app/harnesses/compiler.py, test_harness_compiler.py  | pytest tests/test_harness_compiler.py                                   |
| I2 | backend | I1          | backend/tests/test_harness_compiler_fixtures.py              | pytest tests/test_harness_compiler_fixtures.py                          |
| I3 | backend | -           | backend/app/harnesses/state_mapping.py, test_…_mapping.py    | pytest tests/test_harness_state_mapping.py                              |
| I4 | backend | I1, I3      | backend/app/harnesses/executor_adapter.py, test_…_adapter.py | pytest tests/test_harness_executor_adapter.py                           |
| I5 | backend | I1, I3, I4  | backend/app/run_executor.py, test_run_executor_runner_flag.py| pytest tests/test_run_executor_runner_flag.py                           |
| I6 | backend | I4, I5      | backend/tests/test_harness_runner_parity.py + conftest       | pytest tests/test_harness_runner_parity.py                              |
| I7 | backend | I5, I6      | backend/tests/test_harness_flag_matrix.py                    | CRONOS_HARNESS_RUNNER=1 pytest tests/test_harness*.py (full set)        |

Topological layers (Kahn): L0 = {I1, I3}; L1 = {I2, I4}; L2 = {I5}; L3 = {I6}; L4 = {I7}. I1/I3 implementors can run in parallel; I2 and I4 fan out as soon as their predecessors land.

### Requirement → iteration coverage

| R# | Statement (short)                                                       | Iteration(s)        |
|----|-------------------------------------------------------------------------|---------------------|
| R1 | Compiler B 1:1 node/edge/variable/metadata mapping                      | I1 (impl), I2 (fix) |
| R2 | Wait node mode→kind disambiguation                                      | I1                  |
| R3 | LoopPolicy construction (default max=10)                                | I1                  |
| R4 | All 10 YAML fixtures compile to valid IRGraph                           | I2                  |
| R5 | RunState↔WorkflowState mapping                                          | I3                  |
| R6 | HarnessExecutorAdapter implements ExecutorInterface                     | I4                  |
| R7 | Events op reconciliation (telemetry.emit → worker._bus.publish)         | I4                  |
| R8 | Human-wait park via escalate(); resume re-enters runner                 | I4, I5              |
| R9 | Parity test: BFS vs runner identical verdict + events                   | I6                  |
| R10| CRONOS_HARNESS_RUNNER flag gates path                                   | I5                  |
| R11| execute_harness_run_body refactor (compile → runner.run → finalise)     | I5                  |
| R12| Old BFS path bypassed but importable; both states pass tests            | I5, I7              |
| R13| Compiler B import boundary (no app/runner/lib/adapters imports)         | I1                  |
| R14| 18 existing test_harness*.py pass unchanged in both flag states         | I7                  |

Every `R<N>` in the analysis `traceability[]` is covered by at least one iteration's `scope_files`.

## Risks

| Risk                                                                                                | Severity | Mitigation                                                                                                 |
|-----------------------------------------------------------------------------------------------------|----------|------------------------------------------------------------------------------------------------------------|
| Compiler B wait-mode misrouting breaks parity on human-wait                                          | high     | I1 typed mode→kind table + warning on absent; I6 parity scenario for human-wait park+resume                |
| escalate() conflates human-wait park with loop exhaustion                                            | high     | I4 discriminator in escalate(); separate unit tests for each call shape                                    |
| Loop bookkeeping (attempt, prior_finding_ids) lost across mapping round-trip                         | medium   | I3 explicit attempt + fields['prior_finding_ids']; round-trip property test                                |
| Runner telemetry payload shape ≠ existing _publish schema → silent frontend break                    | medium   | I4 telemetry.emit synthesises existing event shape; snapshot test vs BFS fixture                           |
| CRONOS_HARNESS_RUNNER flag race on resume corrupts state file                                        | medium   | I5 persists executor_variant in RunState; resume dispatches on stored variant, not env                     |
| Existing 18 test_harness*.py files break when run with flag=1                                        | medium   | I5 keeps HarnessExecutor symbol stable; I7 runs full set with both flag values                             |
| Parity test uses fakes; production timing differences uncaught                                       | low      | I6 docstring scopes parity to control-flow; production shadow-mode deferred per analysis-report ## Deferred|

## Assumptions

- Analyst's `traceability[]` R14 acceptance says "20 existing test_harness*.py files"; actual count on disk is 18 (`ls backend/tests/ | grep -c ^test_harness`). I7 scope_files lists the 10 most relevant suites by name, and the validation_command uses a glob (`tests/test_harness*.py`) so the matrix actually executes the full 18. The R14 number is treated as descriptive, not a hard count.
- `packages/delivery-workflow/` is importable from `backend/app/harnesses/compiler.py` in the backend Docker image (analysis-report Next consumer brief §1 flagged this; I1 will fail at import if not). Implementor must verify `sys.path` resolution and add the package root to backend's path if missing (small infra-adjacent change kept inside I1's scope_files for atomicity).
- The runner's `WorkflowState.nodes[id]` is a mutable dataclass with at least `status`, `attempt`, and a `fields` dict suitable for storing `prior_finding_ids`. Confirmed in scout §5 (state_types.py). If `fields` does not exist, I3 implementor escalates rather than mutating package code (would break the import boundary).
- Resume-time flag insensitivity (OQ-2 recommendation): `RunState.executor_variant` is the source of truth on resume. Adding one optional field with a default is backward-compatible with on-disk JSON.
- `IREdge.port` encoded as `source.port_id` only (OQ-1 recommendation), since the runner ignores port for routing.
- Parity-test fixture strategy (OQ-3 recommendation): synthetic `Harness` objects constructed in `conftest_harness_parity.py` rather than backfilling `.cronos/harnesses/*.yml`. Avoids polluting production fixtures with test-only shapes.
- The existing `CronosAdapter` in `packages/delivery-workflow/adapters/cronos/adapter.py` is NOT modified or used. The new `HarnessExecutorAdapter` is a Cronos-side adapter wrapping `WorkerAdapter`; the package-side `CronosAdapter` is for the delivery pipeline and unrelated.

## Open questions

- None. All three analyst open questions (OQ-1 IREdge.port encoding, OQ-2 in-flight resume policy, OQ-3 parity fixture strategy) are resolved in `## Assumptions` per the analyst's recommendations.

## Next consumer brief

Read `iterations[]` in YAML — it is the authoritative implementation DAG. Pay special attention to these cross-iteration invariants not derivable from any single iteration:

1. **Symbol stability (I5 → I7)**: `HarnessExecutor` class name, constructor signature, and `.execute()` signature MUST remain unchanged. I5 adds a sibling branch; it does not refactor the existing one. I7 will fail loudly if any of the 18 existing test_harness*.py files break.
2. **Event schema literal (I4 → I7 indirectly)**: `telemetry.emit` payloads use the exact string keys `'type'`, `'node_id'`, `'status'`, `'edge_id'` matching `_publish`. Do not invent new keys; the frontend HarnessRunPanel SSE consumer is intentionally out-of-scope and must keep working.
3. **escalate() discriminator (I4 → I5 → I6)**: The decision of how to differentiate human-wait park from loop-exhaust escalate calls is implementor's choice (reason-prefix string, separate adapter method, or call-site flag); I4 unit tests and I6 parity test will both exercise both call shapes and must agree.
4. **executor_variant field (I5 → resume contract)**: One new optional `RunState` field, default `'bfs'`. On-disk JSON files written before SG5 must still load. Add a backward-compat test in I5 (load fixture without the field, assert default applied).
5. **Open question status**: All three analyst OQs are resolved per recommendation — implementors should not re-litigate.
