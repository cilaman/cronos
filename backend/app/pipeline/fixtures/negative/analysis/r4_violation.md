---
cc_version: '1.0'
agent: analyst
slug: fixture-test
phase: analysis
status: done
confidence: 0.85
inputs_used:
  - docs/spec.md
  - docs/api.md
  - docs/requirements.md
outputs_produced:
  - .cronos/pipeline/fixture-test/analysis-report-fixture-test.md
blockers: []
next_consumer: design
metrics:
  tool_calls: 8
  files_read: 0
  memory_hits: 0
request: Add feature X to the system.
has_ui: false
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

Negative analysis fixture: R4 violation. inputs_used has 3 entries but
files_read=0 and memory_hits=0, so files_read + memory_hits (0) < len(inputs_used) (3).
normalize() never adjusts files_read or memory_hits, so verify() must still fail.

Expected failure: R4: metrics.files_read (0) + memory_hits (0) = 0 < len(inputs_used) (3)

## Scope

N/A.

## Requirements

N/A.

## Acceptance criteria

N/A.

## Traceability

See header.

## Assumptions

1. This fixture exercises the R4 accessibility hard-fail path.

## Open questions

None.

## Next consumer brief

N/A — this artifact is intentionally invalid.
