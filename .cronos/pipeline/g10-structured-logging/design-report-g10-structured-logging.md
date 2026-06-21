---
cc_version: '1.0'
agent: pipeline-architect
slug: g10-structured-logging
phase: design
status: done
confidence: 0.88
inputs_used:
- memory:project-remediation-board-setup
- memory:project_pipeline_foundation_merged
- memory:project_pipeline_architect_agent
- .cronos/pipeline/g10-structured-logging/analysis-report-g10-structured-logging.md
- .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
- backend/app/main.py
- backend/app/worker.py
- backend/app/worker_pool.py
- backend/pyproject.toml
outputs_produced:
- .cronos/pipeline/g10-structured-logging/design-report-g10-structured-logging.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - backend/app/main.py
  - backend/app/worker.py
  - backend/app/worker_pool.py
  - backend/app/agent.py
  - backend/app/harnesses/executor.py
  - backend/app/api/
  - backend/pyproject.toml
  excluded:
  - frontend/: backend-only observability (has_ui=false)
  - backend/app/harnesses/wait.py: in-scope for G09, not G10
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
iterations:
- id: I1
  type: backend
  scope_files:
  - backend/app/logging_config.py
  - backend/app/main.py
  - backend/tests/test_logging_config.py
  validation_command: cd backend && pytest tests/test_logging_config.py -v
  max_diff_lines: 300
  depends_on: []
- id: I2
  type: backend
  scope_files:
  - backend/app/worker.py
  - backend/tests/test_worker_run_id_logging.py
  validation_command: cd backend && pytest tests/test_worker_run_id_logging.py -v
  max_diff_lines: 250
  depends_on:
  - I1
- id: I3
  type: backend
  scope_files:
  - backend/app/agent.py
  - backend/tests/test_agent_run_id_logging.py
  validation_command: cd backend && pytest tests/test_agent_run_id_logging.py -v
  max_diff_lines: 250
  depends_on:
  - I1
- id: I4
  type: backend
  scope_files:
  - backend/app/harnesses/executor.py
  - backend/tests/test_executor_run_id_logging.py
  validation_command: cd backend && pytest tests/test_executor_run_id_logging.py -v
  max_diff_lines: 200
  depends_on:
  - I1
- id: I5
  type: backend
  scope_files:
  - backend/app/api/metrics.py
  - backend/app/main.py
  - backend/tests/test_metrics_endpoint.py
  validation_command: cd backend && pytest tests/test_metrics_endpoint.py -v
  max_diff_lines: 300
  depends_on: []
- id: I6
  type: backend
  scope_files:
  - backend/app/notifier.py
  - backend/app/worker.py
  - backend/tests/test_notifier.py
  - backend/tests/test_worker_notifier_trigger.py
  validation_command: cd backend && pytest tests/test_notifier.py tests/test_worker_notifier_trigger.py
    -v
  max_diff_lines: 400
  depends_on:
  - I1
  - I2
- id: I7
  type: backend
  scope_files:
  - README.md
  - backend/app/logging_config.py
  validation_command: cd backend && python -c "import pathlib; readme = pathlib.Path('../README.md').read_text();
    assert 'CRONOS_LOG_LEVEL' in readme and 'CRONOS_NOTIFY_URL' in readme and '/api/metrics'
    in readme and 'run_id' in readme, 'README missing G10 observability docs'"
  max_diff_lines: 200
  depends_on:
  - I1
  - I5
  - I6
risks:
- description: JSON formatter wired only to the 'cronos' logger would miss records
    from module-named loggers like 'app.harnesses.executor' (which uses logging.getLogger(__name__)),
    violating R1's 'every line is JSON' criterion.
  severity: high
  mitigation: I1 installs the JSON formatter on the ROOT logger (logging.getLogger())
    by replacing root handlers, not on the 'cronos' child logger. I1's test asserts
    that a log call from a module-named logger (e.g. 'app.harnesses.executor') produces
    valid JSON on capsys.
- description: contextvars.ContextVar bindings can leak across asyncio tasks if set
    without a token-based reset, polluting unrelated concurrent task logs with a stale
    run_id (especially in WorkerPool which serializes per-space but the executor may
    spawn parallel node-dispatch coroutines).
  severity: medium
  mitigation: I1 exposes a `bind_run_context(run_id, task_id)` context manager that
    captures the Token and resets in finally; I2/I3/I4 wrap their execution entry
    points (e.g. _run_task body, run_agent body, HarnessExecutor.execute body) in
    `with bind_run_context(...)` rather than calling .set() directly. Tests in I2/I3/I4
    verify that after the wrapped scope exits, a follow-up log call from the same
    coroutine does NOT carry the stale run_id.
- description: The notifier HTTP POST (R6) running synchronously inside the worker
    finalize path could block task-state transitions if the configured webhook URL
    is slow or hangs, causing a backlog of WAITING tasks not transitioning.
  severity: medium
  mitigation: I6's notifier uses httpx.AsyncClient with an explicit timeout=5.0 (connect+read)
    and is fired via `asyncio.create_task(notify(...))` (fire-and-forget) from the
    finalize path. All exceptions inside the notifier coroutine are caught and logged
    at WARNING level so a failed POST never propagates. I6 tests include a hung-server
    case (monkeypatched httpx that sleeps past timeout) and assert finalize_run still
    completes.
- description: /api/metrics (R5) exposes internal worker-pool state via a public unauth'd
    endpoint (matching /api/health); without rate limiting an attacker can observe
    queue depth/auto-resume churn as a side-channel.
  severity: low
  mitigation: 'I5 documents in the router docstring that /api/metrics is intentionally
    unauth''d (parity with /api/health) and exposes ONLY non-PII numeric aggregates:
    queue_depth, active_tasks, auto_resume_total — no task IDs, titles, or per-task
    fields. If future operator deployment requires hardening, the existing Caddy basicauth
    surface can be re-applied with a config change (no code change).'
- description: I2 wraps worker.py in run_id context binding but worker.py also drives
    feature-decompose and harness-run paths (not just _run_task); a partial binding
    (e.g. only inside _run_task) leaves the harness-run and feature-decompose log
    records uncorrelated, violating R2's 'every log record emitted during a task run'
    criterion.
  severity: medium
  mitigation: 'I2 wraps all four worker execution-entry methods: _run_task, _run_feature_decompose,
    _execute_harness_run, and _resume_harness_run. The test asserts run_id is present
    in log records emitted from each path (parameterized fixture per entry point).
    The harness-run paths bind run_id=run_goal_id; I4 inherits the same binding inside
    HarnessExecutor.execute as a defense-in-depth layer.'
metrics:
  tool_calls: 9
  files_read: 6
  memory_hits: 3
  iterations_planned: 7
---

## Summary

G10 adds JSON-structured logging with `run_id`/`task_id` correlation, a `/api/metrics` endpoint, and a webhook notification on terminal/needs-human transitions — all backend-only, no new heavy deps. The design centers on a single new `logging_config.py` module (stdlib `logging.Formatter` subclass + `contextvars.ContextVar`) wired at the ROOT logger from `main.py`, with the three execution entry points (`worker._run_task` + sibling paths, `agent.run_agent`, `HarnessExecutor.execute`) each wrapping their bodies in a `bind_run_context()` context manager. The iteration DAG is wide: I1 is the only true root; I2/I3/I4/I5 run in layer 1 in parallel after I1 (I5 only depends on the FastAPI app already existing, not on logging, so it could even start sooner — kept depending only on `[]` to maximize parallelism); I6 (notifier) gates on I1+I2; I7 (docs) gates on I1+I5+I6. The chief tradeoff captured as a risk: choosing stdlib `logging`+`contextvars` over `structlog` saves a dependency but requires careful Token-based context reset to avoid leakage across asyncio tasks.

## Components

### Data
- None. G10 adds no schema, no DB tables, no migrations. All metrics are derived from in-memory worker state.

### Backend
- `backend/app/logging_config.py` (new): JsonFormatter (stdlib `logging.Formatter` subclass emitting JSON with keys timestamp/level/logger/message + any contextvars + extra fields); two `ContextVar`s (`_run_id_var`, `_task_id_var`); `bind_run_context(run_id, task_id=None)` context manager (token-based set/reset); `configure_logging()` reading `CRONOS_LOG_LEVEL` with INVALID→WARNING-log + INFO-fallback; wired from `main.py` at import time replacing the current `logging.basicConfig(...)` call.
- `backend/app/worker.py` (modify): import `bind_run_context`; wrap the bodies of `_run_task`, `_run_feature_decompose`, `_execute_harness_run`, `_resume_harness_run` with `with bind_run_context(run_id=<canonical>, task_id=task_id):`; pick the canonical run_id source (task_id for task runs, run_goal_id for harness runs).
- `backend/app/agent.py` (modify): wrap the body of `run_agent()` with `with bind_run_context(run_id=<from caller>, task_id=task.id):`; ensure `drain_stderr()` and the stdout-parsing loop and cancellation paths inherit the context (contextvars propagate via `asyncio.create_task` automatically since Python 3.7).
- `backend/app/harnesses/executor.py` (modify): wrap the body of `HarnessExecutor.execute()` with `with bind_run_context(run_id=run_goal_id):`; defense-in-depth (worker.py I2 also binds this for the harness paths).
- `backend/app/api/metrics.py` (new): FastAPI APIRouter with `GET /api/metrics` (no auth dependency, matching /api/health pattern); aggregates across `WorkerPool._workers.values()` returning `{queue_depth, active_tasks, auto_resume_total}` (sum of `_queue.qsize()`, count of in-flight tasks, sum of `_auto_resume_counts.values()`); 200 JSON response; depends on `WorkerPool` via FastAPI dependency injection (the existing app-state pattern).
- `backend/app/main.py` (modify): replace `logging.basicConfig(...)` with `configure_logging()` call from `logging_config`; register `metrics_router` alongside the other API routers.
- `backend/app/notifier.py` (new): `async def notify_state_change(task_id, task_title, status, exit_reason, summary)` reading `CRONOS_NOTIFY_URL` env var; silent no-op when unset/empty; uses existing `httpx>=0.27` async client with `timeout=5.0`; broad except → WARNING log; never raises.
- Worker finalize integration: in `worker._finalize` (line ~976) trigger `asyncio.create_task(notify_state_change(...))` when `new_state == TaskState.WAITING` OR when exit_reason is in {`ERROR`, `KILLED`, or `NO_CRONOS_STATUS` with non-zero exit}; in `_WorkerProtocolAdapter.finalize_child` (line ~142) trigger same on the WAITING branch.

### Frontend
None. `has_ui=false` from the analysis report; no frontend iterations or components.

## Implementation plan

| ID  | Type    | Depends on | Scope files (abridged)                                              | Validation                                                              |
|-----|---------|------------|---------------------------------------------------------------------|-------------------------------------------------------------------------|
| I1  | backend | -          | backend/app/logging_config.py, backend/app/main.py, tests           | cd backend && pytest tests/test_logging_config.py -v                    |
| I2  | backend | I1         | backend/app/worker.py, tests/test_worker_run_id_logging.py          | cd backend && pytest tests/test_worker_run_id_logging.py -v             |
| I3  | backend | I1         | backend/app/agent.py, tests/test_agent_run_id_logging.py            | cd backend && pytest tests/test_agent_run_id_logging.py -v              |
| I4  | backend | I1         | backend/app/harnesses/executor.py, tests/test_executor_run_id_logging.py | cd backend && pytest tests/test_executor_run_id_logging.py -v       |
| I5  | backend | -          | backend/app/api/metrics.py, backend/app/main.py, tests              | cd backend && pytest tests/test_metrics_endpoint.py -v                  |
| I6  | backend | I1, I2     | backend/app/notifier.py, backend/app/worker.py, 2 test files        | cd backend && pytest tests/test_notifier.py tests/test_worker_notifier_trigger.py -v |
| I7  | backend | I1, I5, I6 | README.md, backend/app/logging_config.py                            | python assertion that README contains CRONOS_LOG_LEVEL, CRONOS_NOTIFY_URL, /api/metrics, run_id |

DAG layering (Kahn): layer 0 = {I1, I5}; layer 1 = {I2, I3, I4}; layer 2 = {I6}; layer 3 = {I7}. I5 placed in layer 0 to maximize parallelism (it does not depend on logging — the metrics endpoint just reads worker state).

**Requirement → iteration coverage:**

| R# | Verifying phase | Covered by |
|----|-----------------|------------|
| R1 | test            | I1 (JsonFormatter on root logger, replacing basicConfig) |
| R2 | test            | I2 (bind_run_context in worker entry points) |
| R3 | test            | I3 (bind_run_context in run_agent + nested helpers) |
| R4 | test            | I4 (bind_run_context in HarnessExecutor.execute) |
| R5 | test            | I5 (GET /api/metrics endpoint) |
| R6 | test            | I6 (notifier.py + worker finalize trigger) |
| R7 | test            | I1 (CRONOS_LOG_LEVEL handling in configure_logging) |
| R8 | review          | I7 (README documentation update) |

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| JSON formatter wired only to 'cronos' logger misses `app.harnesses.executor` (__name__) records — violates R1 | high | I1 installs formatter on ROOT logger; test asserts module-named logger output is JSON |
| ContextVar leakage across asyncio tasks pollutes unrelated coroutines with stale run_id | medium | `bind_run_context` is a Token-based context manager with `finally: var.reset(token)`; tests verify post-scope cleanup |
| Synchronous webhook POST in finalize path blocks task-state transitions if URL hangs | medium | httpx AsyncClient with timeout=5.0 fired via `asyncio.create_task(...)` fire-and-forget; broad except → WARNING; hung-server test |
| /api/metrics unauth'd side-channel exposes operational state | low | Endpoint exposes only numeric aggregates (no PII/task IDs); parity with /api/health; Caddy basicauth can be re-applied as a config change |
| Partial run_id binding in worker.py — covering _run_task but not feature-decompose / harness paths | medium | I2 wraps all four execution-entry methods; parameterized test asserts run_id presence per entry point |

## Assumptions

- **stdlib `logging` + custom JsonFormatter chosen over `python-json-logger` and `structlog`** — avoids new dependency per memory constraint; a ~30-line `logging.Formatter` subclass emitting `json.dumps({...})` covers R1/R2/R3/R4 fully with no third-party code.
- **`httpx.AsyncClient` reused for the notifier** — `httpx>=0.27` is already a backend dep (confirmed via `pyproject.toml` line 13); no new HTTP dependency.
- **Canonical correlation field is `run_id`** — matches `run_goal_id` semantics already present in `executor.py` SSE events. For non-harness task runs the bound `run_id` equals the task_id; `task_id` is bound as a separate field per R3 so agent.py records have both.
- **Metrics endpoint reads `WorkerPool._workers` aggregating across spaces** — exposes a small read-only accessor on `WorkerPool` (e.g. `metrics_snapshot()`) so the router does not reach into private attrs directly; this is a minor I5-internal refactor and stays within I5 scope.
- **R8 (doc) requirement is covered by I7** rather than relying solely on the doc phase — the design budget includes a small docs iteration so README ships in the same goal cut. The doc phase will still run independently for `/CLAUDE.md` updates.
- **No new module under `backend/app/pipeline/`** — G10 is application observability, unrelated to the CC-v1 pipeline contract module of the same conceptual root.
- **Worker-state-change hook for notifier** placed inside `worker._finalize` (line ~976) and `_WorkerProtocolAdapter.finalize_child` (line ~142) — these are the two confirmed WAITING/terminal-error transition points (analyst Next-consumer-brief item #4 + scout findings).

## Open questions

- None. Analyst Open Questions section recorded "None"; design-phase decisions (formatter choice, contextvar mechanism, endpoint placement, notifier shape) all landed inside this design as Assumptions.

## Next consumer brief

Implementors read this YAML's `iterations[]` array; each iteration's `scope_files` is the hard diff boundary. Cross-iteration invariants not derivable from YAML:

1. **Canonical context-var name is `run_id`** (singular) and `task_id` — these are the literal JSON output keys. I1 defines the ContextVar; I2/I3/I4 MUST import and reuse `bind_run_context` from `app.logging_config` rather than introducing their own ContextVar instances.
2. **`bind_run_context` is the only public API for binding** — implementors MUST NOT call `_run_id_var.set(...)` directly. Use the context manager form so Token-based reset happens in `finally`.
3. **For the notifier (I6) the env var name is `CRONOS_NOTIFY_URL`** (not `CRONOS_WEBHOOK_URL`); the request body is exactly `{task_id, task_title, status, exit_reason, summary}` (analyst R6 acceptance criterion). The notifier MUST be fire-and-forget (`asyncio.create_task`) and MUST NOT block finalize_run.
4. **I5's `/api/metrics` route MUST use no auth dependency** (parity with /api/health); router registration in `main.py` should mirror the pattern of `health` not `tasks_router`. Implementor reads `backend/app/main.py` health route as the template.
5. **I7 (docs) MUST mention all four user-facing surfaces**: JSON field names (`timestamp`, `level`, `logger`, `message`, `run_id`, `task_id`), `/api/metrics` response schema, `CRONOS_NOTIFY_URL`, `CRONOS_LOG_LEVEL`. The validation_command performs a literal-string assertion so any missing token fails the gate.

Risks `risks[]` are the implementor's pre-flight checklist — especially the ContextVar leakage (medium) which determines whether I2/I3/I4 ship a correct context-manager wrapper or a leaky `.set()` call.
