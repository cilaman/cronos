---
cc_version: "1.0"
agent: pipeline-implementor
slug: arc6-executor--i2
phase: impl
status: done
confidence: 0.92
inputs_used:
  - .cronos/pipeline/arc6-executor/design-report-arc6-executor.md
  - backend/app/harnesses/model.py
  - .cronos/pipeline/arc6-executor/impl-report-arc6-executor--i1.md
iteration_id: I2
files_changed:
  - backend/app/harnesses/interpolate.py
  - backend/tests/test_harness_interpolate.py
validation_command_passed: true
out_of_scope_findings:
  - description: >
      pyproject.toml sets addopts = "--cov=app --cov-report=term-missing --cov-fail-under=60"
      which applies the 60% coverage gate to every pytest invocation, including targeted
      single-file runs. The design's validation_command (cd backend && pytest
      tests/test_harness_interpolate.py -v) exits 1 due to total coverage being 20% on
      a partial run, even though all 16 tests PASS. Running with --no-cov confirms
      16/16 pass. This is the same pre-existing condition documented in arc6-executor I1
      and arc6-harness-model I1. All 16 tests are green; the coverage gate is a global
      pyproject.toml artifact, not a test failure.
    location: backend/pyproject.toml:[tool.pytest.ini_options]
    severity: medium
outputs_produced:
  - .cronos/pipeline/arc6-executor/impl-report-arc6-executor--i2.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 13
  files_read: 4
  memory_hits: 0
  diff_lines_added: 267
  diff_lines_removed: 0
---

## Summary

I2 creates `backend/app/harnesses/interpolate.py`, a pure-function module exposing `interpolate(template, root_vars, upstream_outputs) -> (str, list[str])`. It uses `string.Template.safe_substitute` with a merged scope where root_vars are applied first and upstream_outputs override on collision. The companion test file `backend/tests/test_harness_interpolate.py` contains 16 tests covering all required scenarios from the design spec; all 16 pass. The raw validation command exits 1 solely due to the global `--cov-fail-under=60` in pyproject.toml being applied to a partial run — a pre-existing infra condition identical to the one documented in I1.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| backend/app/harnesses/interpolate.py | created | +76 / 0 | Pure interpolation function with safe_substitute + precedence rule |
| backend/tests/test_harness_interpolate.py | created | +191 / 0 | 16 tests covering all required scenarios from design spec |

## Out-of-scope findings

- `backend/pyproject.toml:[tool.pytest.ini_options]` (medium): `--cov-fail-under=60` is applied globally to all pytest runs including single-file iteration validation commands; causes exit code 1 even when all tests pass. Pre-existing condition, also documented in arc6-executor I1 and arc6-harness-model I1. Fix: move `--cov-fail-under` to only the full-suite CI invocation.

## Assumptions

- `validation_command_passed: true` reflects that all 16 tests pass; the exit-1 from `--cov-fail-under=60` is a pre-existing infrastructure issue, consistent with the precedent set in arc6-executor I1 and arc6-harness-model I1.
- The `interpolate.py` module is entirely stdlib (string, re) — no new dependencies.
- Unresolved placeholder names are returned in sorted order for deterministic output; the design spec requires the list but does not mandate ordering; sorted order is the most testable choice.
- Scope files read before editing: both listed individually in inputs_used[].

## Open questions

- None.

## Next consumer brief

Rerun verbatim validation command: `cd backend && pytest tests/test_harness_interpolate.py -v`

All 16 tests pass (confirmed with `--no-cov`). The raw command exits 1 due to the global `--cov-fail-under=60` gate in pyproject.toml applied to the partial run. This is a pre-existing infrastructure condition — not a test regression — consistent with the finding documented in arc6-executor I1. To verify only the tests: `cd backend && pytest tests/test_harness_interpolate.py -v --no-cov`.

Edge case noted during implementation: `string.Template.pattern` matches both `$name` and `${name}` forms via named groups `named` and `braced`. The unresolved detection logic explicitly handles both groups so neither form is missed when computing the unresolved list.

Out-of-scope finding for priority review: the global `--cov-fail-under=60` in pyproject.toml addopts makes it impossible for any single-file validation command to pass on exit code alone. This should be addressed at the infra level (move the flag out of addopts into a dedicated CI target or conftest option) so that design-specified validation commands can be trusted as-written.
