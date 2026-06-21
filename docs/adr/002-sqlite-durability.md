# ADR 002: SQLite as durable-queue substrate (over Postgres, Redis, or LangGraph)

## Status

Accepted

## Date

2026-06-20

## Context

G08 introduced durable task execution: a `task_leases` table that gives each
worker a lease with a heartbeat, and a reaper that reclaims crashed leases on
startup. The implementation needed a persistence substrate for the lease and
heartbeat records.

Candidates considered:

1. **Postgres** — strong durability, horizontal scaling, full SQL. Requires a
   separate service, data volume, and network path; significant ops overhead for a
   single-VPS personal system.
2. **Redis** — fast, purpose-built for ephemeral coordination. Adds another service
   and persistence configuration; TTL semantics differ from SQL-style leases.
3. **LangGraph / Temporal-style checkpointing** — framework-level durability that
   checkpoints graph state between node executions. Does not close the crash-mid-run
   gap for long agent invocations because it captures state *between* nodes, not
   *inside* an agent run that may last 30–60 minutes.
4. **SQLite (existing `cronos-index.db`)** — already present, already proven,
   zero additional ops, transactional writes, POSIX file locks.

## Decision

**Use SQLite (`cronos-index.db`) for the lease and heartbeat tables.** No new
services are added.

The G08 `task_leases` table stores `(task_id, worker_id, acquired_at, expires_at,
heartbeat_at)`. The worker updates `heartbeat_at` on a fixed interval to prove
liveness. The reaper on startup clears expired leases and re-enqueues the
corresponding tasks for retry. This is sufficient durability for a single-VPS
personal system with no concurrent worker fleet.

LangGraph- and Temporal-style checkpoint frameworks were explicitly ruled out:
they checkpoint *between* DAG nodes, not *inside* a long-running agent subprocess.
A Claude Code agent run that crashes 45 minutes in produces no checkpoint; the
lease reaper detects the missing heartbeat and re-queues the task from the start.
That restart behaviour is acceptable for this system's workload.

The `revisit` condition: if Cronos ever needs horizontal worker scaling (multiple
VPS nodes sharing a single task queue), SQLite's file-lock model becomes a
bottleneck and Postgres or a purpose-built queue should replace `task_leases`.

## Consequences

- `task_leases` and `auto_resume_counts` live in `cronos-index.db` (transient
  coordination per ADR 001). A startup reaper reconciles them against `.md` task
  files; crash recovery requires no human intervention.
- The worker heartbeat interval and lease expiry are tuned for single-process
  execution. The lease TTL must comfortably exceed the maximum expected agent run
  duration; the current default is 90 minutes.
- No new services or infrastructure are introduced. Backup and restore procedures
  are unchanged.
- If the system outgrows single-VPS SQLite, the revisit path is: extract lease
  logic into an abstraction layer, replace SQLite backend with Postgres, keep
  the markdown-as-truth invariant (ADR 001) intact.
