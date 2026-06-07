# Features Test Coverage Audit

Generated: 2026-06-07
Branch: cronos/2026-06-07-1049-test-coverage-audit

## Coverage Summary

Coverage measured against all 301 feature-scoped tests (full suite: 2466 tests).

| Module | Coverage % | Uncovered Lines |
|--------|-----------|-----------------|
| `app/api/features.py` | 93% | 78, 139, 225, 234, 266, 276–277, 324, 352, 374 |
| `app/feature_hooks.py` | 98% | 53 |
| `app/feature_state.py` | 100% | — |
| `app/feature_sync.py` | 86% | 51, 100–110, 130–132, 205–210, 244, 249–250 |

## Critical Untested Scenarios

### BUG: `set_feature_waiting_question` does not exist in `storage.py`

`feature_sync.py:100` calls `await store.set_feature_waiting_question(feature_id, waiting_q)`.
This method **does not exist** in `storage.py`. In production, every time a realizing goal
transitions to WAITING, this call throws `AttributeError`, which is caught at line 107 and
silently logged. The waiting question is never persisted on the feature.

**Impact:** Feature cards in WAITING state never surface the blocking question to the user.
The AttributeError catch (lines 107–115) exists precisely to paper over this gap, but it
means the bug is silent — no test exercises this recovery path.

Lines 100–110 are 100% uncovered: no test sets `waiting_question` on a goal before calling
`propagate_to_feature`, so the `if waiting_q is not None:` guard is never True.

---

## Missing Tests (P1)
*(Real bugs hidden by absence of coverage)*

### P1-A: `set_feature_waiting_question` AttributeError recovery (feature_sync.py:107–115)

**Scenario:** A realizing goal enters WAITING with a non-null `waiting_question`.
`propagate_to_feature` calls the non-existent `store.set_feature_waiting_question()`.
The AttributeError is caught, and the question is dropped silently.

**What's missing:** A test that:
1. Creates a goal with `waiting_question = "Which provider?"`.
2. Calls `propagate_to_feature(goal.id, store, pool=None)`.
3. Asserts the feature IS in WAITING state (transition succeeds despite AttributeError).
4. Asserts the feature's `waiting_question` is NOT populated (documents the current
   broken behavior and alerts when the storage method is eventually added).

**Files:** `tests/test_feature_sync_waiting_resume.py`
**Lines not hit:** 100–110

---

### P1-B: `_log_mirror_error` callback fires on mirror failure (features.py:75–84)

**Scenario:** `_fire_mirror` schedules `mirror_feature_to_github` as a background asyncio task.
If the coroutine raises, line 78 (`log.error(...)`) fires via the done-callback.

**What's missing:** A test that patches `mirror_feature_to_github` to raise, runs the asyncio
event loop one turn to let the background task settle, and asserts the error is logged.

**File:** `tests/api/test_features_create.py` or `test_features_state_transition.py`
**Line not hit:** 78

---

### P1-C: DELETE endpoint returns 501 (features.py:374)

**Scenario:** `DELETE /api/features/{id}` is a stub returning 501 Not Implemented.
No test documents or asserts this behavior.

**What's missing:**
```python
def test_delete_feature_returns_501(app_client):
    resp = app_client.delete("/api/features/feat-001", auth=("user", "pass"))
    assert resp.status_code == 501
```

**File:** `tests/api/` (new file `test_features_delete.py` or added to `test_features_read.py`)
**Line not hit:** 374

---

### P1-D: `propagate_to_feature` with non-existent item_id (feature_sync.py:51)

**Scenario:** `propagate_to_feature` is called with a task_id that is not in the store.
`_find_root` returns None (line 244), and `propagate_to_feature` returns early at line 51.

**What's missing:** A test calling `propagate_to_feature("nonexistent-id", store, pool=None)`
and asserting no exception is raised and no state is mutated.

**File:** `tests/test_feature_sync_resolution.py`
**Lines not hit:** 51, 244

---

### P1-E: `_find_root` cycle guard (feature_sync.py:249–250)

**Scenario:** A task has a parent chain longer than 50 hops (cycle or pathological depth).
`_find_root` logs a warning and returns None rather than looping forever.

**What's missing:** A test that constructs a 51-hop chain (mocked store returning next
parent on each get) and asserts `_find_root` returns None and logs a warning.

**File:** `tests/test_feature_sync_resolution.py`
**Lines not hit:** 249–250

---

## Missing Tests (P2)
*(Lower-risk gaps that reduce confidence in error handling)*

### P2-A: StorageError on feature create (features.py:139)

`create_feature` catches `StorageError` and returns 400. The only StorageError exercised
by current tests is the `UnknownSpace` path (404). No test triggers a generic storage
failure during `store.create()`.

**File:** `tests/api/test_features_create.py`
**Line not hit:** 139

---

### P2-B: Space not found after feature found — three endpoints

Three endpoints verify the feature exists, then look up its space via `space_store.get()`.
None test the case where the space has been deleted between the two lookups:

| Endpoint | Line | Description |
|----------|------|-------------|
| `PATCH /feature-state` | 225 | space lookup after feature found |
| `PATCH /` (edit) | 266 | space lookup after feature found |
| `POST /process` | 352 | space lookup after feature found |

**File:** respective test files in `tests/api/`
**Lines not hit:** 225, 266, 352

---

### P2-C: TaskNotFound from `transition_feature` in state-change (features.py:234)

`patch_feature_state` does a pre-check `store.get()`, then calls `store.transition_feature()`.
If the task is deleted between the two calls, `transition_feature` raises `TaskNotFound`
(line 234 path). No test exercises this TOCTOU gap.

**File:** `tests/api/test_features_state_transition.py`
**Line not hit:** 234

---

### P2-D: TaskNotFound + StorageError in patch_feature (features.py:276–277)

Similar TOCTOU gap: `patch_feature` calls `store.update()` which may throw `TaskNotFound`
or `StorageError` if the task disappears or a constraint is violated after the initial lookup.

**File:** `tests/api/test_features_edit.py`
**Lines not hit:** 276–277

---

### P2-E: feature not found after set_realizes in patch_realize (features.py:324)

`patch_realize` calls `store.set_realizes(body.item_id, body.feature_id)`, then does a
post-op `store.get(feature_id)`. If the feature was deleted after `set_realizes` succeeds,
line 324 raises 404. No test covers this.

**File:** `tests/api/test_features_realize.py`
**Line not hit:** 324

---

### P2-F: ACTIVE-resume concurrent race in propagate_to_feature (feature_sync.py:130–132)

When a realizing goal resumes from WAITING → ACTIVE, `propagate_to_feature` tries to
transition the feature WAITING → PLANNED. If two concurrent calls race, the second gets
`InvalidTransition` (lines 130–132), which should be silently swallowed.

**What's tested:** The WAITING concurrent race (feature already in WAITING) IS tested at
`test_concurrent_waiting_race_is_idempotent`. The PLANNED concurrent race (feature already
in PLANNED on resume) is NOT tested.

**File:** `tests/test_feature_sync_waiting_resume.py`
**Lines not hit:** 130–132

---

### P2-G: Done-detection DONE concurrent race (feature_sync.py:205–210)

When done-detection fires (all items terminal, branch absent), two goroutines could
race to call `transition_feature(feature_id, DONE)`. The second gets `InvalidTransition`
(lines 205–210). The `except InvalidTransition` branch is not tested.

**File:** `tests/test_feature_sync_done_detection.py`
**Lines not hit:** 205–210

---

### P2-H: `configure_store` not tested (feature_hooks.py:53)

`configure_pool` has two dedicated tests in `test_feature_hooks_enqueue.py`, but
`configure_store` has zero tests. Line 53 (`_task_store = store`) is never executed.

**What's missing:** A test mirroring `test_configure_pool_sets_module_level_pool` for
`configure_store`.

**File:** `tests/test_feature_hooks_enqueue.py`
**Line not hit:** 53

---

## Scenario Checklist (A–H from brief)

| Scenario | Status | Notes |
|----------|--------|-------|
| A. Decomposition failure sticks feature in WAITING | **COVERED** | `test_worker_run_feature_decompose.py` covers crash, BLOCKED, WAIT, zero-items |
| B. Zero realizing items after decomposition → WAITING | **COVERED** | `test_success_zero_items_transitions_to_waiting` |
| C. Feature→WAITING via propagate_to_feature + waiting_question | **PARTIAL** | WAITING transition covered; waiting_question copy (lines 100–110) uncovered; `set_feature_waiting_question` doesn't exist (P1-A) |
| D. Race guard on `_next_feature_key` | **PARTIAL** | Per-space isolation tested; no concurrent-creation stress test |
| E. GitHub mirror failure (no CLI / no remote) | **COVERED** | `test_exception_swallowed_returns_none` + `test_git_repo_url_none_writes_md` |
| F. Space isolation: space A features not in space B board | **PARTIAL** | `test_feature_board_called_with_space_id` checks correct arg; no cross-space isolation integration test |
| G. Delete endpoint 501 response | **MISSING** | No test — P1-C |
| H. validate_realizes rejection cases | **COVERED** | Self-realize, cross-space, wrong-type all tested in `test_features_realize.py` |

---

## Test Quality Notes

### Strengths

- **Worker decompose branch coverage is excellent.** `test_worker_run_feature_decompose.py`
  covers all 5 outcome branches systematically, including fault-tolerance (finalize_run fails,
  transition_feature fails). This is the highest-risk path and it is well exercised.

- **Mirror hook is well tested.** `test_feature_hooks_mirror.py` covers the R6 ordering
  constraint, stale-issue-number clearing, gh_issue_close conditional, and exception swallowing.
  453 lines / 12 tests, all meaningful contract-level assertions.

- **validate_realizes coverage is complete.** All four rejection conditions (self-ref,
  cross-space, wrong type, item-not-found) have dedicated tests with correct HTTP status codes.

### Weaknesses

- **Error-path TOCTOU gaps.** The pattern of "pre-check then mutate" in four endpoints
  (feature-state patch, edit patch, process, realize) creates TOCTOU windows. All four
  second-call error paths are untested (lines 225, 234, 266, 276–277, 352).

- **Phantom configure_store.** `configure_store` is the production startup path wiring the
  store into the mirror hook, yet it has zero test coverage. `configure_pool` has two tests.
  The asymmetry suggests configure_store tests were accidentally skipped.

- **Background task testing gap.** `_fire_mirror` uses `asyncio.create_task` with a
  done-callback for error logging. The background nature makes it hard to test, but the
  current tests don't even attempt to verify the callback fires on failure. A test using
  `asyncio.get_event_loop().run_until_complete` + task scheduling would expose this.

- **Space isolation not integration-tested.** The feature board endpoint scopes by space_id,
  and `feature_board()` in storage is correct. But there's no test that creates features in
  two different spaces and asserts they don't bleed across. The numbering isolation test
  (`test_feat_per_space_isolation`) covers keys but not board queries.

- **`test_waiting_question_is_copied_when_available` has misleading name.** The test
  exercises the WAITING transition but deliberately uses a goal with no waiting_question
  (the comment acknowledges this). It does NOT verify the copy behavior it claims to test.
  The actual lines that copy the question (100–110) are unreachable with the current setup.
