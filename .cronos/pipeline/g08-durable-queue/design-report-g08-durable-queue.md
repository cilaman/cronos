---
cc_version: '1.0'
agent: pipeline-architect
slug: g08-durable-queue
phase: design
status: done
confidence: 0.85
inputs_used:
- memory:project-remediation-board-setup
- memory:pipeline-narrow-k-coverage
- .cronos/pipeline/g08-durable-queue/analysis-report-g08-durable-queue.md
- .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
- backend/app/storage.py
- backend/app/worker.py
- backend/app/worker_pool.py
- backend/app/main.py
outputs_produced:
- .cronos/pipeline/g08-durable-queue/design-report-g08-durable-queue.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - backend/app/storage.py
  - backend/app/worker.py
  - backend/app/worker_pool.py
  - backend/app/main.py
  excluded:
  - 'frontend/: has_ui=false — backend-only reliability feature'
  - 'backend/app/harnesses/: timed-wait durability is G09, out of scope'
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
iterations:
- id: I1
  type: data
  scope_files:
  - backend/app/storage.py
  - backend/tests/test_lease_schema.py
  validation_command: cd backend && pytest tests/test_lease_schema.py -v --override-ini="addopts="
  max_diff_lines: 150
  depends_on: []
- id: I2
  type: backend
  scope_files:
  - backend/app/storage.py
  - backend/tests/test_lease_store.py
  validation_command: cd backend && pytest tests/test_lease_store.py -v --override-ini="addopts="
  max_diff_lines: 350
  depends_on:
  - I1
- id: I3
  type: backend
  scope_files:
  - backend/app/worker.py
  - backend/tests/test_worker_lease.py
  validation_command: cd backend && pytest tests/test_worker_lease.py -v --override-ini="addopts="
  max_diff_lines: 350
  depends_on:
  - I2
- id: I4
  type: backend
  scope_files:
  - backend/app/worker.py
  - backend/tests/test_worker_auto_resume_persist.py
  validation_command: cd backend && pytest tests/test_worker_auto_resume_persist.py
    -v --override-ini="addopts="
  max_diff_lines: 250
  depends_on:
  - I3
- id: I5
  type: backend
  scope_files:
  - backend/app/reaper.py
  - backend/tests/test_reaper.py
  validation_command: cd backend && pytest tests/test_reaper.py -v --override-ini="addopts="
  max_diff_lines: 400
  depends_on:
  - I2
- id: I6
  type: infra
  scope_files:
  - backend/app/main.py
  - backend/tests/test_reaper_integration.py
  validation_command: cd backend && pytest tests/test_reaper_integration.py -v --override-ini="addopts="
  max_diff_lines: 250
  depends_on:
  - I3
  - I5
risks:
- description: Two workers race to acquire the same task's lease (R4). A naive SELECT-then-INSERT
    leaves a TOCTOU window where both observe no lease and both execute the task.
  severity: high
  mitigation: 'Acquire via a single `INSERT OR IGNORE INTO task_leases(task_id, owner,
    lease_expiry, heartbeat_at)` on the PK, then read `con.total_changes` / `cursor.rowcount`:
    1 row changed = lease won, 0 = a live foreign lease already exists so the worker
    skips. The PK uniqueness makes the insert atomic within SQLite''s default locking;
    takeover of an expired lease is a guarded `DELETE WHERE lease_expiry < now` immediately
    followed by the same INSERT OR IGNORE.'
- description: The heartbeat coroutine outlives its task on an unhandled exception,
    leaving a perpetually-refreshed lease that the reaper can never reclaim (dead
    task, live lease).
  severity: high
  mitigation: Start the heartbeat with `asyncio.create_task` and wrap the agent run
    in `try/finally`; the finally block cancels the heartbeat task, awaits its cancellation
    (suppressing CancelledError), then calls `release_lease`. Lease release and heartbeat
    teardown share the one finally so neither can be skipped on the exception path.
- description: The reaper re-enqueues the same expired-lease task on two consecutive
    passes because the stale lease row is still present when the second pass scans.
  severity: medium
  mitigation: Inside the reaper, `delete_expired_lease(task_id)` is called BEFORE
    `worker_pool.enqueue(...)` (R7 criterion 2). Re-enqueue is additionally gated
    on `task_store.get(task_id).state == ACTIVE` (markdown truth) so a task moved
    to done/archived between passes is never re-queued.
- description: Heartbeat UPDATEs every HEARTBEAT_INTERVAL across N space-workers create
    SQLite write contention against the shared cronos-index.db.
  severity: medium
  mitigation: Default HEARTBEAT_INTERVAL=15s (not lower); each heartbeat is a single-row
    UPDATE by PK on a short-lived connection (matching the existing storage.py connection-per-op
    pattern). WAL-mode / concurrency tuning is explicitly deferred (analysis §Deferred)
    and revisited only if space fan-out grows.
- description: I3 and I4 both modify worker.py; if dispatched as parallel implementors
    in the same DAG layer they would produce conflicting diffs against the same file.
  severity: low
  mitigation: 'I4 declares `depends_on: [I3]`, forcing serial execution so the second
    implementor edits worker.py after the first''s diff has landed. The reaper logic
    is isolated in a new module (backend/app/reaper.py, I5) precisely to avoid further
    worker.py contention.'
- description: The durable auto-resume count in SQLite and the in-memory `_auto_resume_counts`
    dict drift, so the 3-resume cap is mis-enforced after a restart (R10).
  severity: medium
  mitigation: 'Treat SQLite as the write-through store of record: `__init__` loads
    all `auto_resume_counts` rows into the dict once; every increment upserts the
    row in the same statement that mutates the dict; every non-max-turns completion
    deletes the row and pops the dict key. The dict is only ever a cache rebuilt from
    the table at construction.'
metrics:
  tool_calls: 16
  files_read: 7
  memory_hits: 2
  iterations_planned: 6
---

## Summary

G08 makes Cronos's in-process task queue durable by adding two SQLite index tables (`task_leases`, `auto_resume_counts`) plus a lease/heartbeat/reaper coordination loop, so a `kill -9`'d or wedged worker is detected and its task re-enqueued within a bounded `LEASE_TTL + REAPER_INTERVAL` SLA. The architecture invariant is preserved: lease rows are disposable index-side coordination only — the reaper always re-derives "is this still my work" from markdown (`task_store.get(id).state == ACTIVE`) before acting, and startup wipes all stale leases. The six-iteration DAG is mostly serial through the storage layer (I1 schema → I2 lease/count CRUD) then forks: worker-side lease lifecycle (I3 → I4) runs in parallel with the standalone reaper module (I5), converging at the lifespan wiring (I6). The chief tradeoff captured in `risks[]` is heartbeat write-frequency vs. recovery latency, resolved at HEARTBEAT_INTERVAL=15s / REAPER_INTERVAL=30s / LEASE_TTL=300s with WAL tuning deferred.

## Components

### Data
- `task_leases(task_id TEXT PK, owner TEXT, lease_expiry REAL, heartbeat_at REAL)`: durable coordination fence; one row per actively-leased task (R1).
- `auto_resume_counts(task_id TEXT PK, count INTEGER)`: persistent replacement for the in-memory `_auto_resume_counts` dict so the 3-resume cap survives restart (R2, R10).
- `_ensure_db_schema()` in `storage.py`: the single idempotent migration point both tables are added to (R1, R2).

### Backend
- `TaskStore` lease CRUD (`acquire_lease`, `heartbeat_lease`, `release_lease`, `get_expired_leases`, `delete_expired_lease`, `clear_all_leases`): index-side primitives shared by the worker and the reaper (R3, R4, R6, R7, R11).
- `TaskStore` auto-resume CRUD (`load_auto_resume_counts`, `upsert_auto_resume_count`, `delete_auto_resume_count`): write-through persistence for the resume counter (R10).
- Worker lease lifecycle in `_run_task`: acquire-before-agent, skip-on-foreign-lease, background heartbeat coroutine, release-in-finally; constants `LEASE_TTL`, `HEARTBEAT_INTERVAL`, owner `f"{space_id}:{uuid4()}"` (R3, R4, R5, R6).
- Worker durable auto-resume: load at `__init__`, upsert on increment, delete on non-max-turns completion (R10).
- `reaper.py` `reaper_loop(task_store, worker_pool, stop_event)`: periodic scan of expired leases + wedged-worker detection, markdown-state-gated re-enqueue; constants `REAPER_INTERVAL`, `HEARTBEAT_TIMEOUT` (R7, R8, R9).
- `main.py` lifespan wiring: startup `clear_all_leases()`, reaper `asyncio.create_task`, teardown in the existing finally block (R8, R11).

## Implementation plan

| ID  | Type     | Depends on | Scope files (abridged)                          | Validation                                                        |
|-----|----------|------------|-------------------------------------------------|-------------------------------------------------------------------|
| I1  | data     | -          | backend/app/storage.py, tests/test_lease_schema.py | cd backend && pytest tests/test_lease_schema.py -v …             |
| I2  | backend  | I1         | backend/app/storage.py, tests/test_lease_store.py  | cd backend && pytest tests/test_lease_store.py -v …              |
| I3  | backend  | I2         | backend/app/worker.py, tests/test_worker_lease.py  | cd backend && pytest tests/test_worker_lease.py -v …            |
| I4  | backend  | I3         | backend/app/worker.py, tests/test_worker_auto_resume_persist.py | cd backend && pytest tests/test_worker_auto_resume_persist.py -v … |
| I5  | backend  | I2         | backend/app/reaper.py, tests/test_reaper.py        | cd backend && pytest tests/test_reaper.py -v …                  |
| I6  | infra    | I3, I5     | backend/app/main.py, tests/test_reaper_integration.py | cd backend && pytest tests/test_reaper_integration.py -v …    |

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Lease-acquisition TOCTOU race lets two workers run one task (R4) | high | `INSERT OR IGNORE` on PK + rowcount check; expired-lease takeover is guarded DELETE-then-INSERT |
| Heartbeat coroutine leaks past task, lease never reclaimable | high | `try/finally` cancels+awaits heartbeat task and releases lease on every exit path |
| Reaper double re-enqueues across consecutive passes | medium | Delete stale lease row before enqueue; gate on markdown ACTIVE state |
| Heartbeat write contention on shared SQLite index | medium | 15s interval, single-row UPDATE by PK, short-lived connection; WAL tuning deferred |
| I3/I4 concurrent diffs on worker.py | low | I4 `depends_on I3` serializes; reaper isolated in new module |
| Auto-resume count DB↔memory drift mis-enforces resume cap (R10) | medium | SQLite is write-through store of record; dict is a cache rebuilt at `__init__` |

## Assumptions

- `_ensure_db_schema()` in `backend/app/storage.py` (lines 493–551) is the correct, idempotent migration point — confirmed by read; the tables are added with `CREATE TABLE IF NOT EXISTS` alongside `tasks`/`discovered_tools`.
- `TaskStore` owns the single shared `cronos-index.db` covering all spaces (each row carries `space_id`), so lease + count CRUD live on `TaskStore` rather than a new class — minimal scope, and the reaper can scan all spaces' leases in one query (analysis §Next-consumer #4).
- The reaper re-enqueues through the existing `WorkerPool.enqueue(space_id, task_id)` (worker_pool.py:100); no worker_pool.py change is required, so it is intentionally not in any iteration's scope_files.
- The owner identifier is `f"{space_id}:{uuid4()}"` generated once at `Worker.__init__`, unique per process-lifetime Worker (analysis assumption confirmed against worker.py:262–307).
- Constant defaults: `LEASE_TTL=300`, `HEARTBEAT_INTERVAL=15`, `REAPER_INTERVAL=30`, `HEARTBEAT_TIMEOUT=2*HEARTBEAT_INTERVAL`; all are module constants (env-overridable is acceptable but not required by acceptance criteria).
- Per the binding `memory:pipeline-narrow-k-coverage` note, file-scoped validation commands append `--override-ini="addopts="` so the per-iteration pytest run is not failed by the global `--cov-fail-under=60` floor; the tester's full-suite run still enforces the floor.
- The existing markdown-driven startup recovery (`main.py` lines 510–523, scanning `board.active`) remains authoritative and unchanged; I6 only prepends `clear_all_leases()` and appends the reaper task.

## Open questions

- None.

## Next consumer brief

Read `iterations[]`, each `scope_files`, `validation_command`, and `risks[]` from the YAML — that is the machine-readable plan. Cross-iteration invariants the implementors MUST honor literally:
- Lease row tuple order is `(task_id, owner, lease_expiry, heartbeat_at)`; `acquire_lease` returns a bool (True = lease won). I3 depends on this signature from I2.
- The reaper (I5) and worker (I3) share the `task_leases` schema but never call each other; the reaper re-enqueues only via `worker_pool.enqueue(task.space_id, task_id)` and only when `task_store.get(task_id).state == ACTIVE` (markdown gate — do not skip this check).
- Lease release (R6) and heartbeat cancellation MUST share one `try/finally` in `_run_task` so neither is skipped on the exception/cancel path.
- I4 edits worker.py after I3 (serial) — rebase onto I3's diff, do not re-add lease code.
- All validation commands carry `--override-ini="addopts="` deliberately; keep it when running them verbatim.
