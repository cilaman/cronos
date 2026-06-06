# Arc 7/S2 — MCP mail tools + mount into agent runs

New `backend/app/messaging_mcp.py` — a stdio MCP server
(entry `python -m app.messaging_mcp`) exposing two tools that
proxy the S1 HTTP API for the **current run's task**:
- `SendMessage(to, subject, body, payload)` → `POST /api/messages/send`.
- `ReadInbox(unread_only=true)` → `GET …/inbox`, returns structured
  messages. It reads `CRONOS_API_BASE`, `CRONOS_TASK_ID`,
  `CRONOS_SPACE_ID` from env to fill `from`/inbox addressing.

Wire into `backend/app/agent.py:223-247`:
- Write a per-run `.mcp.json` into the workspace describing the
  `cronos` stdio server; pass `--mcp-config <path>`.
- Append `mcp__cronos__SendMessage,mcp__cronos__ReadInbox` to **both**
  `PLAN_MODE_TOOLS` and `DEFAULT_TOOLS` in `backend/app/agent.py:132-133`
  in the `--allowedTools` value.
- Inject `CRONOS_API_BASE`/`CRONOS_TASK_ID`/`CRONOS_SPACE_ID` into the
  subprocess env (the local API base + the running task/space).

**Scope files:** `backend/app/messaging_mcp.py` (new),
`backend/app/agent.py` (tool consts, command builder, env injection).

**Acceptance:** a `run_agent` unit test asserts the built command
includes `--mcp-config` and the two `mcp__cronos__*` tool names, and the
env carries the task/space ids; the MCP server's `SendMessage` round-trips
through the S1 API into a recipient mailbox; `ReadInbox` returns it.

**Depends on:** Arc 7/S1 (arc7-mailbox-broker) must be complete before
starting this pipeline.

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

