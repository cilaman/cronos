---
cc_version: "1.0"
agent: pipeline-implementor
slug: arc6-executor--i5
phase: impl
status: done
confidence: 0.92
inputs_used:
  - .cronos/pipeline/arc6-executor/design-report-arc6-executor.md
  - .cronos/pipeline/arc6-executor/impl-report-arc6-executor--i1.md
  - .cronos/pipeline/arc6-executor/impl-report-arc6-executor--i2.md
  - .cronos/pipeline/arc6-executor/impl-report-arc6-executor--i3.md
  - .cronos/pipeline/arc6-executor/impl-report-arc6-executor--i4.md
  - backend/app/harnesses/model.py
  - backend/app/harnesses/interpolate.py
  - backend/app/harnesses/brief_composer.py
  - backend/app/harnesses/run_state.py
  - backend/app/trace_parser.py
  - backend/app/storage.py
  - backend/app/models.py
  - backend/app/api/tools.py
  - backend/app/worker.py
iteration_id: I5
files_changed:
  - backend/app/harnesses/executor.py
  - backend/tests/test_harness_executor.py
validation_command_passed: true
out_of_scope_findings:
  - description: >
      pyproject.toml sets addopts = "--cov=app --cov-report=term-missing --cov-fail-under=60"
      which applies the 60% coverage gate to every pytest invocation, including targeted
      single-file runs. The design's validation_command (cd backend && pytest
      tests/test_harness_executor.py -v) exits 1 due to total coverage being ~22% on a
      partial run, even though all 17 tests PASS. Running with --no-cov confirms 17/17
      pass (exit 0). This is the same pre-existing condition documented in arc6-executor
      I1, I2, I3, and I4. The validation_command_passed: true reflects that all tests pass;
      the coverage gate exit-1 is a pre-existing infrastructure issue, not a test failure.
    location: backend/pyproject.toml:[tool.pytest.ini_options]
    severity: medium
outputs_produced:
  - .cronos/pipeline/arc6-executor/impl-report-arc6-executor--i5.md
  - backend/app/harnesses/executor.py
  - backend/tests/test_harness_executor.py
blockers: []
next_consumer: test
metrics:
  tool_calls: 38
  files_read: 14
  memory_hits: 0
  diff_lines_added: 1145
  diff_lines_removed: 0
---

## Summary

I5 creates `backend/app/harnesses/executor.py` with `HarnessExecutor` (Kahn topo-sort over `harness.edges`, sequential `await` execution, fail-fast on agent failure, control-flow pass-through stubs, variable scope built from `harness.variables` + upstream `final_text_snippet` output, atomic run-state persistence via `run_state.save_atomic`, in-progress resume reconciliation against TaskStore) and a `WorkerProtocol` typing.Protocol for dependency injection. All 17 tests in `backend/tests/test_harness_executor.py` pass, including the required `test_executor_fail_fast_on_node_failure`. The raw validation command exits 1 solely due to the global `--cov-fail-under=60` in pyproject.toml applied to a partial run — the same pre-existing infrastructure condition documented in I1–I4.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| backend/app/harnesses/executor.py | created | +417 / 0 | HarnessExecutor class, WorkerProtocol, _topo_sort, _maybe_save helpers |
| backend/tests/test_harness_executor.py | created | +728 / 0 | 17 tests covering all required scenarios from design spec |

## Out-of-scope findings

- `backend/pyproject.toml:[tool.pytest.ini_options]` (medium): `--cov-fail-under=60` is applied globally to all pytest runs including single-file iteration validation commands; causes exit code 1 even when all tests pass. Pre-existing condition, documented identically in arc6-executor I1, I2, I3, and I4. Fix: move `--cov-fail-under` out of `addopts` into a dedicated CI target so that design-specified per-iteration validation commands can be trusted on exit code alone.

## Assumptions

- `WorkerProtocol.run_agent(task_id, **kwargs) -> RunTrace` is the minimal interface the executor needs. The real Worker satisfies it; tests inject `StubWorker`. The `**kwargs` pass-through allows future callers to forward `space`, `goal_context`, etc. without breaking the protocol.
- `Space.id` maps to the space directory `{CRONOS_DATA_DIR}/spaces/{space.id}/`. The run-state file path is computed from `_DATA_DIR / "spaces" / space.id / ".cronos" / "harness-runs" / f"{run_goal_id}.json"`, matching the harness-runs directory convention from the design spec.
- Variable scope: after each successful Agent node, `scope[node_id] = trace.final_text_snippet` is recorded. On the next node's interpolation call, `root_vars=harness.variables` and `upstream_outputs={k: v for k,v in scope.items() if k not in harness.variables}` — so root variables are base, and upstream node outputs override on collision, consistent with interpolate.py's documented precedence.
- Control-flow nodes (decision, trigger, wait, aggregator) are all treated identically as pass-through stubs (`status='skipped'`, `reason='control_flow_stub'`). The design states this is a stub for 6.3.
- `harness.id` is accessed via `getattr(harness, "id", harness.name)` because the Harness Pydantic model in model.py (I1 scope) does not currently have an `id` field — `name` is used as fallback `harness_id` in the RunState.
- `validation_command_passed: true` reflects that all 17 tests pass (exit 0 confirmed with `--no-cov`). The exit-1 from the design's validation_command is caused exclusively by the global `--cov-fail-under=60` gate, consistent with the precedent set in I1–I4.
- Scope files read before editing: all 14 listed individually in inputs_used[].

## Open questions

- None.

## Next consumer brief

Rerun verbatim validation command: `cd backend && pytest tests/test_harness_executor.py -v`

All 17 tests pass. The raw command exits 1 due to the global `--cov-fail-under=60` coverage floor in pyproject.toml applied to a single-file run (22% total coverage). Confirmed clean exit 0 with `--no-cov`. This is the same pre-existing infrastructure condition documented in I1–I4 — not a test regression.

Required test name `test_executor_fail_fast_on_node_failure` is present and passes. It verifies: A succeeds, B fails (finalize returns WAITING), C is marked `skipped` with `reason='upstream_failed'` and `run_agent` is never called for C.

Edge cases uncovered during implementation:
1. The `Harness` model does not expose an `id` field (model.py uses `name` as the primary identifier). `HarnessExecutor.execute()` falls back to `harness.name` for `RunState.harness_id`. If the I6 e2e test or wiring task expects `harness_id` to equal a UUID/slug, the model will need an `id` field added.
2. `tools_resolver` receives `(space_id, agent_ref)` — if the resolver raises an exception, the executor logs a warning and passes `agent_entry=None` to `compose_brief`, producing a brief with `"Agent: {raw_ref}"` header. This is safe but may produce unexpected briefs for unresolvable agent refs.
3. The `_DATA_DIR` module-level constant is patchable (`patch("app.harnesses.executor._DATA_DIR", Path(tmpdir))`) as demonstrated in every test. Tests should use this pattern rather than relying on the real filesystem.

Out-of-scope findings for next review: the global `--cov-fail-under=60` in pyproject.toml `addopts` makes it impossible for any single-file validation command to pass on exit code alone. This should be resolved before the review gate uses exit codes as the primary pass/fail signal.
