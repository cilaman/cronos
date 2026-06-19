---
agent_mode: auto
agent_model: sonnet
claude_session_id: 985eb9e2-6059-49d7-9021-e16fdd67484d
created_at: '2026-06-07T11:29:31Z'
depends_on:
- 2026-06-07-1129-write-tests-feature-sync-untested-paths
feature_key: null
feature_state: null
id: 2026-06-07-1129-write-tests-api-error-paths-hooks-config
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-07-1129-feature-module-test-coverage-gaps
pending_messages: []
pr_url: null
priority: 3
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: 'Write tests: API error paths + hooks config (P1-B, P1-C, P2-A through P2-E,
  P2-H)'
type: task
updated_at: '2026-06-16T06:30:16Z'
waiting_question: null
---

# Brief

Write missing tests for `backend/app/api/features.py` and `backend/app/feature_hooks.py`
error paths.

Coverage target: features.py lines 78, 139, 225, 234, 266, 276-277, 324, 352, 374;
feature_hooks.py line 53.

## Tests to write

**P1-B — _log_mirror_error callback** (features.py:78)
File: `tests/api/test_features_create.py` (add test)
Test: patch `mirror_feature_to_github` to raise an exception. Trigger a feature state mutation,
run the event loop one tick. Assert the error is logged. Line hit: 78.

**P1-C — DELETE 501 endpoint** (features.py:374)
File: `tests/api/test_features_delete.py` (new file)
Test:
```python
def test_delete_feature_returns_501(app_client):
    resp = app_client.delete("/api/features/feat-001", auth=("user", "pass"))
    assert resp.status_code == 501
```

**P2-A — StorageError on create** (features.py:139)
File: `tests/api/test_features_create.py`
Patch `store.create` to raise `StorageError("disk full")`. Assert POST returns 400 with the
error message. Line hit: 139.

**P2-B — Space not found after feature found (3 endpoints)** (features.py:225, 266, 352)
File: `tests/api/test_features_state_transition.py`, `tests/api/test_features_edit.py`,
`tests/api/test_features_process.py`
For each: patch `space_store.get` to return None after feature is found. Assert 404 is returned.
Lines hit: 225, 266, 352.

**P2-C — TaskNotFound TOCTOU in state-change** (features.py:234)
File: `tests/api/test_features_state_transition.py`
Patch `store.transition_feature` to raise `TaskNotFound`. Assert PATCH /feature-state returns 404.
Line hit: 234.

**P2-D — TaskNotFound + StorageError in patch_feature** (features.py:276-277)
File: `tests/api/test_features_edit.py`
Patch `store.update` to raise `TaskNotFound` → assert 404.
Patch `store.update` to raise `StorageError` → assert 400.
Lines hit: 276-277.

**P2-E — feature not found after set_realizes** (features.py:324)
File: `tests/api/test_features_realize.py`
Patch second `store.get(feature_id)` (after set_realizes succeeds) to return None. Assert 404.
Line hit: 324.

**P2-H — configure_store not tested** (feature_hooks.py:53)
File: `tests/test_feature_hooks_enqueue.py`
Add test mirroring the existing `test_configure_pool_sets_module_level_pool`:
```python
def test_configure_store_sets_module_level_store():
    from app.feature_hooks import configure_store
    mock_store = MagicMock()
    configure_store(mock_store)
    # Verify _task_store is set at module level
    import app.feature_hooks as fh
    assert fh._task_store is mock_store
```
Line hit: 53.

## Acceptance

- All new tests pass individually
- `cd backend && pytest tests/ -x -q` — full suite passes
- Coverage on `api/features.py` reaches ≥96% and `feature_hooks.py` reaches ≥99%

After tests pass, run /goal-task-commit

# History

```
2026-06-09T06:05:17Z [agent]
I'll explore the relevant source files and existing tests before writing the new tests.

Let me read the actual file contents to write accurate tests.

Now let me read the existing test files to understand patterns used:

Now let me read a few more files to understand the test for realize and process:

Let me read the process test file to understand the full pattern:

Let me check the storage exceptions to understand the class hierarchy:

I have all the information needed. `UnknownSpace` is a subclass of `StorageError`, so line 139 (the `except UnknownSpace:` handler) is never hit because existing tests raise `StorageError` directly (caught by line 140). Now I'll write all the required tests.

Now I have all the information needed. Let me write all the tests at once.

Now create the DELETE test file (P1-C):

Now add P2-B and P2-C tests to `test_features_state_transition.py`:

Now add P2-B and P2-D tests to `test_features_edit.py`:

Now add P2-B test to `test_features_process.py`. Let me find a good insertion point:

Now add P2-E test to `test_features_realize.py`. Let me find the end of the file:

Now add P2-H test to `test_feature_hooks_enqueue.py`:

All tests are written. Now let's run the test suite to verify:

The P1-B test is failing because `caplog` doesn't capture logs from asyncio done callbacks in async tests. Let me switch to patching the module-level `log` object directly:

The `patch("app.api.features.log")` approach isn't intercepting the callback's log call. Let me use a custom `logging.Handler` attached directly to the real logger instead:

The asyncio done callback fires in the NEXT event loop iteration after the task completes. I need two `await asyncio.sleep(0)` calls: one to run the task, one to run the done callbacks:

The P1-B test passes. Now let's run all targeted test files:

All 106 tests pass. Now let's run the full test suite:

All 2523 tests pass with 85.13% coverage. Let me verify coverage for the specific target files:

Both `api/features.py` and `feature_hooks.py` are at **100% coverage**. Now let's run the goal-task-commit skill as instructed:

The feature branch is checked out in another workspace. I'll copy the changed test files to that worktree and commit from there:

The commit is pushed. Now let me finalize the task:

## Step 1 — Verify completion

All requirements were met:
- **P1-B**: `test_log_mirror_error_callback_logs_on_exception` — tests `_log_mirror_error` callback logs ERROR when mirror raises (line 78). Required two `await asyncio.sleep(0)` calls: one to run the asyncio task, one to run the done callbacks.
- **P1-C**: `test_features_delete.py` — DELETE returns 501 (line 374)
- **P2-A**: `test_unknown_space_on_create_returns_404` + `test_storage_error_on_create_includes_message` — covers line 139 (UnknownSpace) and message propagation
- **P2-B**: Space-not-found 404 added to state_transition, edit, and process tests (lines 225, 266, ~358)
- **P2-C**: `test_patch_feature_state_transition_raises_task_not_found_returns_404` — TOCTOU in state-change (line 234)
- **P2-D**: `test_patch_feature_storage_error_from_update_returns_400` — StorageError from update (lines 276-277)
- **P2-E**: `test_realize_feature_not_found_after_set_realizes_returns_404` — feature gone after set_realizes (line 324)
- **P2-H**: `test_configure_store_sets_module_level_store` — configure_store test (line 53)

Full suite: **2523 passed**, 85.13% coverage. `api/features.py`: **100%**, `feature_hooks.py`: **100%**. Committed and pushed to `feature/feature-module-test-coverage-gaps` (commit `69d2482`).

## Step 3 — Handle git

Already completed via goal-task-commit — commit `69d2482` pushed to `feature/feature-module-test-coverage-gaps`.

## Step 4 — Write memory

MEMORY[observation]: asyncio done callbacks fire via `call_soon` AFTER the task completes — they run in the NEXT event loop iteration. Testing `_log_mirror_error` requires `await asyncio.sleep(0)` twice: first to run the task, second to run the scheduled callbacks. Single sleep is insufficient.

MEMORY[observation]: `patch("app.api.features.log")` does NOT intercept logs from asyncio done callbacks defined inside the same module — use a custom `logging.Handler` attached to `logging.getLogger("app.api.features")` instead for reliable capture.

MEMORY[fact]: Feature module test coverage raised to 100% for `api/features.py` and `feature_hooks.py`. 7 test files modified/created in `backend/tests/api/` and `backend/tests/`. Key new file: `test_features_delete.py`. Commit 69d2482 on `feature/feature-module-test-coverage-gaps`.

Memory written. Returning to task-finalize.

MEMORY[observation]: asyncio done callbacks fire via `call_soon` AFTER the task completes — they run in the NEXT event loop iteration. Testing `_log_mirror_error` requires `await asyncio.sleep(0)` twice: first to run the task, second to run the scheduled callbacks. Single sleep is insufficient. Also: `patch("app.api.features.log")` does NOT intercept the real logger used by the callback — use a custom `logging.Handler` on `logging.getLogger("app.api.features")` instead.

MEMORY[fact]: Feature module test coverage raised to 100% for `api/features.py` and `feature_hooks.py`. 7 test files modified/created. Key new file: `backend/tests/api/test_features_delete.py`. Commit `69d2482` on `feature/feature-module-test-coverage-gaps`.

STATUS: DONE
```
