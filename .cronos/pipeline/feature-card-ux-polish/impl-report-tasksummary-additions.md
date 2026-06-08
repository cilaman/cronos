---
cc_version: "1.0"
agent: pipeline-implementor
slug: tasksummary-additions
phase: impl
status: done
confidence: 0.97
inputs_used:
  - .cronos/pipeline/feature-card-ux-polish/design-report-tasksummary-additions.md
  - backend/app/models.py
  - backend/app/storage.py
  - backend/tests/test_feature_board.py
outputs_produced:
  - backend/app/models.py
  - backend/app/storage.py
  - backend/tests/test_feature_board.py
  - backend/tests/test_tasksummary_realizes_fields.py
files_changed:
  - backend/app/models.py
  - backend/app/storage.py
  - backend/tests/test_feature_board.py
  - backend/tests/test_tasksummary_realizes_fields.py
validation_command_passed: true
iterations_executed:
  - id: I1
    status: done
    validation_command: "cd backend && pytest tests/test_feature_model.py tests/test_feature_schemas.py tests/test_feature_serialization.py -v --override-ini=\"addopts=\""
    result: "40 passed"
  - id: I2
    status: done
    validation_command: "cd backend && pytest tests/test_feature_board.py tests/test_storage_board_excludes_features.py tests/test_feature_realizes.py -v --override-ini=\"addopts=\""
    result: "13 passed"
  - id: I3
    status: done
    validation_command: "cd backend && pytest tests/test_feature_board.py tests/test_tasksummary_realizes_fields.py -v --override-ini=\"addopts=\""
    result: "16 passed"
full_suite: "2501 passed, 84.95% coverage"
scope_respected: true
---

## Summary

Three-iteration implementation of SG1 backend TaskSummary additions. Added `realized_by_count`
and `realizes_feature_key` to `TaskSummary`; populated them in `board()`, `feature_board()`,
and `realizing_items()` in `storage.py` without touching `summarize()` itself. All design
risks mitigated: O(N) per-call lookup dicts, graceful fallback for deleted realizes targets,
`realizing_count` preserved as-is alongside the new `realized_by_count` field.

## Changes

### I1 — models.py
Added two fields to `TaskSummary` with safe defaults:
```python
realized_by_count: int = 0
realizes_feature_key: str | None = None
```

### I2 — storage.py
- **`board()`**: builds `feature_key_by_id` dict scoped to `scope` before the summary loop;
  assigns `summary.realizes_feature_key = feature_key_by_id.get(task.realizes)` for tasks
  with `realizes` set. `realized_by_count` stays 0 (features excluded from board()).
- **`feature_board()`**: extends the existing `realizing_counts` pre-pass with a parallel
  `feature_key_by_id` dict scoped to `space_id`. Assigns both `realizing_count` and
  `realized_by_count` to the same value; assigns `realizes_feature_key` if `realizes` set.
- **`realizing_items()`**: builds unscoped `feature_key_by_id` dict (matches method's
  cross-space behavior); sets `realizes_feature_key` on each returned summary.

### I3 — tests
- Extended `test_feature_board.py` with `test_feature_board_both_count_fields_coexist` (R5
  regression guard: asserts both `realizing_count` and `realized_by_count` coexist and are equal).
- New file `test_tasksummary_realizes_fields.py` with 10 tests covering: `realized_by_count`
  equals `realizing_count`, zero when no realizers, `realizes_feature_key` populated in all
  three endpoints, R4 AC-3 missing-target (no crash + None), cross-space non-leakage.

## Risk disposition

| Risk | Status |
|------|--------|
| O(N^2) lookup | Mitigated — per-call dict built once before the loop |
| R4 AC-3 missing target crash | Mitigated — `dict.get(task.realizes)` defaults to None; explicit test passes |
| R5 realizing_count regression | Mitigated — `summarize()` untouched; post-assign pattern preserved; regression test passes |
| Scope drift (realizing_count renamed) | Mitigated — both fields present; I3 asserts coexistence |
| Cross-space leak | Mitigated — `feature_key_by_id` scoped by `space_id`; cross-space test passes |
