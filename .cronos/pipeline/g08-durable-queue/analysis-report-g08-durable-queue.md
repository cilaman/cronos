---
cc_version: '1.0'
agent: pipeline-analyst
slug: g08-durable-queue
phase: analysis
status: done
confidence: 0.92
inputs_used:
- memory:project-remediation-board-setup
- .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
- .cronos/workspaces/2026-06-20-1427-create-remedy-goals/REMEDIATION-PLAN.md
- .claude/agents/pipeline-analyst.md
- backend/app/worker.py
- backend/app/worker_pool.py
- backend/app/storage.py
- backend/app/main.py
outputs_produced:
- .cronos/pipeline/g08-durable-queue/analysis-report-g08-durable-queue.md
blockers: []
next_consumer: design
request: "G08: Durable task queue (SQLite lease/heartbeat/reaper)\n\nFiles: backend/app/worker.py\
  \ (asyncio.Queue, startup recovery, _auto_resume_counts), backend/app/worker_pool.py,\
  \ backend/app/storage.py (SQLite schema).\n\nArchitecture invariant: markdown is\
  \ source of truth; SQLite is a disposable index. Lease rows belong in SQLite index-side\
  \ only. Restart/rebuild must re-derive from markdown state, not from lease rows\
  \ (leases expire; markdown persists).\n\nThe proposed schema:\n  task_leases(task_id\
  \ TEXT PK, owner TEXT, lease_expiry REAL, heartbeat_at REAL)\n  auto_resume_counts(task_id\
  \ TEXT PK, count INTEGER)\n\nDecompose the relevant G-number section into testable\
  \ requirements."
has_ui: false
coverage_summary:
  searched:
  - backend/app/worker.py (lines 280–310, 414–463, 1220–1285)
  - backend/app/worker_pool.py (full)
  - backend/app/storage.py (lines 490–549, schema section)
  - backend/app/main.py (lines 500–560, lifespan startup recovery)
  - .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
  - .cronos/workspaces/2026-06-20-1427-create-remedy-goals/REMEDIATION-PLAN.md §G08
  excluded:
  - frontend/: has_ui=false — backend-only reliability feature
  - backend/app/harnesses/: G09 handles timed-wait; out of scope for G08
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
  - glob_structural
traceability:
- requirement_id: R1
  statement: The SQLite index must contain a `task_leases(task_id TEXT PK, owner TEXT,
    lease_expiry REAL, heartbeat_at REAL)` table, created or migrated idempotently
    alongside existing tables in `_ensure_db_schema()`.
  acceptance_criteria:
  - Given a fresh database, `_ensure_db_schema()` creates the `task_leases` table
    with the specified columns and types.
  - Given an existing database without the table, `_ensure_db_schema()` migrates it
    without error (idempotent).
  - Given the table already exists, a second call to `_ensure_db_schema()` succeeds
    without raising.
  verifying_phase: test
  confidence: 0.97
- requirement_id: R2
  statement: The SQLite index must contain an `auto_resume_counts(task_id TEXT PK,
    count INTEGER)` table, created or migrated idempotently by `_ensure_db_schema()`,
    replacing the in-memory `_auto_resume_counts` dict.
  acceptance_criteria:
  - Given a fresh database, `_ensure_db_schema()` creates the `auto_resume_counts`
    table.
  - Given an existing database without the table, `_ensure_db_schema()` migrates it
    without error.
  - 'No in-memory-only `_auto_resume_counts: dict[str, int]` dict remains as the sole
    store of these counts.'
  verifying_phase: test
  confidence: 0.97
- requirement_id: R3
  statement: Before executing a task, the worker must acquire a lease by inserting
    a row into `task_leases` with a unique `owner` identifier (e.g. `f'{space_id}:{worker_uuid}'`)
    and `lease_expiry = time.time() + LEASE_TTL`.
  acceptance_criteria:
  - Given `_run_task` or `_run_goal` begins, a `task_leases` row for the task exists
    before agent invocation.
  - The row's `owner` is unique per worker instance.
  - The row's `lease_expiry` is strictly in the future at acquisition time.
  verifying_phase: test
  confidence: 0.93
- requirement_id: R4
  statement: If a task already holds a valid (non-expired) lease owned by a different
    `owner`, a second worker that attempts to run the same task must skip it to prevent
    double-execution.
  acceptance_criteria:
  - Given task T has an unexpired lease with owner='worker-A', when worker-B attempts
    to acquire the lease, it detects the conflict and does not execute the task.
  - Given a task's lease has expired, a new worker may acquire it (re-execution allowed).
  verifying_phase: test
  confidence: 0.9
- requirement_id: R5
  statement: 'While a task is executing, the worker must send periodic heartbeats:
    updating `heartbeat_at = time.time()` and extending `lease_expiry = time.time()
    + LEASE_TTL` in the `task_leases` row at a configurable `HEARTBEAT_INTERVAL` (default
    ≤ 30 seconds).'
  acceptance_criteria:
  - Given a task running for 2× HEARTBEAT_INTERVAL, the `heartbeat_at` and `lease_expiry`
    values in `task_leases` advance at least twice.
  - HEARTBEAT_INTERVAL is a configurable constant (or env var) with a default ≤ 30
    seconds.
  - The heartbeat coroutine is cancelled cleanly when the task finishes or is cancelled.
  verifying_phase: test
  confidence: 0.92
- requirement_id: R6
  statement: On task completion (success, WAIT, BLOCKED, or cancellation), the worker
    must delete the task's lease row from `task_leases`.
  acceptance_criteria:
  - Given a task completes normally (any terminal state), no `task_leases` row exists
    for that task afterwards.
  - Given a task is cancelled via `stop_current()`, the lease is also removed.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R7
  statement: A reaper background coroutine must periodically scan `task_leases` for
    rows where `lease_expiry < time.time()`, verify each task is still in ACTIVE state
    (markdown truth), delete the stale lease row, and re-enqueue the task on the appropriate
    space's worker.
  acceptance_criteria:
  - Given a worker holding a lease is killed (simulated by deleting the heartbeat
    update), when the lease expires and the reaper fires, then the task is re-enqueued
    within `LEASE_TTL + REAPER_INTERVAL` seconds.
  - The reaper deletes the expired lease row before re-enqueueing to prevent double
    re-enqueue on consecutive passes.
  - If a task's markdown state is not ACTIVE at reaper time (e.g. moved to done/archived
    externally), the reaper does not re-enqueue it.
  verifying_phase: test
  confidence: 0.92
- requirement_id: R8
  statement: The reaper must run at a configurable `REAPER_INTERVAL` (default ≤ 60
    seconds), establishing a bounded recovery SLA of `LEASE_TTL + REAPER_INTERVAL`
    seconds for a crashed or killed worker.
  acceptance_criteria:
  - The reaper loop fires every `REAPER_INTERVAL` seconds (configurable constant or
    env var, default ≤ 60).
  - An integration test with short `LEASE_TTL` (e.g. 5 s) and `REAPER_INTERVAL` (e.g.
    2 s) confirms re-enqueue occurs within `LEASE_TTL + REAPER_INTERVAL + 1` seconds
    after simulated kill.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R9
  statement: 'The reaper (or heartbeat monitor) must detect and log a wedged-worker
    condition: a task whose `heartbeat_at` has not been updated for longer than a
    configurable `HEARTBEAT_TIMEOUT` (> `HEARTBEAT_INTERVAL`) while its lease has
    not yet expired.'
  acceptance_criteria:
  - Given `now - heartbeat_at > HEARTBEAT_TIMEOUT` and `lease_expiry > now`, a WARNING
    log is emitted identifying the task and wedged condition.
  - This condition is informational only; no re-enqueue is triggered until the lease
    expires.
  - The HEARTBEAT_TIMEOUT constant is configurable and defaults to `2 × HEARTBEAT_INTERVAL`.
  verifying_phase: test
  confidence: 0.87
- requirement_id: R10
  statement: Auto-resume counts must be loaded from `auto_resume_counts` at worker
    startup and persisted on every increment/reset, so the 3-resume limit survives
    a process restart.
  acceptance_criteria:
  - Given a task has auto-resume count = 2 at the time of a process restart, when
    the task is re-enqueued after restart, the count starts from 2 (not 0).
  - On increment, the count is upserted into `auto_resume_counts(task_id, count)`.
  - On task completion (non-max-turns outcome), the `auto_resume_counts` row is deleted.
  - Worker `__init__` loads all rows from `auto_resume_counts` into the in-memory
    dict at construction time.
  verifying_phase: test
  confidence: 0.93
- requirement_id: R11
  statement: On process restart, startup recovery in `main.py` must re-derive which
    tasks to re-enqueue from markdown state (ACTIVE task list), not from lease rows;
    stale lease rows from the prior run are cleaned up at startup (all pre-existing
    leases deleted or expired) to prevent spurious reaper actions.
  acceptance_criteria:
  - The startup lifespan logic (already in `main.py` lines 503–523) remains the authoritative
    source; it scans `board.active` (markdown), not `task_leases`.
  - On startup, all rows in `task_leases` are deleted (or a startup-owner cleanup
    is run) so the reaper starts with a clean slate.
  - A test confirms that stale lease rows do not prevent correct re-enqueueing on
    restart.
  verifying_phase: test
  confidence: 0.9
metrics:
  tool_calls: 16
  files_read: 7
  memory_hits: 1
---

## Summary

G08 adds durable coordination state to Cronos's in-process task queue so that wedged or crashed workers are detected and automatically requeued within a bounded interval. The implementation adds two SQLite tables (`task_leases`, `auto_resume_counts`) to the existing index, modifies the Worker class to acquire/heartbeat/release leases around each task execution, adds a reaper background loop to detect and recover expired leases, and persists the previously-in-memory auto-resume counter so it survives restarts. The architecture invariant (markdown-as-truth, SQLite-as-disposable-index) is preserved: lease rows are index-side coordination state only; the reaper always checks markdown state before acting.

## Scope

### In scope
- `task_leases` SQLite table in `storage.py` (`_ensure_db_schema()`): schema, idempotent migration
- `auto_resume_counts` SQLite table in `storage.py`: schema, idempotent migration
- Lease acquisition, heartbeat coroutine, and lease release integrated into `Worker._run_task` / `Worker._run_goal` in `worker.py`
- Duplicate-execution guard: skip task if a valid lease is already held by another owner
- Reaper background coroutine scanning expired leases and re-enqueueing affected tasks
- Wedged-worker detection via structured log warning (heartbeat stalled, lease not yet expired)
- Durable auto-resume counts: persist/load/clear via `auto_resume_counts` table
- Startup lease cleanup (clear stale lease rows on process start)
- Integration tests covering kill simulation, wedged detection, restart count persistence

### Out of scope
- Any frontend/UI changes (has_ui=false; wedge detection surfaces via logs only)
- Harness executor durability (timed-wait restart is G09)
- Multi-worker-per-space parallelism (one Worker per space invariant preserved)
- Non-SQLite queue backends (Redis, Temporal, DBOS — rejected by REMEDIATION-PLAN.md §G08)
- Cross-restart agent session rebinding (already handled by stored `claude_session_id`)

### Deferred
- UI dashboard for lease/wedge status (G10 covers structured logging and metrics)
- Per-task SLA violation alerting beyond a log WARNING
- Lease table persistence for harness-run nodes (separate concern; G09/harness scope)
- SQLite WAL mode / concurrency tuning if space-fan-out grows (revisit per D3 ADR)

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | `task_leases` SQLite table created idempotently by `_ensure_db_schema()` |
| R2 | `auto_resume_counts` SQLite table created idempotently by `_ensure_db_schema()` |
| R3 | Worker acquires lease before executing a task |
| R4 | Valid lease from another owner prevents double-execution |
| R5 | Worker sends periodic heartbeats extending `lease_expiry` while task runs |
| R6 | Worker releases (deletes) lease on task completion or cancellation |
| R7 | Reaper re-enqueues tasks with expired leases (markdown-state-gated) |
| R8 | Reaper interval is configurable; bounded recovery SLA is `LEASE_TTL + REAPER_INTERVAL` |
| R9 | Wedged-worker condition (stalled heartbeat, live lease) is logged as WARNING |
| R10 | Auto-resume count persisted to SQLite; loaded at startup; cleared on completion |
| R11 | Startup clears stale lease rows; restart re-derives enqueue from markdown state |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (machine-readable source of truth). The body summary below mirrors them in compact form.

- R1 — `task_leases` created on first call, no error if already exists, idempotent migration
- R2 — `auto_resume_counts` created on first call, no error if already exists
- R3 — lease row present in DB before agent is invoked; owner is unique per worker
- R4 — concurrent worker with unexpired foreign lease skips task; expired lease allows takeover
- R5 — `heartbeat_at` and `lease_expiry` advance ≥ 2 times during 2×HEARTBEAT_INTERVAL run; interval ≤ 30 s default
- R6 — no lease row exists after completion or cancel
- R7 — expired-lease task re-enqueued; non-ACTIVE task not re-enqueued; stale row deleted pre-enqueue
- R8 — reaper fires every REAPER_INTERVAL (≤ 60 s default); integration test confirms re-enqueue within `LEASE_TTL + REAPER_INTERVAL + 1` s
- R9 — WARNING logged when `now − heartbeat_at > HEARTBEAT_TIMEOUT` (configurable, default = 2×HEARTBEAT_INTERVAL)
- R10 — count=2 at restart → resumes at 2; increment upserts row; completion deletes row; init loads from DB
- R11 — stale leases cleared at startup; `board.active` (markdown) drives enqueue, not lease table

## Traceability

The full requirement → acceptance criteria → verifying_phase map is the YAML `traceability[]` array. This table is the human-facing routing view.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | `task_leases` table created idempotently by `_ensure_db_schema()` |
| R2 | test | `auto_resume_counts` table created idempotently by `_ensure_db_schema()` |
| R3 | test | Worker acquires lease row before agent invocation |
| R4 | test | Valid foreign lease prevents double-execution; expired lease allows takeover |
| R5 | test | Periodic heartbeat advances `heartbeat_at` and `lease_expiry` during execution |
| R6 | test | Lease row deleted on task completion or cancellation |
| R7 | test | Reaper re-enqueues expired-lease tasks gated on markdown ACTIVE state |
| R8 | test | Reaper interval configurable; bounded recovery SLA verifiable via integration test |
| R9 | test | Wedged-worker WARNING logged when heartbeat stalls before lease expires |
| R10 | test | Auto-resume count persisted, loaded at startup, cleared on completion |
| R11 | test | Stale leases cleared at startup; markdown board.active drives re-enqueue |

## Assumptions

- `_ensure_db_schema()` in `backend/app/storage.py` (lines 493–549) is the correct migration point — confirmed by read; no lease tables exist at commit `a724133`.
- The `asyncio.Queue` at `worker.py:285` remains in place as the immediate in-process dispatch mechanism; the durable layer sits beneath it (lease = coordination fence, queue = execution signal).
- One Worker per space is preserved (`WorkerPool._workers: dict[str, Worker]`); the `owner` identifier for a lease is `f"{space_id}:{uuid4()}"` generated at Worker construction — unique per process-lifetime Worker instance.
- The reaper runs as a background `asyncio.Task` started in the same `lifespan` block as existing background loops in `main.py` (lines 353–570), not as a separate process.
- `LEASE_TTL` default is ≥ 2 × agent max-response time (practically several minutes for long Claude runs); exact value is a design decision, not fixed here. A value of 300 s (5 min) is suggested for the design agent to evaluate.
- has_ui=false rationale: G08 is purely a backend reliability change (SQLite schema + worker loop changes). Wedged-worker detection surfaces via structured log WARNING and the existing task state visible in the Kanban board — no new UI components are required.
- Startup lease cleanup (R11) uses a simple `DELETE FROM task_leases` on process start, which is safe because all in-flight execution is halted by the process restart; any previously-held leases are stale by definition.
- All tests must target ≥ 85% line coverage of new modules per the cross-cutting DoD in REMEDIATION-PLAN.md §5.

## Open questions

- None. All acceptance criteria derive directly from REMEDIATION-PLAN.md §G08 with confirmed code references. The design agent will determine concrete constant values (LEASE_TTL, HEARTBEAT_INTERVAL, REAPER_INTERVAL) and the reaper's integration point into the existing lifespan loop.

## Next consumer brief

**Design agent reads:** `traceability[]` (11 requirements, all `verifying_phase: test`), `has_ui: false`, `## Scope` boundaries.

**Key design decisions to resolve:**

1. **Constant values** — choose `LEASE_TTL` (suggested 300 s), `HEARTBEAT_INTERVAL` (≤ 30 s, suggested 15 s), `REAPER_INTERVAL` (≤ 60 s, suggested 30 s), `HEARTBEAT_TIMEOUT` (suggested `2 × HEARTBEAT_INTERVAL`). Trade-off: shorter values reduce recovery latency but increase SQLite write frequency.

2. **Heartbeat coroutine placement** — recommend an `asyncio.create_task()` inside `_run_task` / `_run_goal`, cancelled via a shared event. Ensure it does not outlive the parent task coroutine on exception.

3. **Reaper integration** — recommend a `_reaper_loop()` async function started alongside the existing cron and event-worker tasks in `main.py lifespan`; it calls a `TaskStore.get_expired_leases()` helper that returns `list[str]` task IDs.

4. **Storage access from reaper** — the reaper needs direct SQLite access (not the in-memory `Worker` methods) to scan all spaces' leases in one query; design should consider whether `TaskStore` gains new lease-CRUD methods or a separate `LeaseStore` class.

5. **Duplicate-execution guard (R4)** — must be transactionally safe: `INSERT OR IGNORE` / `SELECT → INSERT` race. Consider SQLite `BEGIN EXCLUSIVE` or `INSERT OR IGNORE` + row-count check pattern.

6. **Architecture invariant enforcement (R11)** — the reaper verifies markdown state (`task_store.get(task_id).state == ACTIVE`) before acting; design must ensure this check happens inside the reaper, not inside Worker (which may be mid-run for another task).
