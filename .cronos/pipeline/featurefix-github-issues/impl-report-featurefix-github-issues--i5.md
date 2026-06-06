---
cc_version: "1.0"
agent: pipeline-implementor
slug: featurefix-github-issues--i5
phase: impl
status: done
confidence: 0.92
inputs_used:
  - memory:project_s1_data_model_impl
  - memory:project_s2_api_impl
  - memory:feedback_pipeline_narrow_k_coverage
  - memory:observation_worktree_main_vs_workspace
  - .cronos/pipeline/featurefix-github-issues/design-report-featurefix-github-issues.md
  - .cronos/pipeline/featurefix-github-issues/review-report-featurefix-github-issues--attempt1.md
  - .cronos/pipeline/featurefix-github-issues/impl-report-featurefix-github-issues--i3.md
  - .cronos/pipeline/featurefix-github-issues/impl-report-featurefix-github-issues--i4.md
  - backend/app/main.py
  - backend/app/api/features.py
  - backend/tests/test_features_api_mirror_fire.py
iteration_id: I5
files_changed:
  - backend/app/main.py
  - backend/app/api/features.py
  - backend/tests/test_main_lifespan_configure_store.py
  - backend/tests/test_features_api_mirror_fire.py
validation_command_passed: true
out_of_scope_findings:
  - description: >
      The StarletteDeprecationWarning about using `httpx` with `starlette.testclient`
      appears when TestClient is used. This is a dependency version mismatch (httpx vs
      httpx2) that affects the entire test suite, not just I5 scope.
    location: "backend/tests/ (global)"
    severity: low
outputs_produced:
  - .cronos/pipeline/featurefix-github-issues/impl-report-featurefix-github-issues--i5.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 38
  files_read: 11
  memory_hits: 4
  diff_lines_added: 291
  diff_lines_removed: 32
---

## Summary

I5 addresses the two blocking findings (F1, F2) from review attempt 1. F1 fix: added `from . import feature_hooks` and `feature_hooks.configure_store(task_store)` to `backend/app/main.py` lifespan startup immediately after `app.state.store = task_store`, ensuring `_task_store` is populated in production and `set_issue_refs` persists issue refs. F2 fix: changed `_fire_mirror` in `backend/app/api/features.py` from `async def` with `await` to a synchronous `def` that schedules `asyncio.create_task(mirror_feature_to_github(...))` with an error-logging `add_done_callback`, making all four mutating endpoints non-blocking on the gh subprocess. All 28 tests pass (6 lifespan smoke tests + 22 mirror call-site tests). The design note F3 (tester branch targeting) is an orchestrator-level concern not addressed here.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| backend/app/main.py | modified | +2 / 0 | F1: import feature_hooks + call configure_store(task_store) after app.state.store assignment |
| backend/app/api/features.py | modified | +35 / -32 | F2: convert _fire_mirror from async direct-await to sync fire-and-forget via asyncio.create_task with error-logging done-callback |
| backend/tests/test_main_lifespan_configure_store.py | created | +184 / 0 | F1 smoke tests: configure_store unit tests, source-level wiring checks, functional mocked-lifespan assertion |
| backend/tests/test_features_api_mirror_fire.py | modified | +70 / 0 (net) | F2 test flip: replace test_mirror_slow_mock_blocks_response with non-blocking assertion; add test_mirror_background_task_observably_executes |

## Out-of-scope findings

- `backend/tests/` (global) — `StarletteDeprecationWarning: Using 'httpx' with 'starlette.testclient' is deprecated; install 'httpx2' instead.` Appears across the entire test suite; not introduced by I5. Low severity, no action required in this iteration.

## Assumptions

- The feature branch worktree is at `/data/spaces/cronos-development/.cronos/workspaces/2026-06-03-1631-pipeline-implementor-features-fixes-s1-m` (branch `feature/features-and-fixes`, HEAD `aedd455`). All scope file edits were made in that worktree per `memory:observation_worktree_main_vs_workspace`.
- `asyncio_mode = "auto"` in `pyproject.toml` means async test functions run without explicit `@pytest.mark.asyncio` but I used it anyway for clarity. The `test_mirror_background_task_observably_executes` test uses `httpx.AsyncClient` and `await asyncio.sleep(0)` to yield to the event loop so background tasks can run.
- The mocked lifespan test (`test_configure_store_called_during_mocked_lifespan`) patches `watch_spaces_dir`, `auto_archive_loop`, `memory_prune_loop`, `discovery_refresh_loop`, `evolve_tools_loop`, and `cron_loop` to avoid the OS file watch limit (`OSError: OS file watch limit reached`) that would otherwise abort startup.
- `_fire_mirror` is now `def` (synchronous) instead of `async def`. All four call sites that previously `await`ed it now call it without `await`. The `asyncio.create_task()` call requires a running event loop, which is always present within a FastAPI async request handler.
- The non-blocking timing assertion uses `elapsed < 0.15s` for a mock that sleeps 0.2s, with a generous 50ms margin. This should be flake-free on any reasonable test hardware.
- Scope files read before editing: all listed individually in inputs_used[].

## Open questions

- None.

## Next consumer brief

**Verbatim validation command to rerun:**
```
cd backend && pytest tests/test_main_lifespan_configure_store.py tests/test_features_api_mirror_fire.py -v --override-ini="addopts="
```

All 28 tests pass (exit 0 with `--override-ini="addopts="`). Results: 6/6 lifespan tests + 22/22 mirror call-site tests.

**Edge cases for the test agent:**

1. `test_configure_store_called_during_mocked_lifespan` restores `fh._task_store = original` in a `finally` block. If the test suite imports `app.main` before this test runs, the module-level `_task_store` may already be `None`. The restore is defensive but essential to avoid cross-test pollution.

2. `test_mirror_non_blocking_response_with_slow_mock` asserts `elapsed < 0.15s` while mock sleeps 0.2s. If CI is extremely slow, this test could flake — the margin can be increased to 0.18 if needed.

3. `test_mirror_background_task_observably_executes` uses `asyncio.sleep(0)` to yield to the event loop once. If the background task needs more than one event loop iteration to execute, the sleep duration should be increased to `0.05`.

4. The `test_all_four_call_sites_use_single_funnel` test uses `inspect.getsource` and counts `_fire_mirror(` occurrences. With the F2 fix `_fire_mirror` is now a sync `def`, but it still appears 4 times in route code — the count is unchanged.

**Out-of-scope findings worth prioritising in the next review:**
- F3 from review attempt 1 (tester ran against wrong branch) — orchestrator must re-target the tester at `feature/features-and-fixes` HEAD before the next review attempt.
- The `StarletteDeprecationWarning` is benign but indicates a future need to switch from `httpx` to `httpx2` for `TestClient` usage.
