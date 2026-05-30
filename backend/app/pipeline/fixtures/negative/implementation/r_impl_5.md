---
cc_version: '1.0'
agent: backend-impl
slug: fixture-test--i1
phase: impl
status: done
confidence: 0.92
inputs_used:
  - .cronos/pipeline/fixture-test/design-report-fixture-test.md
outputs_produced:
  - .cronos/pipeline/fixture-test/impl-report-fixture-test--i1.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 15
  files_read: 1
  memory_hits: 0
  diff_lines_added: 45
  diff_lines_removed: 3
iteration_id: I1
files_changed:
  - backend/app/feature.py
validation_command_passed: false
---

## Summary

Negative implementation fixture: R-impl-5 violation.
validation_command_passed=false with status=done is semantically incoherent —
a failed validation run cannot result in status=done.
normalize() never touches validation_command_passed or status, so verify() must still fail.

Expected failure: R-impl-5: validation_command_passed=false with status=done is incoherent

## Files changed

- backend/app/feature.py

## Out-of-scope findings

None.

## Assumptions

1. This fixture exercises the R-impl-5 hard-fail path.

## Open questions

None.

## Next consumer brief

N/A — this artifact is intentionally invalid.
