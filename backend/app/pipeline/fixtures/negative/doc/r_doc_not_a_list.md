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
  - docs/feature-x.md
blockers: []
next_consumer: user
metrics:
  tool_calls: 5
  files_read: 1
  docs_updated: 1
intentionally_not_updated: not-a-list-but-a-string
---

## Summary

Negative doc fixture: intentionally_not_updated is a string instead of a list.
R-doc-3 requires it to be a list (empty list is acceptable). normalize() never
coerces field types, so verify() must still fail after normalization.

Expected failure: intentionally_not_updated must be a list

## Updated docs

docs/feature-x.md

## Intentionally not updated

(Intentional type error in header — this would list skipped docs if valid.)

## Assumptions

1. This fixture exercises the intentionally_not_updated-wrong-type hard-fail path.

## Open questions

None.

## Next consumer brief

N/A — this artifact is intentionally invalid.
