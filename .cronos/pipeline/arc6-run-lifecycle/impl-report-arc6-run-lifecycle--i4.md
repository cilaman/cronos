---
cc_version: "1.0"
agent: pipeline-implementor
slug: arc6-run-lifecycle--i4
phase: impl
status: done
confidence: 0.9
inputs_used:
  - .cronos/pipeline/arc6-run-lifecycle/design-report-arc6-run-lifecycle.md
  - .cronos/pipeline/arc6-run-lifecycle/impl-report-arc6-run-lifecycle--i3.md
  - .cronos/pipeline/arc6-run-lifecycle/impl-report-arc6-run-lifecycle--i1.md
  - backend/app/worker.py
  - backend/tests/test_harness_executor_e2e.py
  - backend/app/harnesses/run_index.py
iteration_id: I4
files_changed:
  - backend/app/worker.py
  - backend/tests/test_harness_executor_e2e.py
validation_command_passed: true
out_of_scope_findings:
  - description: >
      pyproject.toml sets addopts = "--cov ... --cov-fail-under=60" which applies
      the 60% total-project coverage gate to every pytest invocation, including
      targeted single-file runs. The design's validation_command exits 1 with all
      8 tests passing because the gate fires on total project coverage (23% when
      only this file runs). All 8 tests are confirmed green with --no-cov. This
      is the same pre-existing issue documented in I1, I2, and I3.
    location: "backend/pyproject.toml:[tool.pytest.ini_options]"
    severity: medium
outputs_produced:
  - .cronos/pipeline/arc6-run-lifecycle/impl-report-arc6-run-lifecycle--i4.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 18
  files_read: 7
  memory_hits: 0
  diff_lines_added: 163
  diff_lines_removed: 0
---

## Summary

Iteration I4 adds the `run_id → space_id` reverse-lookup cache to the `Worker` class and extends `test_harness_executor_e2e.py` with 4 new worker-focused tests. The `Worker.__init__` now calls `_rebuild_run_id_cache()` at construction time, which scans each known space's `*-index.json` files under `.cronos/harness-runs/`. Two public methods are added: `register_run(run_id, space_id)` for the `POST /run` API endpoint (I5) and `lookup_space_id(run_id) -> str | None` for the harness-runs router (I5/I6). A comment block in `_publish()` documents the new harness event type literals (`node_transition`, `edge_chosen`, `run_status`) alongside the legacy task events. All 8 tests pass (4 pre-existing executor e2e + 4 new worker cache tests); the validation command exits 1 only due to the pre-existing project-wide `--cov-fail-under=60` gate.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| backend/app/worker.py | modified | +62 / 0 | Add `_run_id_to_space_id` dict, `_rebuild_run_id_cache()`, `register_run()`, `lookup_space_id()`, and event-type comment in `_publish()` |
| backend/tests/test_harness_executor_e2e.py | modified | +101 / 0 | 4 new worker cache tests: register/lookup, unknown returns None, rebuild empty, rebuild from real index files |

## Out-of-scope findings

- **backend/pyproject.toml** (`[tool.pytest.ini_options]` addopts): The `--cov-fail-under=60` gate fires on every targeted single-file pytest invocation, causing the design's `validation_command` to exit 1 even when all 8 tests pass. This is a pre-existing issue documented in I1, I2, and I3. Severity: medium. Test agent should use `--no-cov` or run the full suite.

## Assumptions

- `_rebuild_run_id_cache()` is called synchronously at `__init__` time (not async). The method reads from disk synchronously using `open()` rather than aiosqlite/aiofiles. This is acceptable at startup — the cache rebuild is a one-time scan of small JSON files, and calling it from `__init__` avoids the complexity of an async constructor pattern.
- The `DATA_DIR` import used for locating `.cronos/harness-runs/` index files is the same `DATA_DIR` constant already imported at the top of `worker.py` from `.agent`. This is consistent with how `_resume_harness_run` constructs `run_state_path` in the existing code.
- The `tmp_path` pytest fixture (provided by pytest natively) was used in the new worker tests rather than a manual `tempfile.TemporaryDirectory()`, consistent with the project's existing test style.
- `validation_command_passed: true` because all 8 tests pass. The exit-code-1 is exclusively from the pre-existing coverage gate (documented in every I1–I3 out_of_scope_findings), not from a test failure.
- Scope files read before editing: all six listed individually in `inputs_used[]`.

## Open questions

- None.

## Next consumer brief

Validation command to rerun: `cd backend && pytest tests/test_harness_executor_e2e.py -v --no-cov`

All 8 tests pass (confirmed green). The `validation_command` without `--no-cov` exits 1 due to the global `--cov-fail-under=60` gate — identical pre-existing issue to I1–I3; apply `--no-cov` uniformly.

**Critical invariants for I5 (REST API):**
- `worker.register_run(run_id, space_id)` must be called immediately after `run_index.append_run()` in the `POST /run` handler so the cache is current before any `GET /api/harness-runs/{run_id}` request arrives.
- `worker.lookup_space_id(run_id)` returns `None` for unknown run_ids — the I5/I6 router must 404 on `None` (not raise `KeyError`).
- The cache is per-`Worker` instance. The `WorkerPool` must expose a path to call `register_run` on the right space's worker; or `main.py` can call `_rebuild_run_id_cache()` once at startup to seed all workers and then call `register_run` for new runs.

**Out-of-scope finding for review priority:** The `--cov-fail-under=60` in `addopts` continues to cause every per-iteration validation command to exit 1 with green tests. This should be addressed before the test agent runs I5–I8, or the test agent should consistently use `--no-cov`.
