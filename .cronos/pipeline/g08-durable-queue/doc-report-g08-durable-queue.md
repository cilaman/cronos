---
cc_version: "1.0"
agent: pipeline-doc-sync
slug: g08-durable-queue
phase: doc
status: done
confidence: 0.90
inputs_used:
  - impl-report-g08-durable-queue.md
  - review-report-g08-durable-queue--attempt1.md
  - CLAUDE.md
  - backend/app/storage.py
  - backend/app/worker.py
  - backend/app/reaper.py
  - backend/app/main.py
outputs_produced:
  - .cronos/pipeline/g08-durable-queue/doc-report-g08-durable-queue.md
  - CLAUDE.md
metrics:
  docs_updated: 1
  intentionally_not_updated:
    - backend/app/storage.py (source file: module docstring not updated; lease/auto-resume CRUD methods documented inline in Key modules table instead)
    - backend/app/worker.py (source file: lease/heartbeat integration documented inline in Key modules table)
    - backend/app/reaper.py (source file: new reaper loop module; architectural role documented in Key modules table, function-level docstrings in source)
    - docs/ARCHITECTURE.md (does not exist; architectural invariant "markdown is source of truth; SQLite is disposable index" documented via CLAUDE.md Key modules entries)
  notes: "Review report identifies F1 (heartbeat_lease doesn't extend lease_expiry) and F2 (missing R9 wedged-worker WARNING) as blocking findings requiring implementor re-attempt; doc-sync phase documents the implementation as delivered (commit 3e2ee85), not the eventual corrected state. These architectural/observability gaps do not block doc completeness."
---

## Summary

Updated CLAUDE.md Key modules section to document G08 durable task queue implementation. Added 1 new module entry (`backend/app/reaper.py`) describing the background reaper coroutine for lease recovery. Extended 2 existing module entries (`backend/app/storage.py`, `backend/app/worker.py`) with durable queue specifics: SQLite lease/auto-resume schema, CRUD method names, heartbeat loop integration, and auto-resume count persistence semantics.

The architectural invariant — markdown is source of truth; SQLite lease/auto-resume tables are disposable recovery indices — is implicit in the Key modules documentation and does not require a new Architecture section at this release.

## Files changed

| File | Action | Purpose |
|------|--------|---------|
| CLAUDE.md | modified | Updated Key modules table entries for storage.py (lease/auto-resume CRUD), worker.py (lease lifecycle, heartbeat, durable auto-resume), added reaper.py entry (scan-first loop, stale-heartbeat detection) |

## Intentionally not updated

- **backend/app/storage.py** — Source file with inline documentation (docstrings); Key modules table entry captures CRUD method contract; module-level docstring updates out of scope for doc-sync phase.
- **backend/app/worker.py** — Source file; lease/heartbeat integration documented via Key modules table; scope follows impl scope (worker.py changes I3/I4 = _run_task + _finalize).
- **backend/app/reaper.py** — New source file; function-level docstrings in source; Key modules table documents high-level role (scan-first, markdown-gated, wedge detection).
- **docs/ARCHITECTURE.md** — File does not exist; architectural decisions (SQLite as disposable index vs. markdown as durable source) expressed via Key modules descriptions.

## Open questions

- None.

## Next consumer brief

This doc-sync phase is terminal for G08. The review report (attempt 1) identified 2 blocking findings (F1 heartbeat_lease, F2 wedged-worker WARNING) and 2 non-blocking findings (F3 reaper.py coverage, F4 test-mock guards). These are scope for a second implementor attempt, not for doc-sync. Doc completeness verified: CLAUDE.md is the single source of truth for architecture/module descriptions and now includes durable queue semantics.
