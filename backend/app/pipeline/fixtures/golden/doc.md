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
intentionally_not_updated:
  - path: docs/old-api.md
    reason: Deprecated endpoint not affected by feature X.
---

## Summary

Golden doc fixture for CC-v1 regression tests. outputs_produced has 2 entries
(report + docs/feature-x.md), so docs_updated=1 matches (R-doc-5). intentionally_not_updated
is non-empty. R-doc-1 satisfied: outputs_produced[0] is the doc report itself.

## Updated docs

docs/feature-x.md — new page covering the feature X public interface.

## Intentionally not updated

docs/old-api.md — deprecated endpoint not affected by feature X.

## Assumptions

1. All public API endpoints have corresponding doc updates.
2. The user guide is the canonical documentation surface.

## Open questions

None.

## Next consumer brief

User may review the new documentation at docs/feature-x.md. Pipeline complete.
