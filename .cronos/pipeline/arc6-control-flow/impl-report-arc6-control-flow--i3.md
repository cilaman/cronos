---
cc_version: "1.0"
agent: pipeline-implementor
slug: arc6-control-flow--i3
phase: impl
status: done
confidence: 0.9
inputs_used:
  - .cronos/pipeline/arc6-control-flow/design-report-arc6-control-flow.md
  - .cronos/pipeline/arc6-control-flow/impl-report-arc6-control-flow--i1.md
  - backend/app/harnesses/model.py
  - backend/app/harnesses/executor.py
  - backend/app/harnesses/run_state.py
  - backend/app/harnesses/validator.py
  - backend/app/trace_parser.py
iteration_id: I3
files_changed:
  - backend/app/harnesses/decision.py
  - backend/tests/test_harness_decision.py
validation_command_passed: true
out_of_scope_findings:
  - description: >
      pyproject.toml sets addopts = "--cov=app --cov-report=term-missing --cov-fail-under=60"
      which applies the 60% coverage gate to every pytest invocation including targeted
      single-file runs. All 59 target tests PASS (exit code 1 is from coverage gate only,
      not from a test failure). This is the same pre-existing issue documented in
      arc6-control-flow--i1.
    location: "backend/pyproject.toml:[tool.pytest.ini_options]"
    severity: medium
outputs_produced:
  - .cronos/pipeline/arc6-control-flow/impl-report-arc6-control-flow--i3.md
blockers: []
next_consumer: pipeline-gate
metrics:
  tool_calls: 18
  files_read: 7
  memory_hits: 0
  diff_lines_added: 1005
  diff_lines_removed: 0
---

## Summary

I3 implements `backend/app/harnesses/decision.py` (new module) with three-layer signal precedence (Status marker > exit_reason > regex > variable), and `backend/tests/test_harness_decision.py` (new test file) with 59 tests covering every signal layer in isolation, layered precedence, missing-signal fallback, default edge fallback, and all three variable operators. All 59 tests pass. The validation command exits non-zero only due to the pre-existing global `--cov-fail-under=60` in `pyproject.toml`; this is the same issue documented in I1 and does not indicate a test failure.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| backend/app/harnesses/decision.py | created | +334 / 0 | Decision node evaluator: `resolve_signal`, `edge_matches`, `evaluate_decision`, `_eval_variable_condition` with four-layer signal precedence and whitelisted variable grammar |
| backend/tests/test_harness_decision.py | created | +671 / 0 | 59 tests covering all signal layers (isolation + layered precedence), missing-signal fallback, default edge, and variable operators ==, !=, in |

## Out-of-scope findings

- `backend/pyproject.toml:[tool.pytest.ini_options]`: `--cov-fail-under=60` in `addopts` causes the targeted validation command to exit non-zero even when all specified tests pass. Pre-existing issue documented in arc6-control-flow--i1. Severity: medium. Fix: move coverage gate to a separate CI-only invocation or add `--no-cov` to per-iteration validation commands.

## Assumptions

- `validation_command_passed: true` follows the precedent set by arc6-control-flow--i1: all named test files pass; coverage failure is a global pyproject.toml policy unrelated to I3's scope. Verified by running with `--no-cov` (exit 0, 59 passed).
- The STATUS marker pattern `STATUS: <value>` (regex `STATUS:\s*(\S+)`) is the canonical output convention used by the `task-finalize` skill, consistent with `project_parse_status_fix.md` memory reference.
- `evaluate_decision` accepts `outgoing_edges` as a parameter (caller-provided) rather than discovering them from the full `Harness` object. This keeps the function pure and decoupled from harness graph traversal — the executor (I6) already has the outgoing edges in its BFS queue logic.
- The `resolve_signal` function returns `("variable", None)` when no higher-priority signal is available; the scope dict is passed separately through `evaluate_decision` to `edge_matches`. This avoids encoding the scope inside the signal tuple.
- I1 confirmed `HarnessValidationError` / `HarnessGraphError` hierarchy is established; no imports from `validator.py` are needed by `decision.py`.
- Scope files read before editing: all five listed individually in inputs_used[].

## Open questions

- None.

## Next consumer brief

Rerun the validation command exactly as: `cd backend && pytest tests/test_harness_decision.py -v`

All 59 tests pass. The command exits non-zero (code 1) because pyproject.toml's `addopts` includes `--cov-fail-under=60` which fires on every targeted run — pre-existing global policy issue documented in I1. Add `--no-cov` to disambiguate exit code.

Key contracts established for downstream iterations (I6):
- `evaluate_decision(node, predecessors_state, scope, run_trace, outgoing_edges) -> str` returns an edge id; caller (executor I6) must look up the target node from the returned edge id.
- Signal layer precedence is fully encapsulated in `resolve_signal` + `edge_matches`; I6 should not duplicate signal resolution logic — just call `evaluate_decision`.
- Default edge is `HarnessEdge` with `condition=None`; `edge_matches` always returns False for it (caller must handle separately via `evaluate_decision`).
- Variable conditions use whitelisted grammar (`==`, `!=`, `in`); unsupported operators silently return False — harness authors should use supported operators only.
- `evaluate_decision` raises `ValueError` if no matching edge AND no default edge exists; I6 should catch this and mark the Decision node as `failed`.
- Out-of-scope finding: pyproject.toml coverage floor applies to targeted runs — medium severity, worth fixing in a future iteration.
