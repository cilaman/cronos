# Arc 7/S3 — Wake-on-delivery + replayable message trace

Make delivery wake an idle recipient and make messages replayable.

**Wake-on-delivery:** on `MessageBroker.send`, look up the recipient
task; if it is **not** currently active, `append_pending` a
human-readable poke (`📬 message from <from_addr>: <subject> — call
ReadInbox`) and `enqueue` it on its space worker (reuse
`backend/app/storage.py:925`, `backend/app/worker.py:139`). If active,
the message simply lands in the mailbox for the next `ReadInbox`. Route
through a small worker hook so the broker stays transport-agnostic; the
existing `on_idle` path (`backend/app/worker.py:222`) drains pending as
today.

**Trace persistence:** extend `RunTrace` in
`backend/app/trace_parser.py:110-140` with `messages_sent: list[...]`
/ `messages_received: list[...]` (id, addr, subject, ts), populated when
a run's `SendMessage`/`ReadInbox` tool calls are parsed from the stream.
Persisted in the run JSON via `backend/app/trace_store.py` → replayable.

**Scope files:** `backend/app/worker.py`, `backend/app/messaging.py`
(broker→worker hook), `backend/app/trace_parser.py`,
`backend/app/trace_store.py` (only if a schema bump is needed).

**Acceptance:** sending to a `backlog`/`waiting` task enqueues it with a
`pending_messages` poke and it transitions to `active`; sending to an
already-active task does not double-enqueue; a run that called the mail
tools has non-empty `messages_sent`/`messages_received` in its persisted
trace.

**Depends on:** Arc 7/S1 (arc7-mailbox-broker) and Arc 7/S2
(arc7-agent-mail-tools) must be complete before starting this pipeline.

---

## Standing rules (apply to every phase of this pipeline)

**Branch:** all phase work commits to `feature/arc-7-messaging` (create from
`main` if missing; never branch from another base). Use [[goal-task-commit]]
after the review phase verdict is `pass`. **Do NOT call /goal-finalize in the
doc phase** — the `feature/arc-7-messaging` branch is shared across all four
Arc 7 subgoals and will be manually merged to `main` only after all subgoals
complete. The doc phase simply emits `STATUS: DONE` after the gate passes,
without merging.

**Locked design:** MCP stdio server for `SendMessage`/`ReadInbox`; file-backed
mailboxes at `{space}/.cronos/mailboxes/<task_id>/`; address
`agent://<space_id>/<task_id>`; reuse `pending_messages`, the worker event bus,
`on_idle`/`enqueue`, and `/api/tasks/{id}/stream` SSE. Do not introduce SQLite
tables, Redis, or an HTTP MCP transport.

**Test gate:** the pipeline's own `test` + `review` phases are the gate —
pytest (≥60% floor) and vitest must pass before `doc`. Commit only after the
review phase verdict is `pass`.

**STATUS / gating** is owned by `/pipeline-gate` at each phase; do not emit
STATUS by hand.

