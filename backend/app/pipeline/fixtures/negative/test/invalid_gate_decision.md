---
cc_version: '1.0'
agent: tester
slug: fixture-test
phase: test
status: done
confidence: 0.9
inputs_used:
  - backend/app/feature.py
outputs_produced:
  - .cronos/pipeline/fixture-test/test-report-fixture-test.md
blockers: []
next_consumer: review
metrics:
  tool_calls: 6
  files_read: 1
gate_decision: unknown_value
tests_added: 5
passed: 42
failed: 0
---

## Summary

Negative test fixture: R-val-1 violation. gate_decision='unknown_value' is not in
the allowed set {pass, fail, escalate}. normalize() never touches gate_decision,
so verify() must still fail after normalization.

Expected failure: R-val-1: gate_decision 'unknown_value' not in ['escalate', 'fail', 'pass']

## Gate result

Gate decision is set to an invalid value.

## Failures

None (but gate_decision is invalid).

## Assumptions

1. This fixture exercises the R-val-1 hard-fail path.

## Open questions

None.

## Next consumer brief

N/A — this artifact is intentionally invalid.
