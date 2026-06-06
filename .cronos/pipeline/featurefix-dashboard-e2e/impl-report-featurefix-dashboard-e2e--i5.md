---
cc_version: "1.0"
agent: pipeline-implementor
slug: featurefix-dashboard-e2e--i5
phase: impl
status: done
confidence: 0.92
inputs_used:
  - memory:observation_importlib_reload_test_pollution
  - memory:feedback_pipeline_narrow_k_coverage
  - memory:project_s4_worker_decompose_impl
  - .cronos/pipeline/featurefix-dashboard-e2e/design-report-featurefix-dashboard-e2e.md
  - backend/tests/test_feature_decompose_e2e.py
  - backend/tests/conftest.py
  - backend/app/api/features.py
  - backend/app/api/spaces.py
  - backend/app/api/tasks.py
  - backend/app/models.py
  - backend/app/storage.py
  - backend/app/feature_hooks.py
  - backend/app/feature_sync.py
  - backend/app/git_issues.py
  - backend/app/worker.py
  - backend/tests/test_spaces_feature_totals.py
  - .cronos/pipeline/featurefix-dashboard-e2e/impl-report-featurefix-dashboard-e2e--i2.md
  - backend/pyproject.toml
iteration_id: I5
files_changed:
  - backend/tests/test_features_e2e.py
validation_command_passed: true
out_of_scope_findings:
  - description: "GET /api/features (no trailing slash) returns HTTP 307 redirect to
      /api/features/ because FastAPI's router prefix /api/features with route @router.get('/')
      creates the canonical URL /api/features/. The httpx async test client does not
      follow redirects. Tests must use /api/features/ (with trailing slash). This is
      a minor API ergonomics issue; the Caddy reverse proxy in production handles the
      redirect transparently for browser clients."
    location: "backend/app/api/features.py:148"
    severity: low
outputs_produced:
  - .cronos/pipeline/featurefix-dashboard-e2e/impl-report-featurefix-dashboard-e2e--i5.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 28
  files_read: 18
  memory_hits: 3
  diff_lines_added: 470
  diff_lines_removed: 0
---

## Summary

Iteration I5 creates `backend/tests/test_features_e2e.py` — a 5-test async end-to-end pytest suite covering cross-cutting invariants for the features dashboard slice. The tests verify that (1) feature tasks are excluded from `GET /api/tasks`, (2) `GET /api/features/` returns features in the correct FeatureState lane, (3) `GET /api/spaces` returns `feature_totals` reflecting done features, (4) `gh_issue_close` is invoked when `issue_number` is set, and (5) a newly created backlog feature appears in `feature_totals.backlog`. All 5 tests pass with exit code 0. No `importlib.reload()` is used; the mock pattern mirrors `test_feature_decompose_e2e.py` exactly.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| backend/tests/test_features_e2e.py | created | +470 / 0 | 5 end-to-end tests: board exclusion, features board lane, feature_totals (done + backlog), issue-close lifecycle |

## Out-of-scope findings

- `GET /api/features` (no trailing slash) returns HTTP 307 to `/api/features/` because FastAPI's prefix `/api/features` + route `@router.get("/")` forms the canonical path `/api/features/`. The httpx async test client does not follow redirects automatically. Tests must use `/api/features/?space_id=...` (with trailing slash). Production Caddy proxy handles the redirect transparently. Location: `backend/app/api/features.py:148`. Severity: low.

## Assumptions

- `task_store.create(type="feature")` automatically sets `feature_state=FeatureState.BACKLOG` — confirmed in storage.py. No additional setup needed after creation.
- `POST /api/features` requires `space.git_repo_url` which the test space lacks. All tests use `task_store.create(type="feature")` directly for feature creation, consistent with I2 out_of_scope_findings.
- `enqueue_feature_decomposition` in `feature_hooks.py` reads `_worker_pool`; since `async_client` fixture injects only `app.state.worker_pool` (not `feature_hooks._worker_pool`), `enqueue_feature_decomposition` silently skips. For the e2e decompose path, `_run_feature_decompose` is called directly on a `Worker` instance constructed in the test, with `run_agent` patched via `unittest.mock.patch`.
- The `_inject_git_ops_stubs()` helper is copied verbatim from `test_feature_decompose_e2e.py`; it injects no-op stubs only when the attributes are absent (idempotent).
- Scope files read before editing: all listed individually in inputs_used[].

## Open questions

- None.

## Next consumer brief

Validation command to rerun (verbatim):
```
cd backend && pytest tests/test_features_e2e.py -v --override-ini="addopts="
```

Edge cases uncovered during implementation:
1. **Trailing slash on `/api/features/`** — the httpx async client does NOT follow the 307 redirect from `/api/features` to `/api/features/`. All GET /api/features/ calls in this test file use the explicit trailing slash. The test agent should be aware of this when writing additional tests for the features API.
2. **`feature_hooks._worker_pool` vs `app.state.worker_pool`** — `enqueue_feature_decomposition` reads the module-level `_worker_pool`, not `app.state.worker_pool`. In tests that use only `async_client` (and not the full worker stack), the enqueue call silently no-ops. This is by design for test isolation but means `POST /api/features/{id}/process` tests will not exercise the worker path without additionally patching `feature_hooks._worker_pool`.
3. Out-of-scope finding (low severity, location `backend/app/api/features.py:148`): the trailing-slash redirect should be documented or the router should consider `redirect_slashes=False` on the FastAPI app instance. Not in scope for I5.
