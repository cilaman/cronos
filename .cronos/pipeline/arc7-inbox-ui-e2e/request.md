# Arc 7/S4 — Inbox panel + two-task e2e

**Frontend:** add `Message` to `frontend/src/types.ts`;
surface a task's messages either as a new
`frontend/src/components/InboxPanel.tsx` or a section in
`frontend/src/components/ConversationStream.tsx`
— sender, subject, payload, read state — updating live off the
existing `/api/tasks/{id}/stream` SSE (`message` events) via
`useLiveStream`. Include a small manual "send message" composer for
testing. Match the paper/ink card styling (use [[frontend-design]]).
TanStack key `["inbox", spaceId, taskId]`, invalidate on `message`
event.

**End-to-end pytest** (deterministic, no network): task A's run calls
`SendMessage` to `agent://<space>/<B>`; assert B's mailbox file
exists, B is woken (enqueued with the pending poke), B's run calls
`ReadInbox` and receives the payload, and both runs' traces record the
message. Drive the MCP tools against the in-process API (FastAPI
TestClient); stub the agent subprocess.

**Scope files:** `frontend/src/types.ts`,
`frontend/src/components/InboxPanel.tsx` (new) +/or
`ConversationStream.tsx`, a React Query hook under
`frontend/src/hooks/`, and `backend/tests/test_messaging_e2e.py` (new).

**Acceptance:** inbox panel renders messages + read state and updates
live on delivery; manual composer sends; the e2e test passes covering
send → wake → read → trace end to end.

**Depends on:** Arc 7/S2 (arc7-agent-mail-tools) and Arc 7/S3
(arc7-wake-and-trace) must be complete before starting this pipeline.

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

