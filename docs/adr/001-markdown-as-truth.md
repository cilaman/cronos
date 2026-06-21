# ADR 001: Markdown as truth, SQLite as disposable index

## Status

Accepted

## Date

2026-06-20

## Context

Cronos stores its tasks, goals, and spaces as `.md` files under `.cronos/` within
a space directory. Alongside them, `cronos-index.db` (SQLite) is built from those
files at startup and kept in sync at runtime.

Two competing approaches were considered:

1. **SQLite as truth, markdown as export** — the canonical state lives in the database;
   markdown files are a human-readable snapshot.
2. **Markdown as truth, SQLite as index** — the canonical state lives in `.md` files;
   the database is a disposable performance cache that can be discarded and rebuilt
   at any time.

The system is deployed on a single VPS with no replication; crash scenarios are
real. In a torn dual-write scenario (markdown written, database not yet updated, or
vice versa), one of the two representations must be considered authoritative so the
system can recover without human intervention.

## Decision

**Markdown files are the single source of truth.** `cronos-index.db` is a
disposable performance index: it can be deleted and will be rebuilt correctly from
the `.md` files on next startup. No state exists solely in the database.

This is the **self-healing** invariant: if `cronos-index.db` is corrupt, missing,
or stale, deleting it and restarting the backend is always a correct recovery path.

The implication for G08 (durable task queue): task lease and heartbeat records (see
ADR 002) live in `cronos-index.db` because they are transient coordination data, not
durable task state. A lease row is not a task — it is a claim on a task. Leases are
intentionally ephemeral: a reaper reconciles them at startup against the `.md` files.
Losing lease rows on a crash is safe because the markdown source of truth is intact.

## Consequences

- Any new persistence feature must classify its data as either **durable state**
  (→ markdown) or **transient coordination** (→ SQLite-only).
- The startup path must be able to rebuild the full index from `.md` files alone;
  this constrains schema migrations.
- `cronos-index.db` is excluded from backups or treated as reconstructible; the
  nightly backup targets `/opt/cronos/data` which includes both, but restore is
  always tested by deleting the `.db` and restarting — not by restoring the `.db`.
- G08 task leases live in `cronos-index.db` (transient); the task `.md` files
  remain the durable record. See ADR 002 for the durability substrate choice.
