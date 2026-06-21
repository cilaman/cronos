---
cc_version: "1.0"
agent: pipeline-reviewer
slug: g08-durable-queue--attempt1
phase: review
status: done
confidence: 0.85
inputs_used:
  - memory:project-g08-durable-queue-impl
  - memory:project-g08-design-phase
  - .cronos/pipeline/g08-durable-queue/design-report-g08-durable-queue.md
  - .cronos/pipeline/g08-durable-queue/analysis-report-g08-durable-queue.md
  - .cronos/pipeline/g08-durable-queue/impl-report-g08-durable-queue.md
  - .cronos/pipeline/g08-durable-queue/test-report-g08-durable-queue.md
  - backend/app/storage.py
  - backend/app/worker.py
  - backend/app/reaper.py
  - backend/app/main.py
outputs_produced:
  - .cronos/pipeline/g08-durable-queue/review-report-g08-durable-queue--attempt1.md
blockers: []
next_consumer: implementation
metrics:
  tool_calls: 14
  files_read: 8
  memory_hits: 2
  diff_lines_reviewed: 360
verdict: needs_fix
attempt: 1
findings:
  - id: F1
    severity: high
    file: backend/app/storage.py:674
    evidence: "heartbeat_lease() runs `UPDATE task_leases SET heartbeat_at = ? WHERE task_id = ? AND owner = ?` — it advances heartbeat_at only, never lease_expiry. acquire_lease set lease_expiry=now+LEASE_TTL (300s). reaper.get_expired_leases selects `lease_expiry < now OR heartbeat_at < stale_before`, so a still-running task with fresh heartbeats is reaped once it exceeds LEASE_TTL and re-enqueued (double execution). Violates R5 ('heartbeats extend lease_expiry')."
    blocking: true
    suggested_action: "In backend/app/storage.py heartbeat_lease, also extend the fence: change to `UPDATE task_leases SET heartbeat_at = ?, lease_expiry = ? WHERE task_id = ? AND owner = ?` with lease_expiry=now+ttl. Add a ttl param (worker passes LEASE_TTL at worker.py:897). Add a test asserting lease_expiry advances across heartbeats (strengthen test_heartbeat_lease_updates_timestamp in test_lease_store.py)."
  - id: F2
    severity: medium
    file: backend/app/reaper.py:82
    evidence: "R9 requires a WARNING log for the wedged-worker condition (stalled heartbeat, lease not yet expired). reaper_loop folds stale-heartbeat leases into the same re-enqueue path and logs only at INFO (lines 50,82,100); there is no log.warning in reaper.py and no caplog/WARNING assertion in test_reaper.py. The goal's 'detected and surfaced' acceptance for wedged workers is unmet at the observability level."
    blocking: true
    suggested_action: "In reaper_loop, when `heartbeat_at < now - heartbeat_timeout` but `lease_expiry >= now` (true wedge vs clean crash), emit `log.warning('Reaper: wedged worker — stale heartbeat for task %s (owner=%s)', ...)` before re-enqueue. Add a caplog test in test_reaper.py asserting the WARNING fires for the stale-heartbeat-but-live-expiry case."
  - id: F3
    severity: medium
    file: backend/app/reaper.py:61
    evidence: "reaper.py line coverage is 80% (41 stmts, 8 missed: 61-64, 87-88, 97-98) measured via `pytest ... --cov=app.reaper`. Below the G07 per-new-module DoD of >=85%. Missed branches: non-ACTIVE/missing-task stale-lease cleanup (61-64), the per-task exception handler (87-88), and the stop_event-set exit paths (97-98). Suite-wide coverage 85.5% masks this per-module gap."
    blocking: false
    suggested_action: "Add tests in test_reaper.py for: (a) expired lease whose task is missing/non-ACTIVE → lease deleted, no enqueue; (b) worker_pool.enqueue raising → loop continues; (c) stop_event already set before first wait → clean break. Raises app.reaper coverage to >=85%."
  - id: F4
    severity: low
    file: backend/app/reaper.py:60
    evidence: "`if not isinstance(expired, list): expired = []` (reaper.py:60-61) and the `except sqlite3.OperationalError: pass` swallow in storage.clear_all_leases exist solely to tolerate AsyncMock'd TaskStore in existing lifespan tests (impl-report out_of_scope_findings). Production code is shaped by test mocks and a RuntimeWarning ('coroutine never awaited') leaks from reaper.py:61 during those tests."
    blocking: false
    suggested_action: "Prefer patching reaper_loop (or task_store.get_expired_leases) in test_main_lifespan*.py so the AsyncMock store never reaches the reaper, then drop the isinstance guard. Keep the clear_all_leases OperationalError guard but document it as a genuine first-boot defense, not a test accommodation."
---

## Summary

Scope conformance: yes — observed changed set (storage.py, worker.py, main.py, reaper.py + 6 test files) is exactly the union of the design `iterations[].scope_files[]`; no scope escape. The test gate passed (2791 passed / 0 failed, suite coverage 85.5%) and existing touched-module tests stay green (455 passed locally, no regressions). Verdict is **needs_fix** on one load-bearing correctness defect: the heartbeat refreshes `heartbeat_at` but never extends `lease_expiry` (F1), so with the default `LEASE_TTL=300s` any agent run longer than 5 minutes — the common case for Claude runs — is reaped and re-enqueued while still running, producing the double-execution that R4/R5 exist to prevent. A second blocking gap (F2) is the entirely-missing R9 wedged-worker WARNING (no `log.warning`, no test). Two non-blocking findings cover the reaper's 80% per-module coverage (F3, below the G07 ≥85% DoD) and production code shaped by test mocks (F4).

## Findings

- **F1 (high, blocking)** — `heartbeat_lease` advances `heartbeat_at` only, not `lease_expiry`; reaper's `lease_expiry < now` clause then reaps live long-running tasks → double execution. R5 unmet.
- **F2 (medium, blocking)** — R9 wedged-worker WARNING not implemented or tested; reaper logs only at INFO.
- **F3 (medium, non-blocking)** — `app/reaper.py` at 80% line coverage (< G07 ≥85% target); missed branches at 61-64, 87-88, 97-98.
- **F4 (low, non-blocking)** — `isinstance(expired, list)` guard and `clear_all_leases` OperationalError swallow are test-mock accommodations; leaks an un-awaited-coroutine RuntimeWarning.

## Verdict

needs_fix. F1 alone defeats the anti-double-execution guarantee for the golden path (long agent runs); both blockers are small, well-scoped fixes recoverable in another implementor attempt (attempt 1 of ≤5).

## Assumptions

- Scope contract taken from design `iterations[].scope_files[]` union (I1–I6).
- Diff reviewed against the impl commit `3e2ee85` on `feature/cronos-remediation-plan` (the workspace branch is off `main` and does not contain the change; review used `git show 3e2ee85` + a detached worktree to run tests).
- R5 intent is that heartbeats extend the lease fence — confirmed by the analysis acceptance criterion ("heartbeat_at and lease_expiry advance ≥ 2 times") and the `acquire_lease(ttl)` design.
- Per-new-module ≥85% coverage (G07) applies to `app/reaper.py`; lease/auto-resume CRUD live in the pre-existing `storage.py` and are not a "new module".

## Open questions

- None.

## Next consumer brief

Re-spawn the implementor on the blocking findings:
- **F1** — fix `heartbeat_lease` (storage.py:667, I2 scope) to also extend `lease_expiry`; thread `ttl` from the worker heartbeat loop (worker.py:896, I3 scope). Strengthen the heartbeat test to assert `lease_expiry` advances.
- **F2** — add the R9 WARNING in `reaper_loop` (reaper.py, I5 scope) for the stale-heartbeat-but-unexpired case, plus a caplog test.
- F3 and F4 are non-blocking but cheap to fold into the same pass (raise `app.reaper` to ≥85%, drop the mock-shaped guard). Re-run iterations I2/I3 (F1) and I5 (F2/F3/F4); then re-review as attempt 2.
