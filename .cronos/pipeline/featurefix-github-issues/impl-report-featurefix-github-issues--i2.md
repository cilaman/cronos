---
cc_version: "1.0"
agent: pipeline-implementor
slug: featurefix-github-issues--i2
phase: impl
status: done
confidence: 0.9
inputs_used:
  - .cronos/pipeline/featurefix-github-issues/design-report-featurefix-github-issues.md
  - backend/app/storage.py
  - backend/tests/test_storage.py
  - backend/tests/conftest.py
  - backend/app/models.py
iteration_id: I2
files_changed:
  - backend/app/storage.py
  - backend/tests/test_storage_set_issue_refs.py
validation_command_passed: true
out_of_scope_findings: []
outputs_produced:
  - .cronos/pipeline/featurefix-github-issues/impl-report-featurefix-github-issues--i2.md
blockers: []
next_consumer: pipeline-gate
metrics:
  tool_calls: 16
  files_read: 5
  memory_hits: 0
  diff_lines_added: 168
  diff_lines_removed: 0
---

## Summary

Iteration I2 adds the `set_issue_refs` method to `TaskStore` in `backend/app/storage.py`, modelled line-for-line on the existing `set_pr_refs` method. The method takes keyword-only parameters `issue_number`, `issue_url`, and `proposed_issue_path`, acquires `self._lock`, raises `TaskNotFound` for unknown task IDs, calls `model_copy` with `updated_at=datetime.now(tz=UTC)`, then persists via `atomic_write` and `_reindex_locked`. Seven tests in the new `test_storage_set_issue_refs.py` file cover all required scenarios and all pass. The narrow pytest invocation exits 0 when run with `--override-ini="addopts="` to bypass the project-global `--cov-fail-under=60` floor (per memory:feedback_pipeline_narrow_k_coverage — the full-suite coverage gate runs in Phase 6).

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| backend/app/storage.py | modified | +26 / 0 | Add `set_issue_refs` method to `TaskStore` after `set_pr_refs` |
| backend/tests/test_storage_set_issue_refs.py | created | +142 / 0 | 7 tests covering all required scenarios for `set_issue_refs` |

## Out-of-scope findings

- None.

## Assumptions

- The `asyncio_mode = "auto"` in pyproject.toml means no `@pytest.mark.asyncio` decorator is needed — confirmed by reading conftest.py and existing tests.
- The validation command `cd backend && pytest tests/test_storage_set_issue_refs.py -v` as written fails the global `--cov-fail-under=60` due to narrow module coverage (21%), not test failures. Per memory:feedback_pipeline_narrow_k_coverage, `validation_command_passed: true` is set based on test results (7/7 passed), consistent with the design report Assumptions section stating "the coverage floor is a project-global gate, NOT a per-iteration gate".
- The `Task` model already has `issue_number: int | None`, `issue_url: str | None`, `proposed_issue_path: str | None` fields from S1 (confirmed in backend/app/models.py lines 73-75, 126-128, 219-221).
- Scope files read before editing: all listed individually in inputs_used[].

## Open questions

- None.

## Next consumer brief

Rerun validation: `cd backend && pytest tests/test_storage_set_issue_refs.py -v --override-ini="addopts="`

The plain `cd backend && pytest tests/test_storage_set_issue_refs.py -v` command exits 1 due to the global `--cov-fail-under=60` gate (21% coverage from narrow run), but all 7 tests pass. Use `--override-ini="addopts="` to confirm pass without coverage floor interference.

Edge cases uncovered during implementation: none beyond what the design specified. The `set_issue_refs` implementation is a near-verbatim copy of `set_pr_refs`; no surprises encountered. I3 can proceed (it depends on both I1 and I2) — confirm I1's `impl-report-featurefix-github-issues--i1.md` is `status: done` before starting I3.
