Expose the `DevRuntimeManager` (SG2) over HTTP and stream its logs
via SSE.

**Wire the manager.** Construct `DevRuntimeManager` in the lifespan
([main.py:147-232](backend/app/main.py#L147-L232)) alongside
`worker_pool` ([main.py:192](backend/app/main.py#L192)); stash on
`app.state.dev_runtime_manager`. Add
`await dev_runtime_manager.stop_all()` to the `finally` block
([main.py:223-232](backend/app/main.py#L223-L232)).

**Endpoints.** New `backend/app/api/dev_runtime.py` router
registered at [main.py:238-246](backend/app/main.py#L238-L246)
under `dependencies=_auth`:
- `POST /api/spaces/{id}/dev/start | /stop | /restart` → returns
  `DevRuntimeStatus`.
- `GET /api/spaces/{id}/dev/status` →
  `{state, pid, ports, health, url}`.
- `GET /api/spaces/{id}/dev/stream` → SSE log stream.

Read shared state via `request.app.state.*` like
[spaces.py:46-55](backend/app/api/spaces.py#L46-L55). Return 404
when the space has no `dev_runtime` config; 409 on `start` when
already running.

**SSE.** Clone `stream_space`
([spaces.py:130-148](backend/app/api/spaces.py#L130-L148)):
`StreamingResponse(..., media_type="text/event-stream",
headers={Cache-Control, X-Accel-Buffering, Connection})`. The
generator mirrors `sse_space_events`
([worker.py:986-1002](backend/app/worker.py#L986-L1002)) — emit
`": ok\n\n"`, drain the replay buffer, stream live
`data: {json}\n\n` lines from `manager.subscribe(space_id)`, and
`event: end` on process exit.

**Acceptance:** `start` returns 200 with `state=running`; `status`
reflects state + ports + health; `stream` emits captured log lines
then `end` on stop; `stop` returns 200/204; `start` on a space
without `dev_runtime` → 404; `start` twice → 409.

