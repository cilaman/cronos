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
  diff_lines_added: 45
  diff_lines_removed: 3
  duration_s: 120.5
iteration_id: I1
files_changed:
  - backend/app/feature.py
validation_command_passed: true
---

## Summary

Negative implementation fixture: metrics.duration_s is a trace-owned metric that
agents MUST NOT write. Agents must not include duration_s or token_spend in their
artifacts — these are derived from the run trace by trace_parser post-hoc.
normalize() never removes trace-owned metrics, so verify() must still fail.

Expected failure: metrics.duration_s is trace-owned — agents MUST NOT write it

## Files changed

- backend/app/feature.py

## Out-of-scope findings

None.

## Assumptions

1. This fixture exercises the trace-owned-metric hard-fail path.

## Open questions

None.

## Next consumer brief

N/A — this artifact is intentionally invalid.
