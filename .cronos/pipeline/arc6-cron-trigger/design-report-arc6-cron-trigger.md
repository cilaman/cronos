---
cc_version: '1.0'
agent: pipeline-architect
slug: arc6-cron-trigger
phase: design
status: done
confidence: 0.86
inputs_used:
- memory:project_architecture_key_modules
- memory:project_arc6_board_setup
- memory:project_pipeline_architect_agent
- .cronos/pipeline/arc6-cron-trigger/analysis-report-arc6-cron-trigger.md
- .cronos/pipeline/arc6-cron-trigger/scout-report-arc6-cron-trigger.md
- backend/app/main.py
- backend/app/api/harnesses.py
- backend/pyproject.toml
outputs_produced:
- .cronos/pipeline/arc6-cron-trigger/design-report-arc6-cron-trigger.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - backend/app/main.py (lifespan startup/shutdown block, lines 280-365)
  - backend/app/api/harnesses.py (trigger_harness_run, lines 254-322)
  - backend/app/harnesses/ (directory listing — model, store, run_index, executor
    present)
  - backend/pyproject.toml (dependencies section)
  excluded:
  - 'frontend/: has_ui=false in analysis; pure backend feature'
  - 'backend/app/harnesses/validator.py: schema validation deferred per analysis assumptions'
  - 'backend/app/worker.py: enqueue path consumed via shared helper, not extended'
  strategies:
  - memory_retrieval
  - read_targeted
iterations:
- id: I1
  type: data
  scope_files:
  - backend/pyproject.toml
  - backend/app/harnesses/model.py
  validation_command: cd backend && pip install -e . && python -c 'import croniter,
    dateutil.tz; print(croniter.__name__, dateutil.tz.__name__)'
  max_diff_lines: 80
  depends_on: []
- id: I2
  type: backend
  scope_files:
  - backend/app/harnesses/run_trigger.py
  - backend/app/api/harnesses.py
  - backend/tests/test_harness_run_trigger.py
  validation_command: cd backend && pytest tests/test_harness_run_trigger.py tests/test_harnesses_api.py
    -v
  max_diff_lines: 350
  depends_on:
  - I1
- id: I3
  type: backend
  scope_files:
  - backend/app/harnesses/cron.py
  validation_command: cd backend && pytest tests/test_cron_eval.py -v
  max_diff_lines: 400
  depends_on:
  - I1
- id: I4
  type: backend
  scope_files:
  - backend/app/main.py
  validation_command: cd backend && pytest tests/test_main_lifespan.py -v -k 'cron
    or lifespan'
  max_diff_lines: 120
  depends_on:
  - I2
  - I3
- id: I5
  type: backend
  scope_files:
  - backend/tests/test_cron_loop.py
  - backend/tests/test_cron_eval.py
  validation_command: cd backend && pytest tests/test_cron_loop.py tests/test_cron_eval.py
    -v --timeout=30
  max_diff_lines: 500
  depends_on:
  - I3
  - I4
risks:
- description: Linear scan of run_index per harness per tick (one disk read per harness)
    becomes O(harnesses * runs) at scale; with the default 60s poll interval, a single
    space with hundreds of harnesses could miss its tick budget.
  severity: medium
  mitigation: Document the per-tick cost in cron.py module docstring; cap the per-tick
    wall-clock budget by reading indices concurrently with asyncio.gather() bounded
    by a semaphore (default 16). Add a debug log line with tick duration so regressions
    are visible. Defer in-memory active-run cache to a follow-up if/when telemetry
    shows the bottleneck.
- description: croniter without a stored last-fire timestamp can fire twice within
    the same minute if the poll interval is < 60s and tests reuse a short interval
    — the loop must dedupe within the current cron minute, not the current tick.
  severity: high
  mitigation: In cron.py, define should_fire(expr, tz, now, prev_tick) = (croniter(expr,
    base_time=prev_tick).get_next(datetime) <= now); never fire twice for the same
    (harness, node) within a single cron-minute. Track only prev_tick (one timestamp
    per loop, not per harness) and pass it on each iteration. Cover with a dedicated
    unit test in test_cron_eval.py (R7).
- description: Extracting enqueue_harness_run() from api/harnesses.py risks breaking
    the existing manual-trigger endpoint contract (HTTP 202 body, run_id, worker.register_run
    timing).
  severity: medium
  mitigation: 'I2 keeps the public endpoint surface byte-identical: the route still
    returns {run_id, harness_id, triggered_at} with status 202. Existing tests/test_harnesses_api.py
    must remain green (listed in I2 validation_command); the shared helper accepts
    task_store/harness_store/worker_pool as args so it is callable from both the HTTP
    handler and cron.py without circular imports.'
- description: Malformed cron expression or unknown IANA timezone in trigger.data
    could crash the loop and take all sibling background tasks down — main.py's lifespan
    does not isolate task failures.
  severity: medium
  mitigation: cron_loop wraps each tick in try/except Exception and each per-harness/per-node
    evaluation in an inner try/except; both log via log.exception and continue. R3
    AC explicitly requires log-and-skip on malformed expressions; R5 AC requires log-and-fallback-to-UTC
    on unknown timezones. Both paths covered by tests in test_cron_eval.py (I5).
- description: Test for 'fires at scheduled time' (R7) using real wall-clock would
    breach the <10s budget; tests must mock the clock or use a sub-second interval,
    which can race with asyncio scheduling jitter on CI.
  severity: low
  mitigation: 'I5 tests parameterize cron.py''s now-source (inject a callable now:
    Callable[[], datetime] defaulting to datetime.now(UTC)); R7 test feeds a controlled
    clock that advances past the scheduled minute, sets interval_seconds=0.05, and
    asserts a run appears in read_index() within a 5s asyncio.wait_for. No reliance
    on real wall-clock cron timing.'
metrics:
  tool_calls: 7
  files_read: 5
  memory_hits: 3
  iterations_planned: 5
---

## Summary

Add a stateless `cron_loop` background task to `main.py`'s `lifespan`, mirroring the watcher/archiver/memory_pruner pattern. The loop lives in a new `backend/app/harnesses/cron.py`, re-reads the canonical harness list each tick via `HarnessStore`, evaluates each `trigger` node's `data['expression']` (croniter + dateutil.tz, UTC fallback), skips firings when the harness already has a `status='running'` run, and enqueues new runs through a `run_trigger.enqueue_harness_run()` helper extracted from the existing HTTP trigger endpoint. The five-iteration DAG is wide: I2 (helper extraction) and I3 (cron module) run in parallel after I1 (deps + docstring), then I4 (lifespan wiring) and I5 (tests) close it out. The key non-obvious tradeoff captured in the risk register is the deduplication-without-timestamp problem (high-severity R-risk-2): the loop must remember `prev_tick` (one timestamp, not per-harness) so croniter's `get_next(prev_tick)` semantics prevent double-fires inside the same cron minute when the poll interval is sub-minute.

## Components

### Data
- `backend/pyproject.toml` runtime deps: `croniter` (MIT) and `python-dateutil` (BSD) added — covers R5.
- `backend/app/harnesses/model.py` module docstring: documents the `trigger` node `data` shape (`expression` required, `timezone` optional IANA name, UTC default) — covers the documentation half of R3.

### Backend
- `backend/app/harnesses/run_trigger.py` (new): `async def enqueue_harness_run(task_store, harness_store, worker_pool, space_id, space_dir, harness_name, *, brief, triggered_at) -> RunSummary` — the shared task-create + run-index-append + worker-register + worker-enqueue helper, lifted verbatim from `api/harnesses.py:255-322`.
- `backend/app/api/harnesses.py` `trigger_harness_run`: refactored to delegate to `run_trigger.enqueue_harness_run`; HTTP response body and status code preserved byte-identical.
- `backend/app/harnesses/cron.py` (new): exports `async def cron_loop(harness_store, space_store, spaces_dir, interval_seconds, stop_event, *, task_store, worker_pool, now: Callable[[], datetime] = ...) -> None` plus internal `should_fire(expression, timezone_name, prev_tick, now) -> bool` and `has_active_run(space_dir, harness_name) -> bool` helpers. The module docstring explicitly states "No back-fill of missed ticks across restart — only the current time is evaluated each tick" (R6 documentation requirement).
- `backend/app/main.py` lifespan: adds `cron = asyncio.create_task(cron_loop(...), name="cron")` alongside the five existing background tasks; adds `CRONOS_CRON_INTERVAL_SECONDS` env var (default 60); includes `cron` in the shutdown-await tuple at line 360.

<!-- Frontend section omitted — has_ui=false in analysis. -->

## Implementation plan

| ID | Type    | Depends on | Scope files (abridged)                                                | Validation                                                                              |
|----|---------|------------|-----------------------------------------------------------------------|-----------------------------------------------------------------------------------------|
| I1 | data    | -          | pyproject.toml, harnesses/model.py                                    | pip install -e . && python -c 'import croniter, dateutil.tz'                            |
| I2 | backend | I1         | harnesses/run_trigger.py, api/harnesses.py, tests/test_harness_run_trigger.py | pytest tests/test_harness_run_trigger.py tests/test_harnesses_api.py -v          |
| I3 | backend | I1         | harnesses/cron.py                                                     | pytest tests/test_cron_eval.py -v                                                       |
| I4 | backend | I2, I3     | main.py                                                               | pytest tests/test_main_lifespan.py -v -k 'cron or lifespan'                             |
| I5 | backend | I3, I4     | tests/test_cron_loop.py, tests/test_cron_eval.py                      | pytest tests/test_cron_loop.py tests/test_cron_eval.py -v --timeout=30                  |

Requirement-to-iteration coverage cross-check:
- R1 (lifespan registration + graceful shutdown) → I4; verified by I5 (test_cron_loop.py).
- R2 (re-read harness list each tick; no per-harness state) → I3 (cron.py design); verified by I5.
- R3 (trigger.data schema: expression + timezone) → I1 (docstring) + I3 (runtime parse); verified by I5.
- R4 (overlap guard via run_index) → I3 (has_active_run helper); verified by I5 (R8 test).
- R5 (croniter + python-dateutil deps + UTC fallback) → I1 (deps) + I3 (fallback); verified by I1 validation + I5.
- R6 (no back-fill; documented in code) → I3 module docstring; verified by review (analysis assigns R6 to review phase).
- R7 (test: cron fires at scheduled time) → I5 (test_cron_loop.py).
- R8 (test: tick during active run is skipped) → I5 (test_cron_loop.py).

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Linear run_index disk scan per harness per tick scales poorly | medium | Document cost in cron.py docstring; bound concurrency with a semaphore (16); log tick duration; defer in-memory cache to follow-up |
| Sub-minute poll interval (tests) can fire same cron-minute twice without a prev_tick anchor | high | Use `croniter(expr, base_time=prev_tick).get_next() <= now` semantics; track single `prev_tick` timestamp loop-wide; cover with dedicated unit test |
| Extracting enqueue_harness_run() risks breaking the HTTP /run endpoint contract | medium | I2 preserves response body + status 202; existing tests/test_harnesses_api.py must stay green (in I2 validation_command); helper takes stores as args to avoid circular imports |
| Malformed cron expr or unknown IANA tz could crash the loop and take sibling tasks down | medium | Per-tick try/except in cron_loop; inner try/except per-harness/per-node; log-and-skip on malformed expr; log-and-fallback-to-UTC on unknown tz; both covered in test_cron_eval.py |
| R7 "fires at scheduled time" test could exceed 10s budget or race asyncio jitter on CI | low | Inject `now: Callable[[], datetime]` into cron_loop; tests feed a controlled clock; interval_seconds=0.05; asyncio.wait_for with 5s budget; no real wall-clock dependency |

## Assumptions

- `has_ui=false` carries over from the analysis report — no frontend iterations are planned. If a future request adds a "next-fire-time" UI, that is a separate design cycle.
- `enqueue_harness_run()` lives in `backend/app/harnesses/run_trigger.py` (new module) rather than inside `cron.py` to avoid a cron-on-the-import-graph dependency from `api/harnesses.py`; the HTTP handler imports the helper module, not the cron loop.
- The cron loop's `now` source is injected as a `Callable[[], datetime]` parameter defaulting to `lambda: datetime.now(UTC)`, enabling deterministic tests without monkey-patching croniter or `datetime`.
- `prev_tick` is loop-local state (a single `datetime`), not per-harness state — this stays consistent with R2's "no per-harness state" requirement because prev_tick is a property of the loop, not of any individual trigger.
- `CRONOS_CRON_INTERVAL_SECONDS` defaults to 60. Tests pass `interval_seconds` directly to `cron_loop()`, bypassing the env var; no test reads the env var.
- Trigger node `data` schema validation is intentionally limited to a docstring + runtime log-and-skip on malformed expression (per analysis "Deferred" list and F2). Formal `validator.py` rules are out of scope for this cycle.
- The implementor will choose between `croniter` and `croniter-range`/`apscheduler` — analysis pins `croniter`, so I3 uses it directly. No further library evaluation is in scope.

## Open questions

- None. The analysis report's `## Open questions` is "None" and the request text, scout findings, and inspected code paths are sufficient to fully decompose the work.

## Next consumer brief

Implementors should read YAML fields `iterations[]`, `iterations[].scope_files`, `iterations[].validation_command`, and `risks[]` directly — those are the machine-readable contract. Two cross-iteration invariants are not derivable from the YAML alone and must be honored:

1. **Function signature contract for `enqueue_harness_run`** (I2 → I3, I4): the helper signature `async def enqueue_harness_run(task_store, harness_store, worker_pool, space_id, space_dir, harness_name, *, brief, triggered_at) -> RunSummary` is fixed; I3's `cron_loop` and the refactored I2 HTTP handler must both call it with this exact shape. Diverging signatures will break I4 wiring silently.
2. **`prev_tick` deduplication** (risks #2): I3 must implement `should_fire(expression, tz_name, prev_tick, now)` such that no `(harness_name, node_id)` pair fires twice within the same cron-minute even if the poll interval is sub-minute. I5's test_cron_eval.py must include a dedicated test asserting this — without it, R7's shortened-interval test will produce false greens.

No unresolved open questions for implementors. If during I3 the implementor discovers that `HarnessStore.list(space_dir)` is not safe to call from a background task without holding the store's lock, raise a blocker rather than improvising — the lock semantics in `harnesses/store.py` are load-bearing.
