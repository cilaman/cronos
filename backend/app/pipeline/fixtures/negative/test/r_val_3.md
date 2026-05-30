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
gate_decision: pass
tests_added: 5
passed: 37
failed: 5
---

## Summary

Negative test fixture: R-val-3 violation. gate_decision=pass is incoherent when
failed=5 — a passing gate requires zero failures. normalize() never touches
gate_decision or failed counts, so verify() must still fail.

Expected failure: R-val-3: gate_decision='pass' with failed=5 is incoherent

## Gate result

Contradictory: gate_decision=pass but 5 tests failed.

## Failures

5 tests failed (details omitted — this is an intentionally invalid fixture).

## Assumptions

1. This fixture exercises the R-val-3 hard-fail path.

## Open questions

None.

## Next consumer brief

N/A — this artifact is intentionally invalid.
