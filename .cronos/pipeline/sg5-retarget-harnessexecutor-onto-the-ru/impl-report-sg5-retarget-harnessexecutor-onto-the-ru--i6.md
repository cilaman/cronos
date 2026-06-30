---
cc_version: "1.0"
agent: pipeline-implementor
slug: sg5-retarget-harnessexecutor-onto-the-ru--i6
phase: impl
status: done
confidence: 0.9
inputs_used:
  - .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/design-report-sg5-retarget-harnessexecutor-onto-the-ru.md
  - .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/impl-report-sg5-retarget-harnessexecutor-onto-the-ru--i4.md
  - .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/impl-report-sg5-retarget-harnessexecutor-onto-the-ru--i5.md
  - backend/app/harnesses/executor_adapter.py
  - backend/app/harnesses/executor.py
  - backend/app/harnesses/compiler.py
  - backend/app/harnesses/model.py
  - backend/app/harnesses/run_state.py
  - backend/app/harnesses/state_mapping.py
  - backend/app/run_executor.py
  - backend/tests/test_harness_executor.py
  - backend/tests/test_harness_executor_adapter.py
  - packages/delivery-workflow/runner/core.py
  - packages/delivery-workflow/runner/dispatch.py
  - packages/delivery-workflow/state_types.py
  - packages/delivery-workflow/ir.py
iteration_id: I6
files_changed:
  - backend/tests/test_harness_runner_parity.py
  - backend/tests/conftest_harness_parity.py
validation_command_passed: true
out_of_scope_findings:
  - description: >
      runner.core.run() only seeds entry nodes (in-degree-0 nodes with no forward-edge predecessors)
      to its initial work_list. On resume, it checks whether each entry node is already in
      dispatched — if so, the work_list stays empty and run() returns immediately with
      status='done' without traversing downstream nodes. This means the runner cannot resume a
      human-wait harness from the wait node's successors the way BFS does (BFS uses
      waiting_node_id to enqueue successors directly on resume). The runner-resume-from-wait
      path is therefore not testable with the current runner.core.run() API and is omitted from
      the parity test suite. Production resume for the runner path relies on
      workflowstate_to_runstate() correctly mapping waiting_node_id (I5's run_executor.py
      already calls this); the runner itself does not re-enter mid-graph.
    location: "packages/delivery-workflow/runner/core.py"
    severity: medium
  - description: >
      BFS HarnessExecutor emits node_transition events with a 'to_status' key;
      HarnessExecutorAdapter._TelemetryOps emits the same event type with a 'status' key.
      These two schemas are structurally identical except for the status field name. The parity
      tests document this divergence with explicit assertions (test_bfs_uses_to_status_key,
      test_runner_uses_status_key) and use a _node_transition_statuses() helper that accepts
      both keys. Callers who consume SSE node_transition events must handle both keys or
      normalize upstream.
    location: "backend/app/harnesses/executor.py:_publish_event / backend/app/harnesses/executor_adapter.py:_TelemetryOps"
    severity: low
outputs_produced:
  - .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/impl-report-sg5-retarget-harnessexecutor-onto-the-ru--i6.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 55
  files_read: 16
  memory_hits: 0
  diff_lines_added: 1144
  diff_lines_removed: 0
---

## Summary

I6 implements the parity test suite for the BFS HarnessExecutor vs. the delivery-workflow runner path (via HarnessExecutorAdapter). Two new files are created: `conftest_harness_parity.py` (343 lines) providing four synthetic Harness fixtures covering linear, aggregator-all, aggregator-any, and human-wait scenarios; and `test_harness_runner_parity.py` (801 lines) with 38 tests across five test classes. All 38 tests pass (`38 passed in 0.45s`) under the specified validation command. Two structural divergences were uncovered during implementation: the runner cannot resume from mid-graph human-wait nodes (documented as medium out-of-scope finding), and the two paths emit `node_transition` events with different status field names (`to_status` vs `status`).

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| backend/tests/conftest_harness_parity.py | created | +343 / 0 | Four synthetic Harness fixtures (linear, agg-all, agg-any, human-wait) for parity tests |
| backend/tests/test_harness_runner_parity.py | created | +801 / 0 | 38 parity tests across TestLinearParity, TestDecisionAggAllParity, TestDecisionAggAnyParity, TestHumanWaitParity, TestEventSchemaParity |

## Out-of-scope findings

- **runner.core.run() cannot resume from mid-graph** (`packages/delivery-workflow/runner/core.py`, severity: medium): The runner seeds only entry nodes to its initial work_list. On resume, if entry nodes are already dispatched, work_list stays empty and run() exits immediately. BFS uses `waiting_node_id` to enqueue successors directly on resume. The `test_runner_resume_completes` test was dropped from scope; only `test_bfs_resume_completes` and `test_bfs_resume_agent_done` test resume behavior. Production runner resume relies on the run_executor.py run_state→workflowstate→run_state mapping (I5), not on runner.core.run() resuming mid-graph.

- **node_transition event schema divergence** (`executor.py` / `executor_adapter.py`, severity: low): BFS emits `to_status`; runner adapter emits `status`. Both schemas are otherwise identical. The parity suite documents this with `test_bfs_uses_to_status_key` and `test_runner_uses_status_key` and uses a `_node_transition_statuses()` helper accepting both keys. SSE consumers must handle both.

## Assumptions

- The `harness_decision_agg_all` fixture uses direct fan-out (no decision node) rather than a decision node + two edges. This is necessary because BFS decision nodes pick only ONE edge winner, making it impossible to verify `aggregator(all)` with both branches done via the BFS path. The runner's `_enqueue_successors` follows ALL edges with empty/unconditional conditions, so direct fan-out from a non-decision node matches both BFS and runner behavior correctly.
- The aggregator node's `data['inputs']['from']` field lists predecessor node IDs explicitly because the runner's `_dispatch_aggregator` reads predecessors from `node.data['inputs']['from']` (not from harness edge topology). Without this field, `_dispatch_aggregator` would receive an empty predecessor list and fire immediately.
- The `harness_decision_agg_any` fixture uses a single decision+branch-a path. The runner evaluates the decision node via `_dispatch_decision` (returns done without routing) and `_enqueue_successors` follows the unconditional `yes→branch-a` edge. BFS evaluates the decision and also follows `yes` as the winning edge for this scenario.
- `pytest_plugins = ["tests.conftest_harness_parity"]` in the test module imports the fixtures without a `conftest.py` file, consistent with the design iteration's dual-file approach.
- BFS executor writes RunState to disk; tests patch `app.harnesses.executor._DATA_DIR = tmp_path` to isolate file I/O per test.
- Scope files read before editing: all 16 listed individually in inputs_used[].

## Open questions

- None.

## Next consumer brief

**Validation command to rerun**: `cd backend && pytest tests/test_harness_runner_parity.py -v --override-ini="addopts="`

**Result**: 38 passed in 0.45s (exit code 0).

**Edge cases the test agent should know about**:

1. `test_runner_resume_completes` is intentionally absent. The runner cannot resume from a partially-executed human-wait harness because `runner.core.run()` only seeds entry nodes and exits if they are all already dispatched. Only BFS resume is tested (`test_bfs_resume_completes`, `test_bfs_resume_agent_done`).

2. The `harness_decision_agg_all` fixture has NO decision node — it uses direct fan-out with two output ports on `agent-main`. Any test that expects a decision node in this fixture will fail. This was a deliberate design choice to work around the BFS single-edge-winner constraint.

3. Event schema: `_node_transition_statuses()` helper in the test module accepts both `status` (runner) and `to_status` (BFS) keys. Tests that assert on raw event dicts must use `e.get("status") or e.get("to_status")` rather than a fixed key.

4. The out-of-scope finding on runner mid-graph resume (severity: medium) should be prioritized in the next review cycle — it means the runner path's human-wait resume in production differs fundamentally from BFS resume, and the production path (I5) has not been tested for actual resume correctness end-to-end.
