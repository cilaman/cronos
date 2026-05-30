---
cc_version: '1.0'
agent: architect
slug: fixture-test
phase: design
status: done
confidence: 0.9
inputs_used:
  - docs/spec.md
outputs_produced:
  - .cronos/pipeline/fixture-test/design-report-fixture-test.md
blockers: []
next_consumer: backend-impl
metrics:
  tool_calls: 10
  files_read: 1
  memory_hits: 0
  iterations_planned: 1
coverage_summary:
  searched:
    - backend/app/
  excluded: []
  strategies:
    - memory_retrieval
    - read_targeted
iterations:
  - id: I1
    type: backend
    scope_files:
      - backend/app/feature.py
    validation_command: pytest backend/tests/test_feature.py -v
    depends_on: []
risks:
  - description: Schema migration may cause downtime.
    severity: low
    mitigation: Coordinate with ops before deploying.
---

## Summary

Negative design fixture: the required '## Implementation plan' section is ABSENT.
normalize() can only rename existing sections (case normalization), not insert
missing ones. verify() must still fail after normalization.

Expected failure: missing required section (## Implementation plan)

## Components

A single backend component.

## Risks

See header risks list.

## Assumptions

1. This fixture exercises the missing-required-section hard-fail path for design.

## Open questions

None.

## Next consumer brief

N/A — this artifact is intentionally invalid.
