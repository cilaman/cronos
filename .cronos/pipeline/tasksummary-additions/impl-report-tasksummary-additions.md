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
  - .cronos/pipeline/tasksummary-additions/impl-report-tasksummary-additions.md
blockers: []
next_consumer: test
iteration_id: I3
files_changed:
  - backend/app/models.py
  - backend/app/storage.py
  - backend/tests/test_feature_board.py
  - backend/tests/test_tasksummary_realizes_fields.py
validation_command_passed: true
metrics:
  tool_calls: 28
  files_read: 10
  memory_hits: 0
  diff_lines_added: 215
  diff_lines_removed: 8
  tests_added: 11
---

## Summary

Three-iteration implementation of SG1 backend TaskSummary additions. Added `realized_by_count`
and `realizes_feature_key` to `TaskSummary`; populated them in `board()`, `feature_board()`,
and `realizing_items()` in `storage.py` without touching `summarize()` itself. All design risks
mitigated: O(N) per-call lookup dicts, graceful fallback for deleted realizes targets,
`realizing_count` preserved alongside the new `realized_by_count`. Full test suite: 2501 passed,
84.95% coverage.

## Files changed

### backend/app/models.py
Added two fields to `TaskSummary` with safe defaults:
```python
realized_by_count: int = 0
realizes_feature_key: str | None = None
```

### backend/app/storage.py
- **`board()`**: builds `feature_key_by_id` dict scoped to `scope` before the summary loop;
  assigns `summary.realizes_feature_key = feature_key_by_id.get(task.realizes)` for tasks
  with `realizes` set. `realized_by_count` stays 0 (features excluded from board by design).
- **`feature_board()`**: extends the existing `realizing_counts` pre-pass with a parallel
  `feature_key_by_id` dict scoped to `space_id`. Assigns both `realizing_count` and
  `realized_by_count` to the same value; assigns `realizes_feature_key` if `realizes` set.
- **`realizing_items()`**: builds unscoped `feature_key_by_id` dict (matches method's
  cross-space behavior); sets `realizes_feature_key` on each returned summary.

### backend/tests/test_feature_board.py
Extended with `test_feature_board_both_count_fields_coexist` — R5 regression guard asserting
both `realizing_count` and `realized_by_count` coexist and equal the same value.

### backend/tests/test_tasksummary_realizes_fields.py
New test file with 10 tests covering: `realized_by_count` equals `realizing_count`, zero when
no realizers, `realizes_feature_key` populated in all three endpoints (board/feature_board/
realizing_items), R4 AC-3 missing-target graceful fallback (no crash + None), cross-space
non-leakage.

## Out-of-scope findings

None.

## Assumptions

- `summarize()` at storage.py:360 is not modified. New fields are assigned on the returned
  TaskSummary after `summarize()` returns, matching the existing `realizing_count` pattern at
  storage.py:795.
- `realized_by_count` equals `realizing_count` for feature tasks in `feature_board()`. Analysis
  Assumption #4 binds: both fields coexist; neither removes the other.
- No SQLite migration required — these fields are computed denorm, not persisted columns.

## Open questions

None.

## Next consumer brief

Consumer: test phase. Validation command:

```
cd backend && pytest tests/test_feature_board.py tests/test_tasksummary_realizes_fields.py tests/test_storage_board_excludes_features.py tests/test_feature_realizes.py -v --override-ini="addopts="
```

Key coverage: `realized_by_count` + `realizing_count` coexist and equal on feature summaries;
`realizes_feature_key` populated in board/feature_board/realizing_items; R4 AC-3 missing-target
returns None without raising; cross-space lookup scoping prevents leakage.
