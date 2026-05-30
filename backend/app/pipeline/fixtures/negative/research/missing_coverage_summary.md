---
cc_version: '1.0'
agent: scout
slug: fixture-test
phase: scout
status: done
confidence: 0.9
inputs_used:
  - docs/spec.md
outputs_produced:
  - .cronos/pipeline/fixture-test/scout-report-fixture-test.md
blockers: []
next_consumer: analysis
metrics:
  tool_calls: 8
  files_read: 1
  memory_hits: 0
---

## Summary

Negative research fixture: coverage_summary is ABSENT from the header.
The research schema requires coverage_summary. normalize() cannot insert missing
required fields, so verify() must still fail after normalization.

Expected failure: missing required header fields: coverage_summary

## Coverage

Would be here if coverage_summary were present.

## Findings

N/A.

## Assumptions

1. This fixture exercises the missing-required-field hard-fail path.

## Open questions

None.

## Next consumer brief

N/A — this artifact is intentionally invalid.
