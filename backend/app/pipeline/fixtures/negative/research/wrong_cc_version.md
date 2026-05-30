---
cc_version: '2.0'
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
coverage_summary:
  searched:
    - docs/
  excluded: []
  strategies:
    - memory_retrieval
    - read_targeted
---

## Summary

Negative research fixture: cc_version is '2.0' instead of '1.0'.
normalize() never touches cc_version, so verify() must still fail after normalization.

Expected failure: cc_version='2.0' not supported by this verifier (expected '1.0')

## Coverage

Searched docs/. Excluded nothing.

## Findings

N/A.

## Assumptions

1. This fixture exercises the wrong-cc_version hard-fail path.

## Open questions

None.

## Next consumer brief

N/A — this artifact is intentionally invalid.
