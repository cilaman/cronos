---
cc_version: '1.0'
agent: doc-writer
slug: fixture-test
phase: doc
status: done
confidence: 0.9
inputs_used:
  - backend/app/feature.py
outputs_produced:
  - .cronos/pipeline/fixture-test/doc-report-fixture-test.md
blockers: []
next_consumer: user
metrics:
  tool_calls: 5
  files_read: 1
  docs_updated: 0
intentionally_not_updated: []
---

## Summary

Negative doc fixture: R-doc-4 violation. status=done with only the report in
outputs_produced (no additional docs written), and intentionally_not_updated is
empty. R-doc-4 requires that if no docs were updated and status=done, then
intentionally_not_updated must be non-empty to explain why. A silent no-op is
not a valid doc-sync outcome. normalize() cannot add entries to
intentionally_not_updated, so verify() must still fail.

Expected failure: R-doc-4: status=done with only the report in outputs_produced
requires non-empty intentionally_not_updated

## Updated docs

None updated (only the report itself is in outputs_produced).

## Intentionally not updated

(Intentionally empty — exercises R-doc-4 failure path.)

## Assumptions

1. This fixture exercises the R-doc-4 silent-no-op hard-fail path.

## Open questions

None.

## Next consumer brief

N/A — this artifact is intentionally invalid.
