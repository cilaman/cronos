# Arc 7/S1 — Mailbox broker + persistence + API

New `backend/app/messaging.py`:
- `Message` Pydantic model: `id, from_addr, to_addr, subject, body,
  payload: dict, created_at, delivered_at: datetime|None,
  read_at: datetime|None`.
- `MessageStore` — file-as-truth: one atomic JSON per message under
  `{space}/.cronos/mailboxes/<task_id>/<msg_id>.json` (reuse the
  tmp→rename `atomic_write` pattern from
  `backend/app/trace_store.py`). Methods: `save(msg)`,
  `inbox(space_id, task_id, unread_only=False) -> list[Message]`
  (order-stable by `created_at`), `mark_read(space_id, task_id, msg_id)`.
- `MessageBroker` — in-process singleton: `send(msg)` resolves the
  `agent://` address, persists via `MessageStore`, then publishes a
  `message` event onto the worker event bus so subscribers update live.
  Address parse/format helpers `parse_addr`/`format_addr`.

New `backend/app/api/messaging.py` (registered in
`backend/app/main.py:237` like the other routers):
- `POST /api/messages/send` body `{to, subject, body, payload}` → 201
  with the stored `Message` (sender resolved from request context;
  explicit `from` allowed for manual/testing sends).
- `GET /api/spaces/{id}/tasks/{task_id}/inbox?unread=<bool>` → messages.
- `POST /api/spaces/{id}/tasks/{task_id}/inbox/{msg_id}/read` → 204.

**Scope files:** `backend/app/messaging.py` (new),
`backend/app/api/messaging.py` (new), `backend/app/main.py` (router
registration only).

**Acceptance:** `send` writes one JSON + returns it; `inbox` lists it
order-stably; `unread` filter + `mark_read` flips `read_at`; broker
publishes a `message` event observable via the worker bus. Invalid
`agent://` address → 422.

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

