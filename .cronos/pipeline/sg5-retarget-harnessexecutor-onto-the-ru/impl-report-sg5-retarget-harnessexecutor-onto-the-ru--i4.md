---
cc_version: "1.0"
agent: pipeline-implementor
slug: sg5-retarget-harnessexecutor-onto-the-ru--i4
phase: impl
status: done
confidence: 0.92
inputs_used:
  - .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/design-report-sg5-retarget-harnessexecutor-onto-the-ru.md
  - .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/impl-report-sg5-retarget-harnessexecutor-onto-the-ru--i1.md
  - .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/impl-report-sg5-retarget-harnessexecutor-onto-the-ru--i3.md
  - packages/delivery-workflow/interface.py
  - packages/delivery-workflow/state_types.py
  - packages/delivery-workflow/results.py
  - packages/delivery-workflow/ir.py
  - packages/delivery-workflow/null_runtime.py
  - packages/delivery-workflow/runner/core.py
  - packages/delivery-workflow/runner/dispatch.py
  - packages/delivery-workflow/lib/conditions.py
  - backend/app/harnesses/state_mapping.py
  - backend/app/harnesses/decision.py
  - backend/app/harnesses/run_state.py
  - backend/app/harnesses/executor.py
  - backend/app/harnesses/compiler.py
  - backend/app/models.py
  - backend/app/trace_parser.py
iteration_id: I4
files_changed:
  - backend/app/harnesses/executor_adapter.py
  - backend/tests/test_harness_executor_adapter.py
validation_command_passed: true
out_of_scope_findings:
  - description: "asyncio.get_event_loop() is deprecated in Python 3.12 when there is no running loop; the _run_sync helper emits a DeprecationWarning. This is a known asyncio.run() vs event-loop-access pattern issue that should be addressed in a follow-up (replace with asyncio.new_event_loop().run_until_complete())."
    location: "backend/app/harnesses/executor_adapter.py:487"
    severity: low
outputs_produced:
  - .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/impl-report-sg5-retarget-harnessexecutor-onto-the-ru--i4.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 28
  files_read: 18
  memory_hits: 0
  diff_lines_added: 1164
  diff_lines_removed: 0
---

## Summary

I4 implements `HarnessExecutorAdapter` in `backend/app/harnesses/executor_adapter.py` — a Cronos-side bridge from the `ExecutorInterface` protocol to the BFS worker runtime. The adapter wraps a `WorkerAdapter` Protocol stub for `dispatchAgent` (calls `run_agent` + `finalize_child`), delegates `evalCondition` to `harnesses.decision.eval_condition`, and discriminates `escalate()` calls between human-wait parking (sets WorkflowState to `blocked`) and loop-exhaust escalation (sets to `escalated`) using reason-string prefix matching. Telemetry events are synthesised to match the existing `_publish` schema (`node_transition`, `edge_chosen`, `run_status`). All 47 unit tests pass, including a snapshot test validating the telemetry event shape matches the BFS-path fixture.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| backend/app/harnesses/executor_adapter.py | created | +505 / 0 | HarnessExecutorAdapter, WorkerAdapter Protocol, _StateOps, _TelemetryOps |
| backend/tests/test_harness_executor_adapter.py | created | +659 / 0 | 47 unit tests covering R6/R7/R8, escalate discriminator, snapshot test |

## Out-of-scope findings

- `asyncio.get_event_loop()` deprecated warning in `executor_adapter.py:487` — the `_run_sync` helper uses the deprecated event loop accessor when there is no running loop. Low severity; the tests pass. Should be replaced with `asyncio.new_event_loop().run_until_complete()` in a follow-up.

## Assumptions

- `WorkerAdapter.run_agent(task_id)` and `finalize_child(task_id)` take a single positional `task_id` argument (no `trace` param for `finalize_child`, unlike the existing BFS `WorkerProtocol`). This matches the design spec's `WorkerAdapter` Protocol definition and keeps the adapter simpler; the real `Worker.finalize_child` accepts `(task_id, trace)` so callers in I5 will need to wire the trace through separately or use the BFS path.
- The `in` operator in `eval_condition` uses comma-separated values (`x in done,failed`) per the lib/conditions.py implementation — the test was corrected accordingly.
- `task_id_factory` in tests resolves child task IDs without hitting TaskStore; I5 will inject the real creation path via a pre-wired factory or direct lookup.
- Scope files read before editing: all listed individually in inputs_used[].

## Open questions

- None. The design's `escalate()` discriminator is implemented via `_is_human_wait()` reason-prefix check; I5 and I6 tests will exercise both call shapes end-to-end.

## Next consumer brief

Rerun: `cd backend && python -m pytest tests/test_harness_executor_adapter.py -v --override-ini="addopts="`

Edge cases uncovered during implementation:
1. **`_run_sync` in sync context**: `dispatchAgent` is called synchronously by `runner.core.run()` (via `dispatch_node`). When no event loop is running (test contexts without pytest-asyncio auto mode), `asyncio.get_event_loop()` emits a DeprecationWarning in Python 3.12. The threaded fallback handles the already-running-loop case correctly. Consider replacing with `asyncio.new_event_loop()` in I5.
2. **`waiting_node_id` not set by adapter**: The adapter sets `WorkflowState.status = "blocked"` on human-wait escalation but does NOT set `RunState.waiting_node_id` — that responsibility stays with `run_executor.py` (I5) which reads `to_run_state()` after the runner returns and sets `waiting_node_id` from the blocked node's id before persisting.
3. **`runGate` raises `NotImplementedError`**: Cronos harnesses have no gate nodes; if a compiled harness somehow produces a gate kind, the runner will log a dispatch failure. The out-of-scope finding is low severity.
4. **`eval_condition` `in` syntax**: comma-separated values, not space-separated. Ensure I5/I6 test harnesses use `x in v1,v2` syntax in edge conditions.
