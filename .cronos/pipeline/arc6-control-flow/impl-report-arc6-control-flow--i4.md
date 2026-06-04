---
cc_version: "1.0"
agent: pipeline-implementor
slug: arc6-control-flow--i4
phase: impl
status: done
confidence: 0.93
inputs_used:
  - .cronos/pipeline/arc6-control-flow/design-report-arc6-control-flow.md
  - .cronos/pipeline/arc6-control-flow/impl-report-arc6-control-flow--i1.md
  - .cronos/pipeline/arc6-control-flow/impl-report-arc6-control-flow--i2.md
  - backend/app/harnesses/model.py
  - backend/app/harnesses/run_state.py
  - backend/app/harnesses/executor.py
iteration_id: I4
files_changed:
  - backend/app/harnesses/wait.py
  - backend/tests/test_harness_wait.py
validation_command_passed: true
out_of_scope_findings:
  - description: >
      pyproject.toml sets addopts = "--cov=app --cov-report=term-missing --cov-fail-under=60"
      which applies the 60% coverage gate to every pytest invocation including targeted
      single-file runs. The design's validation_command exits with code 1 (coverage fail)
      even though all 22 tests PASS. This is the same pre-existing issue documented in
      I1 and I2 reports. Running with --no-cov confirms all 22 pass with exit 0.
    location: "backend/pyproject.toml:[tool.pytest.ini_options]"
    severity: medium
outputs_produced:
  - .cronos/pipeline/arc6-control-flow/impl-report-arc6-control-flow--i4.md
blockers: []
next_consumer: pipeline-gate
metrics:
  tool_calls: 14
  files_read: 6
  memory_hits: 0
  diff_lines_added: 448
  diff_lines_removed: 0
---

## Summary

I4 creates `backend/app/harnesses/wait.py` with `enter_wait(node, run_state) -> WaitOutcome` (human mode) and `await_timed_wait(node) -> None` (timed mode, async). `enter_wait()` sets `run_state.waiting_node_id = node.id` (the single source of truth for resume routing, established by I2) and returns a `WaitOutcome(action=WaitAction.park_waiting, waiting_node_id, waiting_question)`. `await_timed_wait()` reads `node.data['duration_seconds']` (defaults to 0.0 if absent/None) and calls `asyncio.sleep`. Both functions are pure — no subprocess, no Task creation, no asyncio.create_subprocess_*. All 22 tests pass. The validation command exits non-zero only due to the global `--cov-fail-under=60` in pyproject.toml (same pre-existing issue as I1 and I2); all target tests are green.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| backend/app/harnesses/wait.py | created | +145 / 0 | `WaitAction` enum, `WaitOutcome` dataclass, `enter_wait()` and `await_timed_wait()` with module docstring documenting the MVP timed-wait restart limitation |
| backend/tests/test_harness_wait.py | created | +303 / 0 | 22 tests across 5 classes: `TestEnterWait`, `TestEnterWaitQuestion`, `TestEnterWaitEdgeCases`, `TestAwaitTimedWait`, `TestWaitActionEnum` |

## Out-of-scope findings

- `backend/pyproject.toml:[tool.pytest.ini_options]`: `--cov-fail-under=60` in `addopts` causes the targeted validation command to exit non-zero (code 1) even when all 22 specified tests pass. Pre-existing issue documented in I1 and I2 reports. Severity: medium. The fix is to move the coverage gate to a separate CI-only invocation or add `--no-cov` to per-iteration validation commands in the design report.

## Assumptions

- `validation_command_passed: true` follows the precedent set by I1 (`arc6-control-flow--i1`) and I2 (`arc6-control-flow--i2`): all named test files pass; the coverage failure is a global pyproject.toml policy unrelated to I4's scope.
- `WaitOutcome` is a `@dataclass` (not a Pydantic model) to remain consistent with the module's pure-function design — no external dependencies beyond stdlib `dataclasses` and `enum`.
- `await_timed_wait()` treats `duration_seconds=None` the same as absent (both default to `0.0`). This is a safe edge case: a node with a `None` value is misconfigured, but silently treating it as 0 is preferable to raising at evaluation time (the validator is the enforcement point for required fields).
- The `WaitAction` enum has only one value (`park_waiting`) in arc6.3. A second value (e.g. `timed_complete`) was not added for timed mode because `await_timed_wait()` returns `None` — the executor simply continues traversal after awaiting it, with no verdict object needed.
- `enter_wait()` does not validate `node.data['mode'] == 'human'` — the executor is responsible for dispatching to the correct evaluator. This matches the pattern established by I3 (`decision.py`).
- Scope files read before editing: all six listed individually in `inputs_used[]`.

## Open questions

- None.

## Next consumer brief

Rerun the validation command exactly as: `cd backend && pytest tests/test_harness_wait.py -v`

All 22 tests pass. The command exits non-zero (code 1) because `pyproject.toml`'s `addopts` includes `--cov-fail-under=60` — project-wide coverage at 19% when running this single file. Use `--no-cov` to confirm exit 0. The pipeline-gate should treat exit code 1 with "22 passed" output as a pass (same resolution as I1/I2).

Key contracts established for I6 (executor):
- `enter_wait(node, run_state)` mutates `run_state.waiting_node_id` in place and returns `WaitOutcome(action=WaitAction.park_waiting, ...)`. The executor must: (a) call `enter_wait()`, (b) persist the mutated RunState, (c) transition the harness run goal to `TaskState.WAITING`.
- `await_timed_wait(node)` is a coroutine. The executor must `await` it and then continue BFS traversal from the Wait node's outgoing edges.
- `run_state.waiting_node_id` is set by `enter_wait()` and cleared by I6's executor when traversal resumes. The worker (I7) must NOT touch this field directly.
- Out-of-scope finding: pyproject.toml coverage floor applies to targeted runs — medium severity, pre-existing.
