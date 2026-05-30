---
cc_version: '1.0'
agent: reviewer
slug: fixture-test
phase: review
status: done
confidence: 0.88
inputs_used:
  - backend/app/feature.py
outputs_produced:
  - .cronos/pipeline/fixture-test/review-report-fixture-test.md
blockers: []
next_consumer: doc
metrics:
  tool_calls: 7
  files_read: 1
verdict: pass
findings:
  - id: F1
    severity: high
    file: backend/app/feature.py:42
    evidence: SQL query is not parameterized — injection risk.
    blocking: true
    suggested_action: Rewrite using parameterized queries.
---

## Summary

Negative review fixture: R-rev-4 violation. verdict=pass is incoherent when a
finding has blocking=true. A blocking finding means the implementation cannot
proceed without a fix. normalize() never touches verdict or blocking fields,
so verify() must still fail after normalization.

Expected failure: R-rev-4: verdict='pass' is incoherent with a finding marked blocking=true

## Findings

F1: SQL injection risk at backend/app/feature.py:42. BLOCKING.

## Verdict

pass (intentionally contradicts F1.blocking=true)

## Assumptions

1. This fixture exercises the R-rev-4 hard-fail path.

## Open questions

None.

## Next consumer brief

N/A — this artifact is intentionally invalid.
