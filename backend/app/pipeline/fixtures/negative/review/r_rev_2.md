---
cc_version: '1.0'
agent: reviewer
slug: fixture-test
phase: review
status: done
confidence: 0.85
inputs_used:
  - backend/app/feature.py
outputs_produced:
  - .cronos/pipeline/fixture-test/review-report-fixture-test.md
blockers: []
next_consumer: doc
metrics:
  tool_calls: 7
  files_read: 1
verdict: needs_fix
findings:
  - id: ISSUE-001
    severity: medium
    file: backend/app/feature.py:15
    evidence: Missing input validation on user-supplied data.
    blocking: false
    suggested_action: Add validation before processing.
---

## Summary

Negative review fixture: R-rev-2 violation. findings[0].id='ISSUE-001' does not
match the required pattern '^F[0-9]+$'. Finding IDs must use the F-prefix format
(e.g. F1, F42). normalize() never touches finding IDs, so verify() must still fail.

Expected failure: R-rev-2: findings[0].id 'ISSUE-001' does not match '^F[0-9]+$'

## Findings

ISSUE-001: missing input validation (uses wrong ID format — should be F1).

## Verdict

needs_fix

## Assumptions

1. This fixture exercises the R-rev-2 finding-id-format hard-fail path.

## Open questions

None.

## Next consumer brief

N/A — this artifact is intentionally invalid.
