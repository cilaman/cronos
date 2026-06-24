---
cc_version: '1.0'
agent: pipeline-analyst
slug: test-feature-bad-ac
phase: analysis
status: done
confidence: 0.85
inputs_used:
- memory:project_architecture
- backend/app/main.py
- docs/spec.md
outputs_produced:
- .cronos/pipeline/test-feature-bad-ac/analysis-report-test-feature-bad-ac.md
blockers: []
next_consumer: design
request: Test feature with missing acceptance criteria.
has_ui: false
coverage_summary:
  searched:
  - backend/app/main.py
  excluded:
  - frontend/
  strategies:
  - read_targeted
traceability:
- requirement_id: R1
  statement: The system shall process valid inputs.
  acceptance_criteria:
  - Given a valid input, the system returns a result.
  verifying_phase: test
- requirement_id: R2
  statement: The system shall validate inputs.
  acceptance_criteria: []
  verifying_phase: test
metrics:
  tool_calls: 4
  files_read: 2
  memory_hits: 1
---

## Summary

Analysis with a missing acceptance criteria entry to exercise the acceptance check.

## Scope

R1 has AC; R2 has empty acceptance_criteria.

## Requirements

| R# | Statement |
|----|-----------|
| R1 | Process valid inputs |
| R2 | Validate inputs (missing ACs) |

## Acceptance criteria

R1 has one AC. R2 has no ACs (intentional defect for testing).

## Traceability

| R# | Verifying phase |
|----|-----------------|
| R1 | test |
| R2 | test |

## Assumptions

None.

## Open questions

None.

## Next consumer brief

R2 is missing acceptance criteria — gate should fail.
