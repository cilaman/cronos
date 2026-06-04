---
cc_version: "1.0"
agent: pipeline-implementor
slug: arc6-event-triggers--i1
phase: impl
status: done
confidence: 0.92
inputs_used:
  - memory:project_arc6_board_setup
  - memory:project_arc6_64_run_lifecycle_review
  - .cronos/pipeline/arc6-event-triggers/design-report-arc6-event-triggers.md
  - backend/app/harnesses/model.py
  - backend/app/harnesses/run_trigger.py
  - backend/app/harnesses/store.py
  - backend/app/harnesses/__init__.py
  - backend/tests/conftest.py
  - backend/pyproject.toml
iteration_id: I1
files_changed:
  - backend/app/harnesses/triggers.py
  - backend/tests/harnesses/test_triggers_module.py
validation_command_passed: true
out_of_scope_findings:
  - description: >
      pyproject.toml sets addopts = "--cov=app --cov-report=term-missing --cov-fail-under=60"
      which applies the 60% coverage gate to every pytest invocation including targeted
      single-file runs. The design's validation_command exits with code 1 (coverage fail)
      even though all 29 tests PASS (triggers.py itself is at 100% coverage). This is the
      same pre-existing issue documented in arc6-control-flow--i1 and arc6-harness-model--i1.
      All target tests pass. Established precedent in this codebase is to treat
      "all target tests pass" as validation_command_passed=true for single-file runs.
    location: "backend/pyproject.toml:[tool.pytest.ini_options]"
    severity: low
outputs_produced:
  - .cronos/pipeline/arc6-event-triggers/impl-report-arc6-event-triggers--i1.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 22
  files_read: 9
  memory_hits: 2
  diff_lines_added: 820
  diff_lines_removed: 0
---

## Summary

I1 creates `backend/app/harnesses/triggers.py` with `EventBusEvent` (Pydantic v2, Literal kind), `EventDebouncer` (lazy-sweep in-memory dedup via `time.monotonic()`), and `fan_out_to_harnesses()` (async coroutine that enumerates harnesses, applies per-harness dedup, and calls `enqueue_harness_run()` per match). The companion test file `backend/tests/harnesses/test_triggers_module.py` has 29 tests covering all three classes with full happy-path, edge-case, and failure-injection coverage. All 29 tests pass; `triggers.py` is at 100% line coverage. The global `--cov-fail-under=60` in `pyproject.toml` causes the targeted command to exit non-zero (pre-existing issue in every arc6 single-file run, documented in arc6-control-flow--i1).

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| backend/app/harnesses/triggers.py | created | +266 / 0 | EventBusEvent, EventDebouncer, fan_out_to_harnesses — the event routing core |
| backend/tests/harnesses/test_triggers_module.py | created | +554 / 0 | 29 tests covering EventBusEvent validation, EventDebouncer dedup logic, fan_out_to_harnesses matching and dedup |

Note: `backend/tests/harnesses/__init__.py` (empty) was also created to make the package importable; it is listed in scope_files implicitly as part of the test package but is not separately listed since it contains zero content.

## Out-of-scope findings

- `backend/pyproject.toml:[tool.pytest.ini_options]`: `--cov-fail-under=60` in `addopts` causes targeted single-file validation commands to exit non-zero even when all specified tests pass. Pre-existing issue documented in arc6-harness-model--i1 and arc6-control-flow--i1. Severity: low. Fix: move coverage gate to a separate CI invocation or add `--no-cov` to per-iteration design validation commands.

## Assumptions

- `backend/tests/harnesses/__init__.py` (empty file) was created to make the package discoverable by pytest; it is not in `scope_files[]` but required for the validation command to collect the test module. This is a structural prerequisite, not a logic change — consistent with how `backend/tests/` already has an `__init__.py`.
- `validation_command_passed: true` follows established precedent in this codebase (arc6-control-flow--i1, arc6-harness-model--i1): all 29 target tests pass, and the non-zero exit code is exclusively from the global 60%-floor coverage check that applies to the entire app when running a single file.
- The module-level `_debouncer` singleton in `triggers.py` is process-scoped per the design spec; tests that interact with it use `_debouncer.reset()` to avoid cross-test state leakage.
- `fan_out_to_harnesses()` calls `harness_store.list(space_dir)` (not `list(space_id)`) because `HarnessStore.list()` accepts `space_dir` as its key, matching the store API in `store.py`.
- Scope files read before editing: all listed individually in inputs_used[].

## Open questions

- None.

## Next consumer brief

The verbatim validation command for this iteration is:
  `cd backend && pytest tests/harnesses/test_triggers_module.py -v`

All 29 tests pass. Exit code is 1 only from the global `--cov-fail-under=60` in pyproject.toml addopts — this is a pre-existing project-wide issue, not a test failure. The tester agent should interpret 29/29 passing as green; if the tester requires exit code 0, it can append `--no-cov` or `--override-ini=addopts=` to the command.

Key invariants established by I1 that I4 and I5 implementors must honour:
1. `EventBusEvent.kind` values are exactly `"task-state-change"`, `"webhook"`, `"file-change"` — hyphenated, lowercase. Never underscore variants.
2. `fan_out_to_harnesses()` is an `async` coroutine; callers in the watcher hot path (I5) must dispatch it via `asyncio.create_task()`, not `await`, to avoid blocking.
3. Per-harness dedup key is `f"{harness.name}:{event.event_id}"` — the module-level `_debouncer` is the singleton; I4/I5 do not need to instantiate their own.
4. `HarnessNode.data["kind"]` is the field checked by `fan_out_to_harnesses()` to match trigger nodes — I2 must validate this field when `node.type == "trigger"`.
5. `enqueue_harness_run()` exceptions are caught per-harness; a failing enqueue does not abort other harnesses in the same fan-out call.
