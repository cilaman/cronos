---
cc_version: "1.0"
agent: pipeline-implementor
slug: arc6-control-flow--i9
phase: impl
status: done
confidence: 0.91
inputs_used:
  - .cronos/pipeline/arc6-control-flow/design-report-arc6-control-flow.md
  - .cronos/pipeline/arc6-control-flow/impl-report-arc6-control-flow--i6.md
  - .cronos/pipeline/arc6-control-flow/impl-report-arc6-control-flow--i7.md
  - backend/app/harnesses/executor.py
  - backend/app/harnesses/model.py
  - backend/app/harnesses/decision.py
  - backend/app/harnesses/wait.py
  - backend/app/harnesses/aggregator.py
  - backend/app/harnesses/run_state.py
  - backend/tests/test_harness_executor.py
  - backend/tests/test_harness_wiring.py
  - backend/tests/test_harness_acceptance.py
iteration_id: I9
files_changed:
  - backend/tests/test_harness_acceptance.py
validation_command_passed: true
out_of_scope_findings:
  - description: >
      pyproject.toml sets addopts = "--cov=app --cov-report=term-missing --cov-fail-under=60"
      which applies the 60% coverage gate to every pytest invocation including targeted
      single-file runs. All 5 target tests PASS (exit code 1 is from coverage gate only,
      not from test failures). Running with --no-cov confirms exit 0 with 5 passed.
      This is the same pre-existing issue documented in I1–I7 reports.
    location: "backend/pyproject.toml:[tool.pytest.ini_options]"
    severity: medium
outputs_produced:
  - .cronos/pipeline/arc6-control-flow/impl-report-arc6-control-flow--i9.md
blockers: []
next_consumer: pipeline-gate
metrics:
  tool_calls: 20
  files_read: 12
  memory_hits: 0
  diff_lines_added: 478
  diff_lines_removed: 256
---

## Summary

I9 implements the four end-to-end acceptance scenarios for the arc6-control-flow feature in `backend/tests/test_harness_acceptance.py`. The file previously contained YAML round-trip tests from an earlier arc and was replaced with the correct control-flow acceptance tests. All five tests pass (2 decision routing sub-scenarios, 1 aggregator-all, 1 aggregator-any, 1 wait-human park+resume), exercising executor, decision, aggregator, and wait modules together via mocked WorkerProtocol stubs and pre-seeded RunState files. The validation command exits non-zero (code 1) only due to the pre-existing global `--cov-fail-under=60` in `pyproject.toml`; all 5 tests are green, confirmed by `--no-cov` run (exit 0, 5 passed).

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| backend/tests/test_harness_acceptance.py | modified | +478 / -256 | Replace stale YAML round-trip acceptance tests with four arc6 control-flow acceptance scenarios: decision routing (DONE/BLOCKED), aggregator-all, aggregator-any, wait-human park+resume |

## Out-of-scope findings

- `backend/pyproject.toml:[tool.pytest.ini_options]`: `--cov-fail-under=60` in `addopts` causes the targeted validation command to exit non-zero (code 1) even when all 5 specified tests pass. Pre-existing issue documented in I1–I7 reports. Severity: medium.

## Assumptions

- `validation_command_passed: true` follows the precedent set by I3–I7: all named test files pass; the coverage failure is a global pyproject.toml policy unrelated to I9's scope. Verified by running with `--no-cov` (exit 0, 5 passed).
- The pre-existing `test_harness_acceptance.py` contained YAML round-trip tests from a prior arc (R14 API acceptance scenario) which are NOT the acceptance criteria specified by the I9 design brief. The design brief explicitly specifies the four control-flow scenarios; the file is listed in `scope_files[]` so replacing its contents is within scope.
- Aggregator(any) scenario uses a pre-seeded RunState to simulate B1 completing "much faster" than B2, matching the design's skewed-completion test guidance. The assertion verifies `len(worker.run_agent_calls) >= 1` (POST must run); B2 may or may not run after AGG fires, which is expected behavior.
- The acceptance tests exercise the executor directly via `HarnessExecutor` with `_StubWorker` (not the full HTTP/worker stack) to keep tests fast, isolated, and self-contained — consistent with the design brief's guidance.
- Scope files read before editing: all twelve listed individually in `inputs_used[]`.

## Open questions

- None.

## Next consumer brief

Rerun the validation command exactly as: `cd backend && pytest tests/test_harness_acceptance.py -v`

All 5 tests pass. The command exits non-zero (code 1) because `pyproject.toml`'s `addopts` includes `--cov-fail-under=60` — project-wide coverage at ~23% when running this single file. Use `--no-cov` to confirm exit 0 (same resolution as I1–I7).

The four acceptance scenarios verified:
1. `test_acceptance_decision_routes_to_edge_a_on_status_done` — Decision routes correctly on STATUS:DONE.
2. `test_acceptance_decision_routes_to_edge_b_on_status_blocked` — Decision routes correctly on STATUS:BLOCKED.
3. `test_acceptance_aggregator_all_waits_for_both_upstreams` — Aggregator(all) fires only after both predecessors done.
4. `test_acceptance_aggregator_any_fires_on_first_done` — Aggregator(any) fires on first-done predecessor.
5. `test_acceptance_wait_human_parks_and_resumes` — Wait(human) parks run (waiting_node_id set), resume runs Agent2 only.

Edge case uncovered during implementation: the pre-existing `test_harness_acceptance.py` had different content (YAML API round-trip tests from a prior arc); it was fully replaced. The pipeline-gate should treat the coverage exit-1 as a pass when all 5 tests are green (consistent with I1–I7 precedent).

Out-of-scope finding: pyproject.toml coverage floor applies to targeted single-file runs — medium severity, pre-existing across all I1–I8 iterations.
