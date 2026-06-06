---
cc_version: "1.0"
agent: tester
slug: featurefix-board-ui
phase: test
status: done
confidence: 0.9
inputs_used: []
outputs_produced:
  - .cronos/pipeline/featurefix-board-ui/test-report-featurefix-board-ui.md
blockers: []
next_consumer: user
gate_decision: fail
tests_added: 0
passed: 3131
failed: 8
errors: 15
coverage: 82.96
metrics:
  tool_calls: 9
  files_read: 0
  memory_hits: 0
  tests_run: 3154
---

## Summary

Gate run for goal `featurefix-board-ui` in space `cronos-development`. 3131 tests passed, 8 failed, 15 errored, 0 skipped. Coverage: 83.0%. Gate decision: **FAIL**.

## Gate result

| Metric | Value |
|--------|-------|
| Passed | 3131 |
| Failed | 8 |
| Errors | 15 |
| Skipped | 0 |
| Coverage | 83.0% |
| Exit code | 1 |
| Gate decision | **fail** |

## Failures

- `tests/test_feature_board.py::COLLECTION_ERROR`: ImportError: cannot import name 'FeatureState' from 'app.models' (or 'branch_exists_on_origin' from 'app.git_ops')
- `tests/test_feature_decompose_e2e.py::COLLECTION_ERROR`: ImportError: cannot import name 'FeatureState' from 'app.models' (or 'branch_exists_on_origin' from 'app.git_ops')
- `tests/test_feature_hooks_enqueue.py::COLLECTION_ERROR`: ImportError: cannot import name 'FeatureState' from 'app.models' (or 'branch_exists_on_origin' from 'app.git_ops')
- `tests/test_feature_model.py::COLLECTION_ERROR`: ImportError: cannot import name 'FeatureState' from 'app.models' (or 'branch_exists_on_origin' from 'app.git_ops')
- `tests/test_feature_numbering.py::COLLECTION_ERROR`: ImportError: cannot import name 'FeatureState' from 'app.models' (or 'branch_exists_on_origin' from 'app.git_ops')
- `tests/test_feature_persistence.py::COLLECTION_ERROR`: ImportError: cannot import name 'FeatureState' from 'app.models' (or 'branch_exists_on_origin' from 'app.git_ops')
- `tests/test_feature_serialization.py::COLLECTION_ERROR`: ImportError: cannot import name 'FeatureState' from 'app.models' (or 'branch_exists_on_origin' from 'app.git_ops')
- `tests/test_feature_sync_done_detection.py::COLLECTION_ERROR`: ImportError: cannot import name 'FeatureState' from 'app.models' (or 'branch_exists_on_origin' from 'app.git_ops')
- `tests/test_feature_sync_integration.py::COLLECTION_ERROR`: ImportError: cannot import name 'FeatureState' from 'app.models' (or 'branch_exists_on_origin' from 'app.git_ops')
- `tests/test_feature_sync_resolution.py::COLLECTION_ERROR`: ImportError: cannot import name 'FeatureState' from 'app.models' (or 'branch_exists_on_origin' from 'app.git_ops')
- `tests/test_feature_sync_waiting_resume.py::COLLECTION_ERROR`: ImportError: cannot import name 'FeatureState' from 'app.models' (or 'branch_exists_on_origin' from 'app.git_ops')
- `tests/test_feature_transitions.py::COLLECTION_ERROR`: ImportError: cannot import name 'FeatureState' from 'app.models' (or 'branch_exists_on_origin' from 'app.git_ops')
- `tests/test_git_ops_branch_exists.py::COLLECTION_ERROR`: ImportError: cannot import name 'FeatureState' from 'app.models' (or 'branch_exists_on_origin' from 'app.git_ops')
- `tests/test_worker_run_feature_decompose.py::COLLECTION_ERROR`: ImportError: cannot import name 'FeatureState' from 'app.models' (or 'branch_exists_on_origin' from 'app.git_ops')
- `tests/test_worker_run_one_branching.py::COLLECTION_ERROR`: ImportError: cannot import name 'FeatureState' from 'app.models' (or 'branch_exists_on_origin' from 'app.git_ops')
- `tests/test_feature_realizes.py::test_set_realizes`: tests/test_feature_realizes.py:26: in test_set_realizes     feat = await _make_feat(task_store, "Widget feature")            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ tests/test_feature_realizes.
- `tests/test_feature_realizes.py::test_realizing_items`: tests/test_feature_realizes.py:35: in test_realizing_items     feat = await _make_feat(task_store)            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^ tests/test_feature_realizes.py:12: in _make_feat     return a
- `tests/test_feature_realizes.py::test_validate_realizes`: tests/test_feature_realizes.py:52: in test_validate_realizes     feat = await _make_feat(task_store, "Feature")            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ tests/test_feature_realizes.py:12: in
- `tests/test_feature_realizes.py::test_set_realizes_clears`: tests/test_feature_realizes.py:71: in test_set_realizes_clears     feat = await _make_feat(task_store)            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^ tests/test_feature_realizes.py:12: in _make_feat     retu
- `tests/test_feature_storage_schema.py::test_feature_columns_present`: tests/test_feature_storage_schema.py:42: in test_feature_columns_present     assert col in cols, f"Expected column '{col}' missing from tasks table (found: {cols})" E   AssertionError: Expected column
- `tests/test_feature_storage_schema.py::test_ensure_db_schema_feature`: tests/test_feature_storage_schema.py:57: in test_ensure_db_schema_feature     assert col in info, f"Column {col} missing" E   AssertionError: Column feature_state missing E   assert 'feature_state' in
- `tests/test_feature_storage_schema.py::test_idx_tasks_space_realizes`: tests/test_feature_storage_schema.py:72: in test_idx_tasks_space_realizes     assert "idx_tasks_space_realizes" in indexes, ( E   AssertionError: Index idx_tasks_space_realizes not found. Existing: {'
- `tests/test_feature_storage_schema.py::test_migration_idempotent`: tests/test_feature_storage_schema.py:83: in test_migration_idempotent     assert "feature_state" in cols E   AssertionError: assert 'feature_state' in {'depends_on_json', 'id', 'parent_id', 'space_id'

## Assumptions

- Test suite is at `backend/tests/` (pytest) and `frontend/` (vitest when present).
- `tests_added: 0` — tester is a gate runner only; test authoring belongs to test-architect.
- `tool_calls: 9` is a fixed estimate; Bash-based agents cannot count tool invocations dynamically.
- `inputs_used: []` — the tester runs shell commands against the live test suite, not Read-tool file accesses; R4 is satisfied trivially (0 + 0 >= 0).
- 15 test modules failed to collect due to `ImportError: cannot import name 'FeatureState' from 'app.models'` and `cannot import name 'branch_exists_on_origin' from 'app.git_ops'`. These are counted as errors.
- 8 tests in `test_feature_realizes.py` and `test_feature_storage_schema.py` failed at runtime due to missing storage schema features.

## Open questions

- Why is `FeatureState` absent from `app.models` despite being referenced by 14 test files? The S1 data model impl (commit b511f1b) claims it was added.
- Why is `branch_exists_on_origin` absent from `app.git_ops`?

## Next consumer brief

Gate result: **FAIL** — 3131p / 8f / 15e, coverage 83.0%.
Fix 23 failing/errored test(s) before advancing the pipeline. See ## Failures for details.
