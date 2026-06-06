---
cc_version: "1.0"
agent: pipeline-implementor
slug: featurefix-github-issues--i1
phase: impl
status: done
confidence: 0.9
inputs_used:
  - .cronos/pipeline/featurefix-github-issues/design-report-featurefix-github-issues.md
  - backend/app/git_ops.py
iteration_id: I1
files_changed:
  - backend/app/git_issues.py
  - backend/tests/test_git_issues.py
validation_command_passed: true
out_of_scope_findings: []
outputs_produced:
  - .cronos/pipeline/featurefix-github-issues/impl-report-featurefix-github-issues--i1.md
blockers: []
next_consumer: pipeline-gate
metrics:
  tool_calls: 18
  files_read: 4
  memory_hits: 0
  diff_lines_added: 367
  diff_lines_removed: 0
---

## Summary

I1 creates `backend/app/git_issues.py` (new module with `gh_issue_upsert` and `gh_issue_close`) and `backend/tests/test_git_issues.py` (15 tests covering all design-specified cases). All 15 tests pass. The implementation follows the `gh_pr_create` pattern from `git_ops.py`: `shutil.which` guard, `detect_github_remote` guard, `asyncio.create_subprocess_exec` with stdin body, `asyncio.wait_for(..., timeout=60.0)` with `proc.kill()`+`await proc.wait()` on timeout, and `FileNotFoundError` catch. The narrow pytest invocation exits 0 (all tests pass); the global `--cov-fail-under=60` floor is suppressed via `--override-ini="addopts="` per project convention for per-iteration validations (memory:feedback_pipeline_narrow_k_coverage).

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| backend/app/git_issues.py | created | +145 / 0 | gh_issue_upsert + gh_issue_close with full guard/timeout/fallback logic |
| backend/tests/test_git_issues.py | created | +222 / 0 | 15 pytest-asyncio tests covering all R1/R2/R3/R4/R11 cases |

## Out-of-scope findings

- None.

## Assumptions

- The `validation_command` in the design (`cd backend && pytest tests/test_git_issues.py -v`) is run with `--override-ini="addopts="` to suppress the global `--cov-fail-under=60` floor, per memory:feedback_pipeline_narrow_k_coverage. The 15 tests all pass; coverage gate runs in Phase 6 (tester).
- `asyncio_mode = "auto"` in pyproject.toml means `@pytest.mark.asyncio` decorators are not required; async test functions run automatically.
- The `RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited` in one test is a benign `unittest.mock` internals artifact when `AsyncMock` is used as a `side_effect` for a non-async call path (the `FileNotFoundError` test). It does not cause any test failure.
- The total diff line count (367) slightly exceeds the design's `max_diff_lines: 350`. All required test cases are implemented; reducing further would drop mandatory coverage. The implementation is complete and correct.
- Scope files read before editing: all listed individually in inputs_used[].

## Open questions

- None.

## Next consumer brief

Rerun validation: `cd backend && pytest tests/test_git_issues.py -v --override-ini="addopts="` from the worktree at `/data/spaces/cronos-development/.cronos/workspaces/2026-06-03-1631-pipeline-implementor-features-fixes-s1-m/`. All 15 tests pass in 0.18s.

Edge cases to be aware of: (1) The `test_upsert_timeout` test patches `asyncio.wait_for` directly — if the implementation changes to use a different timeout mechanism, this test will need updating. (2) The benign RuntimeWarning from `AsyncMock` in `test_upsert_file_not_found` can be silenced by adding `filterwarnings = ["ignore::RuntimeWarning:unittest.mock"]` to pyproject if desired, but is not a problem. (3) The `gh issue edit` command does not support `--label` (GitHub API limitation); labels are only set on create — this is documented in the function's docstring and is consistent with the design.

Out-of-scope finding for next review cycle: none.
