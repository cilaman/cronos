---
cc_version: "1.0"
agent: pipeline-implementor
slug: featurefix-api--i5
phase: impl
status: done
confidence: 0.95
inputs_used:
  - memory:s1_data_model_impl
  - memory:pipeline_narrow_k_coverage
  - memory:worktree_main_vs_workspace
  - .cronos/pipeline/featurefix-api/design-report-featurefix-api.md
  - .cronos/pipeline/featurefix-api/impl-report-featurefix-api--i1.md
  - .cronos/pipeline/featurefix-api/impl-report-featurefix-api--i2.md
  - .cronos/pipeline/featurefix-api/impl-report-featurefix-api--i4.md
  - backend/app/api/features.py
  - backend/app/models.py
  - backend/app/feature_hooks.py
  - backend/app/storage.py
  - backend/app/space_storage.py
  - backend/app/api/tasks.py
  - backend/tests/api/test_features_router_registration.py
iteration_id: I5
files_changed:
  - backend/app/api/features.py
  - backend/tests/api/test_features_create.py
validation_command_passed: true
out_of_scope_findings: []
outputs_produced:
  - .cronos/pipeline/featurefix-api/impl-report-featurefix-api--i5.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 26
  files_read: 13
  memory_hits: 3
  diff_lines_added: 524
  diff_lines_removed: 55
---

## Summary

Iteration I5 implements `POST /api/features` in `backend/app/api/features.py`, replacing the 501 stub with a real endpoint that: (1) returns 400 when `space.git_repo_url is None`, (2) returns 404 when the space does not exist, (3) calls `store.create(type=body.type, ...)` to allocate a `feature_key` and write the MD file, and (4) calls `_fire_mirror(task, space, "create")` — a single internal helper that funnels all mirror calls through `mirror_feature_to_github` (R13 compliance). Also adds `_build_feature_read()` and `_fire_mirror()` helpers plus the necessary imports (`StorageError`, `UnknownSpace`, `HTTPException`, `mirror_feature_to_github`). All 16 tests in the new `test_features_create.py` pass in 0.36 s.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| backend/app/api/features.py | modified | +64 / -55 | Replace POST / stub with real implementation; add _fire_mirror and _build_feature_read helpers; add imports |
| backend/tests/api/test_features_create.py | created | +460 / 0 | 16 tests covering 201 success, FEAT/FIX key formats, mirror call_count (R13), 400 (no git), 404 (missing space), 422 (bad schema), 401 (unauth), StorageError → 400 |

## Out-of-scope findings

- None.

## Assumptions

- `store.create(type="feature", ...)` already allocates `feature_key` and sets `feature_state=FeatureState.BACKLOG` via the S1-implemented `_next_feature_key()` branch — confirmed by reading `storage.py` lines 904-932.
- `_build_feature_read()` extracts only the fields present in `FeatureRead.model_fields` via a dict comprehension — this avoids forward-reference issues since `FeatureRead` is a standalone model (not a `Task` subclass), as noted in the I1 impl-report.
- `_fire_mirror()` uses `# type: ignore[arg-type]` on the `reason` parameter because `mirror_feature_to_github` is typed with `TYPE_CHECKING`-only imports; at runtime mypy is not run, so this is safe.
- The test `app_client` fixture wires `app.state.space_store` directly (not via lifespan) following the identical pattern in `test_features_router_registration.py`.
- Branch preflight confirmed `feature/features-and-fixes` before any edits.
- Scope files read before editing: all listed individually in inputs_used[].

## Open questions

- None.

## Next consumer brief

Rerun validation with: `cd backend && pytest tests/api/test_features_create.py -v --override-ini="addopts="`

All 16 tests passed in 0.36 s on first run. No fix iteration was required.

Edge cases uncovered during implementation:
- `_build_feature_read()` uses `FeatureRead.model_fields` key filtering — if future iterations add fields to `FeatureRead` that do not exist on `Task`, this helper will silently omit them. Downstream I7 and I9 that also use `_build_feature_read()` should verify the field set remains complete or extend the helper.
- The `test_storage_error_returns_400` test patches `StorageError` from `app.storage` directly; it confirms that mirror is NOT called when `store.create()` raises (R13 zero-mirror-on-failure guarantee).
- I8/I9/I11 must route their mirror calls through the same `_fire_mirror()` helper already present in `api/features.py` — adding a second call site would break R13.

No out-of-scope findings to prioritize.
