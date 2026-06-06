Expose the runtime over HTTP and round out lifecycle in `backend/app/api/harnesses.py`.

- `POST .../harnesses/<name>/run` — manual trigger, returns `run_id`.
- `GET  .../harnesses/<name>/runs` — run-history list.
- `GET  .../harness-runs/<run_id>` — status: per-node state, chosen edges, child ids,
  timings (snapshot; avoid N+1 trace reads).
- `POST .../harness-runs/<run_id>/cancel` — stop the current child (`stop_current` /
  `_current_cancel`), abort the interpreter, mark the run failed atomically. `DELETE` a
  harness with active runs handled cleanly.
- **Run-level SSE** `GET .../harness-runs/<run_id>/stream` emitting node/edge transitions,
  built on `subscribe`/`sse_events`/`_run_buffer` replay in worker.py (late joiners get
  the backlog).

Acceptance: POST /run executes; GET status reflects live per-node state; cancel stops a
mid-flight run; SSE replays prior transitions to a late subscriber.

