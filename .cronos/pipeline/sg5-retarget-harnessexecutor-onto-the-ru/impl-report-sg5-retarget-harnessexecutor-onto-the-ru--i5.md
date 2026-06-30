---
cc_version: "1.0"
agent: pipeline-implementor
slug: sg5-retarget-harnessexecutor-onto-the-ru--i5
phase: impl
status: done
confidence: 0.9
inputs_used:
  - .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/design-report-sg5-retarget-harnessexecutor-onto-the-ru.md
  - .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/impl-report-sg5-retarget-harnessexecutor-onto-the-ru--i1.md
  - .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/impl-report-sg5-retarget-harnessexecutor-onto-the-ru--i3.md
  - .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/impl-report-sg5-retarget-harnessexecutor-onto-the-ru--i4.md
  - backend/app/run_executor.py
  - backend/app/harnesses/run_state.py
  - backend/app/harnesses/compiler.py
  - backend/app/harnesses/executor_adapter.py
  - backend/app/harnesses/state_mapping.py
  - backend/app/harnesses/executor.py
  - packages/delivery-workflow/runner/core.py
iteration_id: I5
files_changed:
  - backend/app/run_executor.py
  - backend/tests/test_run_executor_runner_flag.py
validation_command_passed: true
out_of_scope_findings:
  - description: >
      The design report body says "RunState.executor_variant (new optional field) lives
      in backend/app/harnesses/run_state.py (edited by I5)" but run_state.py is NOT in
      I5's scope_files[]. The implementation avoids this scope violation by storing
      executor_variant as an extra top-level JSON key via _write_executor_variant()
      and reading it back via _read_executor_variant(), bypassing RunState.to_dict()/from_dict().
      This is backward-compatible: old files without the key return the default 'bfs'.
      If a downstream iteration needs RunState.executor_variant as a declared field,
      it should add run_state.py to its scope_files.
    location: "backend/app/harnesses/run_state.py"
    severity: low
outputs_produced:
  - .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/impl-report-sg5-retarget-harnessexecutor-onto-the-ru--i5.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 28
  files_read: 11
  memory_hits: 0
  diff_lines_added: 858
  diff_lines_removed: 1
---

## Summary

I5 implements the `CRONOS_HARNESS_RUNNER` env-flag branch in `backend/app/run_executor.py`. Two module-level helpers (`_read_executor_variant`, `_write_executor_variant`) persist the chosen executor variant (`'bfs'` or `'runner'`) as an extra key in the run-state JSON file, providing backward-compatibility with pre-SG5 files (missing key defaults to `'bfs'`). `execute_harness_run_body` now reads the flag only on the initial-run path and stores the variant; on resume it reads the stored variant — never the current env flag. A new private method `_execute_harness_run_runner` implements the runner path (compile → HarnessExecutorAdapter → runner.core.run → state_mapping → finalize). The old `HarnessExecutor` import and `.execute()` invocation are preserved verbatim under the default `'bfs'` branch. All 19 tests pass.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| backend/app/run_executor.py | modified | +333 / -1 | Add _read/_write_executor_variant helpers, CRONOS_HARNESS_RUNNER flag branch in execute_harness_run_body, and _execute_harness_run_runner runner path |
| backend/tests/test_run_executor_runner_flag.py | created | +525 / 0 | 19 tests covering helpers, backward-compat, dispatch (BFS/runner), and four resume combinations |

## Out-of-scope findings

- The design report body says `RunState.executor_variant` lives in `backend/app/harnesses/run_state.py` (edited by I5), but that file is NOT in I5's `scope_files[]`. Implementation avoids the scope violation by persisting `executor_variant` as an extra JSON key (outside the `RunState` dataclass) via `_write_executor_variant`/`_read_executor_variant`. This is fully backward-compatible. If a downstream iteration needs `RunState.executor_variant` as a declared dataclass field, it should add `backend/app/harnesses/run_state.py` to its `scope_files[]`. (Location: `backend/app/harnesses/run_state.py`, severity: low)

## Assumptions

- `backend/app/harnesses/run_state.py` is NOT in scope_files for I5. The `executor_variant` is stored as an extra JSON key alongside the RunState JSON rather than as a declared field. `RunState.from_dict()` ignores unknown keys; `RunState.to_dict()` (via `asdict()`) does not emit it. `_write_executor_variant()` patches the file atomically after every read/write cycle.
- `asyncio.coroutine` was removed in Python 3.12. Tests use `AsyncMock` and plain `async def` fixtures instead.
- `_data_dir()` is patched via `patch("app.run_executor.RunExecutor._data_dir", return_value=tmp_path)` in tests so run-state file paths resolve under `tmp_path`.
- Scope files read before editing: all 11 listed individually in inputs_used[].

## Open questions

- None. All three analyst OQs were resolved in the design report Assumptions section.

## Next consumer brief

**Validation command to rerun**: `cd backend && pytest tests/test_run_executor_runner_flag.py -v --override-ini="addopts="`

**Edge cases uncovered during implementation**:

1. The design says `RunState.executor_variant` is "added to RunState in run_state.py (edited by I5)" but `run_state.py` is absent from I5's `scope_files[]`. The implementation works around this by persisting the variant outside the dataclass (extra JSON key). If I6/I7 depend on `RunState.executor_variant` as a declared field, run_state.py must be added to their scope_files.

2. `_execute_harness_run_runner` receives a `HarnessExecutorAdapter` whose `state` attribute is a `_StateOps` instance (not a `StateOps` protocol object from the runner's perspective). `runner.core.run()` accepts `state_ops=adapter.state` — this works because `_StateOps` exposes `.read()` and `.write()` matching the protocol.

3. In `_execute_harness_run_runner`, after `runner_run()` completes and `workflowstate_to_runstate()` produces a `RunState`, `save_atomic()` is called (which uses `asdict()` and omits `executor_variant`). The subsequent `_write_executor_variant()` call re-adds it. The two-step write is atomic at file level (both use `os.replace`); a crash between them would leave the file without `executor_variant`, which `_read_executor_variant()` handles by defaulting to `'bfs'` — a safe degradation.

4. The `_publish_cb` callback in the runner path uses `loop.create_task()` (fire-and-forget) since `runner.core.run()` is synchronous. Tests that need to assert on published events must patch `_publish_cb` or the adapter's telemetry.
