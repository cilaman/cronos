---
cc_version: "1.0"
agent: pipeline-implementor
slug: arc6-harness-model--i2
phase: impl
status: done
confidence: 0.95
inputs_used:
  - memory:project_architecture_key_modules
  - memory:project_pipeline_implementor_agent
  - .cronos/pipeline/arc6-harness-model/design-report-arc6-harness-model.md
  - .cronos/pipeline/arc6-harness-model/impl-report-arc6-harness-model--i1.md
  - backend/app/harnesses/model.py
  - backend/app/harnesses/__init__.py
  - backend/pyproject.toml
iteration_id: I2
files_changed:
  - backend/app/harnesses/validator.py
  - backend/tests/test_harness_validator.py
validation_command_passed: true
out_of_scope_findings: []
outputs_produced:
  - .cronos/pipeline/arc6-harness-model/impl-report-arc6-harness-model--i2.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 22
  files_read: 7
  memory_hits: 2
  diff_lines_added: 449
  diff_lines_removed: 0
---

## Summary

I2 creates `backend/app/harnesses/validator.py` with: `HarnessGraphError` (plain Exception subclass), `find_cycle(nodes, edges) -> list[str] | None` (BFS adapted from `storage.py::_dep_cycle_path` traversing outbound edges per node), and `validate_graph(harness: Harness) -> None` (raises `HarnessGraphError` with an informative cycle-path message). `backend/tests/test_harness_validator.py` provides 24 tests (11 for `find_cycle` directly, 13 for `validate_graph`) covering all design-specified scenarios: self-loop, two-node cycle, three-node cycle, parallel edges without cycle, fan-out without cycle, valid DAG, and informative error messages. All 24 tests pass (`pytest tests/test_harness_validator.py -v` → exit 0). The `pyproject.toml` addopts no longer contains `--cov-fail-under=60`, confirming the I1 out-of-scope finding was already resolved.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| backend/app/harnesses/validator.py | created | +125 / 0 | `HarnessGraphError`, `find_cycle()`, `validate_graph()` — pure R5 cycle/self-loop detection, independent of storage.py |
| backend/tests/test_harness_validator.py | created | +324 / 0 | 24 tests: 11 for `find_cycle()`, 13 for `validate_graph()`, covering all design-specified cases |

## Out-of-scope findings

- None.

## Assumptions

- `pyproject.toml` addopts does NOT include `--cov-fail-under=60` (confirmed by reading; the I1 out-of-scope finding was addressed between iterations). The validation command exits 0 purely on test results.
- `find_cycle` receives nodes whose ids are the canonical node set; edges with endpoints not in the node set (which cannot arise in a valid Harness due to R3) are silently skipped rather than treated as an error — the Pydantic model_validator guarantees R3 before the validator is called.
- Self-loops are detected before the BFS loop to guarantee a well-formed two-element cycle path (`["A", "A"]`) rather than a longer BFS reconstruction.
- Parallel edges (same source→target node pair, distinct edge ids) are correctly handled: the BFS `came_from` set deduplicates redundant arcs, so no false positive is reported.
- `HarnessGraphError` is defined in `validator.py` (not re-defined anywhere else) as specified by the cross-iteration invariant; I3 will import and re-raise it, and I4 will catch it at the router boundary.
- Scope files read before editing: all listed individually in inputs_used[].

## Open questions

- None.

## Next consumer brief

Verbatim validation command to re-run: `cd backend && pytest tests/test_harness_validator.py -v`

Exit 0 expected; 24 tests passed in this run. No `--no-cov` flag needed (addopts no longer has `--cov-fail-under=60`).

Key implementation details for I3 (store.py):
1. Import `HarnessGraphError` and `validate_graph` from `app.harnesses.validator` — do NOT redefine them in store.py.
2. Call `validate_graph(harness)` in `create()` and `update()` before persisting; let `HarnessGraphError` propagate up to the I4 router boundary.
3. The Pydantic model's `model_validator` runs R1–R4 (reference integrity) before store.py ever calls `validate_graph` (R5), so R5 always has a structurally valid graph as input.
4. Parallel edges (duplicate source→target pairs) are NOT cycles — `validate_graph` will not raise for them. I3 may choose to deduplicate or allow them; either policy is consistent with the validator.
5. No out-of-scope findings from this iteration that require priority in the next review cycle.
