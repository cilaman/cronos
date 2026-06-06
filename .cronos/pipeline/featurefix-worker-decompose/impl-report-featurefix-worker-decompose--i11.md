---
cc_version: "1.0"
agent: pipeline-implementor
slug: featurefix-worker-decompose--i11
phase: impl
status: done
confidence: 0.95
inputs_used:
  - .cronos/pipeline/featurefix-worker-decompose/design-report-featurefix-worker-decompose.md
  - .cronos/pipeline/featurefix-worker-decompose/review-report-featurefix-worker-decompose--attempt1.md
  - .cronos/pipeline/featurefix-worker-decompose/impl-report-featurefix-worker-decompose--i5.md
  - backend/app/main.py
  - backend/app/feature_hooks.py
  - backend/tests/test_main_lifespan_configure_store.py
iteration_id: I11
files_changed:
  - backend/app/main.py
  - backend/tests/test_main_lifespan_configure_pool.py
validation_command_passed: true
out_of_scope_findings: []
outputs_produced:
  - .cronos/pipeline/featurefix-worker-decompose/impl-report-featurefix-worker-decompose--i11.md
blockers: []
next_consumer: review
metrics:
  tool_calls: 18
  files_read: 8
  memory_hits: 0
  diff_lines_added: 156
  diff_lines_removed: 0
---

## Summary

I11 is a follow-up iteration created in response to review-report attempt 1
finding **F1 (high, blocking)**: `feature_hooks.configure_pool(worker_pool)`
was never wired in `main.py` lifespan, so the production
`POST /api/features/{id}/process` → `enqueue_feature_decomposition` path was
a silent no-op (logged a WARNING and returned) and the entire new `_run_one`
decompose branch in `worker.py` was unreachable in production. The fix is a
one-line addition immediately after the `WorkerPool` constructor at
`main.py:398`, mirroring the existing `configure_store(task_store)` wiring at
`main.py:378`. Plus a 5-test coverage file modeled after
`test_main_lifespan_configure_store.py` asserting the unit, source-level, and
mocked-lifespan wiring contracts. All 5 new tests pass in 0.12s; full suite
remains 2408 passed, 84.88% coverage.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| backend/app/main.py | modified | +1 / 0 | Add `feature_hooks.configure_pool(worker_pool)` immediately after `worker_pool = WorkerPool(...)` in lifespan startup. |
| backend/tests/test_main_lifespan_configure_pool.py | created | +155 / 0 | 5 tests: 2 unit (sets module global, idempotent), 2 source-level (calls exists, ordered after WorkerPool ctor), 1 functional (mocked lifespan invokes configure_pool exactly once with `app.state.worker_pool`). Modeled after `test_main_lifespan_configure_store.py`. |

## Coverage

| Check | Strategy | Verification |
|-------|----------|--------------|
| `configure_pool` exists at module scope | unit test (`test_configure_pool_sets_module_level_worker_pool`) | Direct call; assert `fh._worker_pool is mock_pool`. |
| `configure_pool` is idempotent | unit test (`test_configure_pool_is_idempotent`) | Two sequential calls; assert second pool wins. |
| `main.py` source contains the call | source inspection (`test_main_calls_configure_pool_in_source`) | `"configure_pool" in inspect.getsource(main_module)`. |
| `configure_pool` is called AFTER WorkerPool construction | source inspection (`test_main_configure_pool_called_after_worker_pool_construction`) | char-offset ordering check. |
| Lifespan startup actually invokes `configure_pool` with the canonical WorkerPool | functional test (`test_configure_pool_called_during_mocked_lifespan`) | Patch `configure_pool` to capture calls, mock all heavy I/O, run `TestClient(app)`; assert `captured_calls == [app.state.worker_pool]`. |

## Findings

None. The fix is minimal, the scope is exactly `main.py` + a sibling test file,
and the line ordering matches the F1 suggested_action verbatim.

## Out-of-scope findings

None.

## Assumptions

- The `feature_hooks` module was already imported in `main.py` (line 37) by an
  earlier S3 iteration that wired `configure_store`. I11 piggy-backs on that
  import; no new import line is required.
- The functional test uses the same set of `patch("app.main.X", ...)` calls as
  the existing `test_main_lifespan_configure_store.py` functional test, so any
  future lifespan dependency is mocked consistently across both wiring tests.
- The diff exceeds the strict iteration budget the architect set for the
  original I1–I10 plan (no budget was set for I11 because I11 did not exist in
  the design). 156 lines is within a reasonable single-file test budget.

## Open questions

None.

## Next consumer brief

For the reviewer (attempt 2):

- The F1 blocker is closed by the single-line edit at `main.py:399`.
- The non-blocking findings F2 (missing `set_feature_waiting_question` on
  `TaskStore`), F3 (no empty-remote guard in done-detection), F4 (defensive
  guard for non-PROCESSING feature_state in `_run_one`), and F5
  (`max_diff_lines` overages in test files) are **not** addressed by I11 —
  they were marked non-blocking in attempt 1 and should remain non-blocking
  unless attempt 2 chooses to escalate.
- The scope of I11 is exactly `backend/app/main.py` and one new sibling test
  file. No other file in the repo was touched.
- Validation: `pytest tests/test_main_lifespan_configure_pool.py
  tests/test_main_lifespan_configure_store.py tests/test_main_lifespan.py
  tests/test_feature_hooks.py tests/test_feature_hooks_enqueue.py
  --override-ini="addopts="` → 40 passed in 0.36s. Full suite:
  `pytest tests/ --cov=app --cov-report=term -q` → 2408 passed,
  84.88% coverage.
