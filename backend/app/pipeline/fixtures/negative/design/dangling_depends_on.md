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
  iterations_planned: 2
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
    depends_on:
      - I99
risks:
  - description: Schema migration may cause downtime.
    severity: low
    mitigation: Coordinate with ops before deploying.
---

## Summary

Negative design fixture: iterations[0].depends_on references I99 which is not
defined in the iterations list (dangling dependency reference).
normalize() never touches iteration dependencies, so verify() must still fail.

Expected failure: iterations[0].depends_on references unknown iteration id 'I99'

## Components

A single backend component.

## Implementation plan

Iteration I1 depends on I99 which does not exist.

## Risks

See header risks list.

## Assumptions

1. This fixture exercises the dangling-depends_on hard-fail path.

## Open questions

None.

## Next consumer brief

N/A — this artifact is intentionally invalid.
