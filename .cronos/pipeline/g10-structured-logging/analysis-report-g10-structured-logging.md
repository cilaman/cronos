---
cc_version: '1.0'
agent: pipeline-analyst
slug: g10-structured-logging
phase: analysis
status: done
confidence: 0.9
inputs_used:
- memory:project-remediation-board-setup
- memory:project_pipeline_analyst_agent
- .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
- .cronos/workspaces/2026-06-20-1427-create-remedy-goals/REMEDIATION-PLAN.md
- backend/app/main.py
- backend/app/worker.py
- backend/app/agent.py
- backend/app/harnesses/executor.py
outputs_produced:
- .cronos/pipeline/g10-structured-logging/analysis-report-g10-structured-logging.md
blockers: []
next_consumer: design
request: 'G10: Structured logging + correlation IDs + metrics + notifications. Add
  observability to the unattended-operation core. After: a single run_id traces a
  task end-to-end across worker/harness/agent logs; JSON-structured logs emitted by
  the backend (configurable format); a metrics endpoint or structured log output covering
  queue depth, task durations, failure counts, and auto-resume rate; a push notification
  is sent on terminal/needs-human states.'
has_ui: false
coverage_summary:
  searched:
  - backend/app/main.py (logging setup, format string)
  - backend/app/worker.py (log calls, run_id usage, WAITING transitions)
  - backend/app/agent.py (run_agent log calls, task_id references)
  - backend/app/harnesses/executor.py (run_goal_id scope, log calls)
  excluded:
  - frontend/: no UI changes required — observability is backend-only
  - backend/app/harnesses/wait.py: in-scope for G09, not G10
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
  - grep_keyword
traceability:
- requirement_id: R1
  statement: The backend emits JSON-structured log records instead of plain-text formatted
    strings.
  acceptance_criteria:
  - 'Given the backend starts, when any log.info/warning/error call fires, then each
    line written to stdout/stderr is valid JSON with at minimum the keys: timestamp
    (ISO-8601), level, logger, message.'
  - 'The logging.basicConfig format string in main.py (currently ''%(asctime)s %(levelname)s
    %(name)s: %(message)s'') is replaced with a JSON formatter or structlog processor.'
  - Existing free-text format strings in log calls (e.g. 'Enqueued task %s (queue
    size=%d)') are preserved as the message value; they do not need rewriting.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R2
  statement: Every log record emitted during a task run in worker.py carries a run_id
    field whose value uniquely identifies that execution.
  acceptance_criteria:
  - Given a task enters _run_task(), when any log call fires within that task's execution
    scope, then the JSON record includes run_id matching the task's active run identifier.
  - run_id must also propagate into _finalize(), _finalize_child(), and any sub-calls
    that produce log output for that task.
  - run_id is not hardcoded — it is bound at execution entry (via contextvars.ContextVar
    or structlog.contextvars.bind_contextvars) so callers do not pass it explicitly.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R3
  statement: Every log record emitted by agent.py during run_agent() carries a run_id
    and task_id field.
  acceptance_criteria:
  - Given run_agent() is called for a task, when any log call fires inside run_agent()
    or its nested helpers, then the JSON record includes both run_id and task_id.
  - task_id is the task.id value already in scope; run_id is the value propagated
    from the caller's context.
  - Log calls in drain_stderr(), the stdout-parsing loop, and the cancellation path
    all carry both fields.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R4
  statement: Every log record emitted by harnesses/executor.py during a harness run
    carries the harness run_id.
  acceptance_criteria:
  - Given HarnessExecutor.execute() is called with a run_goal_id, when any log call
    fires within that harness execution, then the JSON record includes run_id equal
    to run_goal_id.
  - The run_id binding is established once at harness execution entry and inherited
    by all node-dispatch paths (agent, decision, wait, aggregator).
  verifying_phase: test
  confidence: 0.9
- requirement_id: R5
  statement: GET /api/metrics returns a JSON document with queue depth, active task
    count, failure counts, and auto-resume rate.
  acceptance_criteria:
  - 'GET /api/metrics (no auth required, same as /api/health) returns HTTP 200 with
    Content-Type: application/json.'
  - 'The response contains at minimum: queue_depth (current asyncio queue size across
    all workers), active_tasks (count of tasks in ACTIVE state), auto_resume_total
    (cumulative auto-resume events since last restart).'
  - 'Optional fields: completed_tasks, failed_tasks if derivable from in-memory counters
    without a full DB scan.'
  - The endpoint must not introduce significant latency (no blocking DB queries in
    the hot path).
  verifying_phase: test
  confidence: 0.85
- requirement_id: R6
  statement: When a task transitions to WAITING (needs-human) or a terminal-error
    state (exit_reason in {ERROR, KILLED, NO_CRONOS_STATUS with non-zero exit}), the
    system sends a push notification to a configurable webhook URL.
  acceptance_criteria:
  - If CRONOS_NOTIFY_URL is set, the system POSTs a JSON body {task_id, task_title,
    status, exit_reason, summary} to that URL when the conditions above are met.
  - If CRONOS_NOTIFY_URL is unset or empty, notification silently skips (no error
    logged, no exception raised).
  - A notification failure (HTTP error, network timeout) is caught and logged at WARNING
    level; it must not affect task state transitions.
  - Notification is triggered from the finalize path in worker.py where WAITING and
    error transitions currently live (lines ~142–146 and ~933).
  verifying_phase: test
  confidence: 0.88
- requirement_id: R7
  statement: The backend log level is controllable via the CRONOS_LOG_LEVEL environment
    variable without code changes.
  acceptance_criteria:
  - 'The CRONOS_LOG_LEVEL env var (values: DEBUG, INFO, WARNING, ERROR; default: INFO)
    is read at startup and sets the root logging level.'
  - Setting CRONOS_LOG_LEVEL=DEBUG enables debug-level output from cronos.* loggers.
  - An invalid value logs a warning and falls back to INFO.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R8
  statement: Logging format, metrics endpoint, and notification configuration are
    documented.
  acceptance_criteria:
  - 'A README section or in-code config block documents: the JSON log field names
    (timestamp, level, logger, message, run_id, task_id), the /api/metrics endpoint
    and its response schema, and the CRONOS_NOTIFY_URL and CRONOS_LOG_LEVEL env vars.'
  - Documentation is accurate against the implemented field names (not aspirational).
  verifying_phase: review
  confidence: 0.92
metrics:
  tool_calls: 12
  files_read: 6
  memory_hits: 2
---

## Summary

G10 adds end-to-end observability to Cronos's unattended execution core. The system currently uses Python's `logging` module with a plain-text format (`%(asctime)s %(levelname)s %(name)s: %(message)s`), no `run_id` correlation across the worker/harness/agent path, no metrics endpoint, and no notification mechanism. This goal replaces the format with JSON-structured output, binds `run_id` into all log records within a task execution scope via Python `contextvars` or `structlog.contextvars`, adds a lightweight `GET /api/metrics` endpoint, and sends a webhook notification (opt-in via `CRONOS_NOTIFY_URL`) when tasks reach needs-human or error terminal states.

## Scope

### In scope
- JSON log format replacing `logging.basicConfig` plain-text format in `main.py`
- `run_id` + `task_id` context binding in `worker.py` task execution paths
- `run_id` + `task_id` context binding in `agent.py` `run_agent()` function
- `run_id` context binding in `harnesses/executor.py` harness execution entry
- `GET /api/metrics` endpoint on the FastAPI app (in `main.py` or a new `api/metrics.py` router)
- Push notification via HTTP POST to `CRONOS_NOTIFY_URL` on WAITING / terminal-error state transitions (triggered from `worker.py` finalize path)
- `CRONOS_LOG_LEVEL` env var for runtime log-level control
- Documentation of JSON fields, metrics endpoint, and env vars

### Out of scope
- Full observability stack (OpenTelemetry collector, Prometheus, Grafana, dashboards)
- Distributed tracing spans (Jaeger, Zipkin)
- Log aggregation infrastructure (ELK, Loki)
- Notification channels beyond a single configurable webhook (no native Slack/PagerDuty/SMS integrations)
- UI changes of any kind

### Deferred
- Per-task duration metrics (requires persisting task start timestamps; can ride with G08 lease tables)
- Notification retry logic with backoff
- Structured metrics in Prometheus exposition format (can add later if needed)
- Multiple notification channels / routing rules

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | Backend emits JSON-structured log records instead of plain-text |
| R2 | `run_id` in every worker.py log record within a task execution scope |
| R3 | `run_id` + `task_id` in every agent.py log record during `run_agent()` |
| R4 | Harness `run_id` in every executor.py log record during a harness run |
| R5 | `GET /api/metrics` returns queue depth, active task count, auto-resume total |
| R6 | Push notification to `CRONOS_NOTIFY_URL` on WAITING or terminal-error state |
| R7 | `CRONOS_LOG_LEVEL` env var controls root logging level at startup |
| R8 | Logging format, metrics endpoint, and env vars documented |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]`
array (the machine-readable source of truth). Compact summary:

- R1 — Every log line is valid JSON with `timestamp`, `level`, `logger`, `message`; `logging.basicConfig` format string replaced
- R2 — All log records in `_run_task` / `_finalize` / `_finalize_child` carry `run_id` without explicit argument threading
- R3 — All log records in `run_agent()`, `drain_stderr()`, and cancellation path carry `run_id` + `task_id`
- R4 — All log records in `executor.execute()` and node-dispatch methods carry `run_id` = `run_goal_id`
- R5 — `GET /api/metrics` returns 200 JSON with `queue_depth`, `active_tasks`, `auto_resume_total`; no blocking DB queries
- R6 — WAITING / terminal-error → POST to `CRONOS_NOTIFY_URL`; absent URL = silent skip; failure = WARNING log only
- R7 — `CRONOS_LOG_LEVEL` env var sets root level; invalid value → WARNING + INFO fallback
- R8 — README/config documents JSON fields, `/api/metrics` schema, `CRONOS_NOTIFY_URL`, `CRONOS_LOG_LEVEL`

## Traceability

The full requirement → acceptance criteria → verifying_phase map is the YAML
`traceability[]` array. Downstream agents read the YAML directly.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | Backend emits JSON-structured log records |
| R2 | test | worker.py log records carry run_id within task scope |
| R3 | test | agent.py log records carry run_id + task_id during run_agent() |
| R4 | test | executor.py log records carry harness run_id |
| R5 | test | GET /api/metrics returns queue depth, active task count, auto-resume total |
| R6 | test | Push notification sent on WAITING/terminal-error; silent if URL unset |
| R7 | test | CRONOS_LOG_LEVEL controls root log level; fallback on invalid value |
| R8 | review | Logging format, metrics endpoint, and env vars documented |

## Assumptions

- **has_ui=false rationale:** G10 is backend observability only — no new screens, forms, or visual state changes. The existing frontend SSE stream already surfaces task status; the metrics endpoint is consumed externally (CLI, monitoring scripts), not via the Cronos UI.
- **Technology choice (design decision):** The choice between Python `logging` + a JSON formatter (e.g. `python-json-logger`) and `structlog` is left to the architect. Either satisfies R1–R4; the key constraint is no new infrastructure (no OpenTelemetry collector, Prometheus). `contextvars.ContextVar` or `structlog.contextvars.bind_contextvars` are the two implementation shapes for R2–R4.
- **run_id source in worker.py:** The task's "run_id" for correlation purposes is the task's own `task_id` (tasks are uniquely identified per-run) supplemented by any harness `run_goal_id` for harness runs. Scout confirmed `run_id` already exists as a concept in executor.py's `run_goal_id` and in `_run_id_to_space_id` in worker.py. The design agent must decide the canonical field name.
- **Metrics freshness:** R5 requires no blocking DB queries. Queue depth is `self._queue.qsize()` (O(1)), active task count is derivable from in-memory state, auto-resume total from `_auto_resume_counts`. Per-task duration metrics are deferred because they require persisting start timestamps (G08 scope).
- **Notification scope:** Only `WAITING` and hard-error terminal states trigger notifications. `DONE` transitions do not (not actionable for an unattended operator who only needs to know when something needs attention).
- **Scout confidence:** Scout `status=done`, `confidence=0.92` — upper bound on this report's confidence is 0.92; this report's confidence is 0.90 due to implementation detail ambiguities in context-binding approach (design-time decision).

## Open questions

- None. The implementation approach (logger vs structlog, JSON formatter library) is a design-phase decision; both options satisfy the requirements as stated.

## Next consumer brief

**Design agent reads:** `traceability[]` (8 requirements, R1–R8), `has_ui: false`, `## Scope` IN/OUT/DEFERRED boundaries.

**Key design decisions for the architect:**
1. **Context propagation mechanism** — choose between `contextvars.ContextVar` (stdlib, works with `logging`) or `structlog.contextvars.bind_contextvars` (requires adding `structlog` dep). The key constraint: the binding must work across `await` boundaries in asyncio without explicit argument threading.
2. **JSON formatter** — if staying with `logging`: `python-json-logger` (pypi: `python-json-logger`) is the common choice; add to `pyproject.toml` `[project.dependencies]`.
3. **Metrics endpoint placement** — either inline in `main.py` (simple, no new file) or a new `backend/app/api/metrics.py` router; the latter is cleaner for testing.
4. **Notification trigger point** — the finalize path in `worker.py` at line ~142 (exit_reason-based WAITING) and line ~933 (agent error) are the two insertion points. A thin `notifier.py` module (async HTTP POST via `aiohttp` or `httpx`) isolates the concern and simplifies testing with monkeypatching.
5. **run_id field name** — must be consistent across worker, agent, and executor. Recommend `run_id` (already used in executor SSE events) rather than inventing a new name.
6. **Risk:** `harnesses/executor.py` uses `log = logging.getLogger(__name__)` which resolves to the module name `app.harnesses.executor`. Ensure the JSON formatter is wired at the root logger level (not just `cronos.*`) so `__name__`-based loggers are also captured in JSON format.
