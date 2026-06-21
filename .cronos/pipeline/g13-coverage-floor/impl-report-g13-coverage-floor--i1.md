---
cc_version: '1.0'
agent: pipeline-implementor
slug: g13-coverage-floor--i1
phase: impl
status: done
confidence: 0.99
iteration_id: I1
inputs_used:
- .cronos/pipeline/g13-coverage-floor/design-report-g13-coverage-floor.md
- backend/pyproject.toml
outputs_produced:
- .cronos/pipeline/g13-coverage-floor/impl-report-g13-coverage-floor--i1.md
blockers: []
next_consumer: test
files_changed:
- backend/pyproject.toml
validation_command: cd backend && pytest tests/ --cov=app --cov-report=term-missing
  --cov-fail-under=80
validation_command_passed: true
metrics:
  tool_calls: 8
  files_read: 3
  memory_hits: 2
  diff_lines_added: 1
  diff_lines_removed: 1
---

## Summary

Raised the pytest coverage enforcement floor from 60% to 80% in `backend/pyproject.toml`
(line 39, `[tool.pytest.ini_options].addopts`). This is a single-token change:
`--cov-fail-under=60` → `--cov-fail-under=80`.

The full test suite was run at the new floor and passed: **2964 tests passed, 86.84%
total coverage**, providing ~6.84% headroom above the new 80% gate. The CI job (G02
`ci.yml`) reads this same `addopts` value at runtime and will enforce the new floor
automatically.

## Files changed

| File | Change |
|------|--------|
| `backend/pyproject.toml` | Line 39: `--cov-fail-under=60` → `--cov-fail-under=80` |

Diff is exactly 1 line removed and 1 line added (within the `max_diff_lines: 5` bound).

## Sanity check

`grep -rn -- --cov-fail-under backend/ .github/` returns exactly **one** match:

```
backend/pyproject.toml:39:addopts = "--cov=app --cov-report=term-missing --cov-fail-under=80"
```

No shadowing or duplicate occurrences exist.

## Out-of-scope findings

`TESTING.md` still documents the old 60% floor. This is a doc-only discrepancy with
no functional impact — `pyproject.toml` is the authoritative source consumed by
pytest and CI. The doc-sync phase should update that reference.

## Assumptions

- Design report scope was authoritative: `backend/pyproject.toml` is the sole change
  site; no source or test files were modified.
- Current actual coverage (86.84%) exceeds the new 80% floor, leaving ~6.84%
  headroom — consistent with the ~85.15% baseline cited in the design.
- G02 CI job inherits `addopts` from `pyproject.toml` at test time; no CI YAML edit
  was needed.

## Open questions

None. The floor value (80, not 85) was fixed by the source brief and design.

## Next consumer brief

**Test phase:** Re-run the same validation command as the authoritative gate:

```
cd backend && pytest tests/ --cov=app --cov-report=term-missing --cov-fail-under=80
```

Expected: all tests pass, total coverage ≥ 80%. The only scope file is
`backend/pyproject.toml`; no new tests are needed. The test report should confirm
the coverage number and exit 0.
