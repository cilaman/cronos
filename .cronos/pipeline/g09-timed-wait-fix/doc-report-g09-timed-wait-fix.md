---
cc_version: '1.0'
agent: pipeline-doc-sync
slug: g09-timed-wait-fix
phase: doc
status: done
confidence: 0.95
inputs_used:
- .cronos/pipeline/g09-timed-wait-fix/impl-report-g09-timed-wait-fix--i4.md
- .cronos/pipeline/g09-timed-wait-fix/review-report-g09-timed-wait-fix--attempt1.md
- CLAUDE.md
- docs/HARNESSES.md
outputs_produced:
- .cronos/pipeline/g09-timed-wait-fix/doc-report-g09-timed-wait-fix.md
intentionally_not_updated: []
blockers: []
next_consumer: none
metrics:
  tool_calls: 4
  files_read: 4
  docs_updated: 2
---

## Summary

Updated CLAUDE.md and docs/HARNESSES.md to document the G09 timed-wait fix. The
MVP caveat about timed waits re-sleeping the full duration on restart has been
removed and replaced with accurate documentation of the new behavior: on restart,
a timed wait sleeps only the *remaining* interval and fires immediately if the
wake time has already passed. Two documentation files updated; no source code
edited.

## Files updated

| File | Change |
|------|--------|
| `CLAUDE.md` (line 87) | Updated `backend/app/harnesses/wait.py` entry: removed MVP note; now states `await_timed_wait()` sleeps timed-mode runs and on restart sleeps only the remaining duration via `wake_at` timestamp |
| `CLAUDE.md` (line 91) | Updated `backend/app/harnesses/run_state.py` entry: added `wake_at` field to lifecycle timing fields; documented that `wake_at` is persisted for timed Wait nodes to enable remaining-duration sleep on restart |
| `docs/HARNESSES.md` (lines 502–503) | Updated timed-wait behavior section under "Wait — pause the run": removed MVP caveat about re-sleeping full duration; now documents that on restart the run sleeps only the remaining interval and fires immediately if the wake time has passed |

## Intentionally not updated

None — all relevant documentation touched by this feature has been updated. The
change is purely behavioral (no API, schema, or UI surface change per the review
report `has_ui=false`), so no other docs require changes.

## Assumptions

- The implementation report (I4) is the source of truth for the behavior change.
- The review report's verdict (`pass`) confirms no additional user-facing
  documentation obligations.
- No schema, API, or frontend changes were made (confirmed by review), so no
  swagger, type definitions, or component docs require updates.

## Open questions

None.

## Next consumer brief

All G09 documentation is complete. The feature can now be shipped — harness
timed Wait nodes now handle process restarts correctly by sleeping only the
*remaining* duration instead of re-sleeping the full duration.
