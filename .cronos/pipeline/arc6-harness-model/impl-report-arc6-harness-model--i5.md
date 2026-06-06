---
cc_version: "1.0"
agent: pipeline-implementor
slug: arc6-harness-model--i5
phase: impl
status: done
confidence: 0.95
inputs_used:
  - memory:project_architecture_key_modules
  - memory:project_pipeline_implementor_agent
  - .cronos/pipeline/arc6-harness-model/design-report-arc6-harness-model.md
  - .cronos/pipeline/arc6-harness-model/impl-report-arc6-harness-model--i4.md
  - backend/app/main.py
  - backend/app/auth.py
  - backend/app/api/harnesses.py
  - backend/app/harnesses/__init__.py
  - backend/tests/conftest.py
  - backend/tests/test_auth.py
  - backend/tests/test_api_misc.py
iteration_id: I5
files_changed:
  - backend/app/main.py
  - backend/tests/test_harness_wiring.py
validation_command_passed: true
out_of_scope_findings: []
outputs_produced:
  - .cronos/pipeline/arc6-harness-model/impl-report-arc6-harness-model--i5.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 22
  files_read: 11
  memory_hits: 2
  diff_lines_added: 150
  diff_lines_removed: 0
---

## Summary

I5 wires the `HarnessStore` and `harnesses_router` into `backend/app/main.py` and
provides 6 integration tests in `backend/tests/test_harness_wiring.py` that verify
both auth wiring (unauthenticated → 401) and DI ordering (authenticated → 200/404,
not 500). Two import lines were added to `main.py` (router + HarnessStore), three
lines initialize `HarnessStore()` and assign it to `app.state.harness_store` inside
the `lifespan` context (after `memory_store`, before the worker pool), and one line
registers the router with `_auth` dependencies. All 6 tests pass.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| backend/app/main.py | modified | +6 / 0 | Import harnesses_router + HarnessStore; initialize harness_store in lifespan; register router with _auth |
| backend/tests/test_harness_wiring.py | created | +144 / 0 | 6 integration tests: 401 on unauth list/post, 200 on authed list of existing space, 404 on authed nonexistent space, HarnessStore isinstance check, 200 when auth disabled |

## Out-of-scope findings

- None.

## Assumptions

- `conftest.py` does not set `app.state.harness_store`, so `test_harness_wiring.py`
  injects it via an `autouse` fixture (`_inject_harness_store`) that creates a fresh
  `HarnessStore()` for each test and cleans up afterwards. This is consistent with the
  pattern in `test_api_misc.py` which also sets `app.state.*` directly.
- The `HarnessStore` constructor requires no arguments (confirmed by reading
  `backend/app/harnesses/store.py` in I3 — data is loaded lazily per space_dir call).
- Initialization order: `harness_store` is placed after `memory_store` and before
  `worker_pool` in `lifespan`. This is safe because `HarnessStore` has no dependencies
  on any other store.
- The `_inject_harness_store` fixture targets the `harness_store` attribute specifically
  so it does not interfere with other `app.state` attributes set by the `async_client`
  fixture from `conftest.py`.
- Scope files read before editing: all listed individually in inputs_used[].

## Open questions

- None.

## Next consumer brief

Verbatim validation command to re-run: `cd backend && pytest tests/test_harness_wiring.py -v`

All 6 tests pass (exit 0). Key details for the test agent:

- `test_harness_store_on_app_state` checks `isinstance(app.state.harness_store, HarnessStore)`;
  if the `_inject_harness_store` fixture ever fails to run, this will fail as an AttributeError,
  not an assertion error — watch for that distinction in failure output.
- The autouse `_inject_harness_store` fixture deletes `app.state.harness_store` after each test
  to avoid cross-test leakage. If the lifespan context is activated (e.g., by a future test
  that uses `TestClient` with `lifespan=True`), the store will be re-initialized from `main.py`
  automatically.
- Edge case uncovered: the `conftest.py` `async_client` fixture does not set `harness_store`
  on `app.state`. Any future test that uses `async_client` and hits a harnesses endpoint without
  first injecting `harness_store` will get a 500 (AttributeError on `request.app.state.harness_store`).
  The I6 acceptance test author must either extend conftest.py or add a local `autouse` fixture
  similar to `_inject_harness_store`.
- No out_of_scope_findings to prioritize.
