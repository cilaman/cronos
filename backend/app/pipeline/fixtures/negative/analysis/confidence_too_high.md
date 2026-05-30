---
cc_version: '1.0'
agent: analyst
slug: fixture-test
phase: analysis
status: done
confidence: 1.5
inputs_used:
  - docs/spec.md
outputs_produced:
  - .cronos/pipeline/fixture-test/analysis-report-fixture-test.md
blockers: []
next_consumer: design
metrics:
  tool_calls: 8
  files_read: 1
  memory_hits: 0
request: Add feature X to the system.
has_ui: true
coverage_summary:
  searched:
    - docs/
  excluded: []
  strategies:
    - memory_retrieval
traceability:
  - requirement_id: R1
    statement: Feature X must be accessible via the API.
    acceptance_criteria:
      - API endpoint returns 200.
    verifying_phase: test
---

## Summary

Negative analysis fixture: confidence=1.5 violates R3 (must be in [0.0, 1.0]).
normalize() never adjusts confidence values, so verify() must still fail.

Expected failure: R3: confidence 1.5 not in [0.0, 1.0]

## Scope

N/A.

## Requirements

N/A.

## Acceptance criteria

N/A.

## Traceability

See header.

## Assumptions

1. This fixture exercises the R3 confidence-range hard-fail path.

## Open questions

None.

## Next consumer brief

N/A — this artifact is intentionally invalid.
