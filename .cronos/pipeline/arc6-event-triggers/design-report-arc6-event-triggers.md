---
cc_version: '1.0'
agent: pipeline-architect
slug: arc6-event-triggers
phase: design
status: done
confidence: 0.85
inputs_used:
- memory:project_arc6_board_setup
- memory:project_arc6_64_run_lifecycle_review
- memory:project_pipeline_schemas
- .cronos/pipeline/arc6-event-triggers/analysis-report-arc6-event-triggers.md
- .cronos/pipeline/arc6-event-triggers/scout-report-arc6-event-triggers.md
- backend/app/harnesses/model.py
- backend/app/harnesses/validator.py
- backend/app/harnesses/run_trigger.py
- backend/app/api/harnesses.py
- backend/app/worker.py
- backend/app/main.py
outputs_produced:
- .cronos/pipeline/arc6-event-triggers/design-report-arc6-event-triggers.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - backend/app/harnesses/
  - backend/app/worker.py
  - backend/app/main.py
  - backend/app/api/harnesses.py
  excluded:
  - 'frontend/: has_ui=false; backend subsystem only'
  strategies:
  - memory_retrieval
  - read_targeted
iterations:
- id: I1
  type: backend
  scope_files:
  - backend/app/harnesses/triggers.py
  - backend/tests/harnesses/test_triggers_module.py
  validation_command: cd backend && pytest tests/harnesses/test_triggers_module.py
    -v
  max_diff_lines: 350
  depends_on: []
- id: I2
  type: backend
  scope_files:
  - backend/app/harnesses/validator.py
  - backend/app/harnesses/model.py
  - backend/tests/harnesses/test_validator_triggers.py
  validation_command: cd backend && pytest tests/harnesses/test_validator_triggers.py
    -v
  max_diff_lines: 300
  depends_on: []
- id: I3
  type: backend
  scope_files:
  - backend/app/worker.py
  - backend/tests/test_worker_event_callback.py
  validation_command: cd backend && pytest tests/test_worker_event_callback.py -v
  max_diff_lines: 250
  depends_on: []
- id: I4
  type: backend
  scope_files:
  - backend/app/api/harnesses.py
  - backend/tests/api/test_harnesses_webhook.py
  validation_command: cd backend && pytest tests/api/test_harnesses_webhook.py -v
  max_diff_lines: 350
  depends_on:
  - I1
  - I2
- id: I5
  type: backend
  scope_files:
  - backend/app/main.py
  - backend/tests/test_main_watch_file_change_trigger.py
  validation_command: cd backend && pytest tests/test_main_watch_file_change_trigger.py
    tests/test_worker_event_callback.py -v
  max_diff_lines: 350
  depends_on:
  - I1
  - I2
  - I3
- id: I6
  type: backend
  scope_files:
  - backend/tests/integration/test_event_triggers_e2e.py
  validation_command: cd backend && pytest tests/integration/test_event_triggers_e2e.py
    -v && pytest tests/ --cov=app --cov-fail-under=60
  max_diff_lines: 400
  depends_on:
  - I1
  - I2
  - I3
  - I4
  - I5
risks:
- description: Calling fan_out_to_harnesses() synchronously inside watch_spaces_dir()
    could block the watcher loop if HarnessStore enumeration becomes slow with many
    harnesses per space, dropping or delaying file events.
  severity: medium
  mitigation: In I5, dispatch fan_out_to_harnesses() via asyncio.create_task() so
    the watcher loop only enqueues — never awaits — harness-store reads; add an explicit
    comment marking the watcher hot path; cover with a test that asserts watch_spaces_dir()
    returns to its loop within 10ms of a matching file event even when fan-out is
    artificially slowed.
- description: Worker callback exception could propagate up and abort _finalize()
    after store.finalize_run() already persisted DONE — leaving downstream hooks (autopilot
    PR, merge task, propagate_to_parent) skipped.
  severity: high
  mitigation: In I3, wrap the on_task_state_change callback invocation in try/except
    inside _finalize() exactly like the existing autopilot_pr.run_post_done_flow block
    (lines 821-836); log.exception on failure and continue; add a regression test
    feeding a callback that raises RuntimeError and asserting autopilot_pr is still
    invoked.
- description: Plaintext Bearer tokens in harness YAML mean any space-storage read
    of a harness file leaks webhook auth credentials; an attacker with read access
    to .cronos/harnesses/ can replay webhooks.
  severity: medium
  mitigation: 'In I4, document the trade-off in the inline comment block (R7); add
    a log.warning emitted once-per-process if any harness YAML stores a webhook auth_token
    shorter than 16 characters (signals likely-weak token); flag a follow-up goal
    for secrets-API migration in ## Open questions.'
- description: 'Circular import risk: triggers.py needs HarnessStore (to enumerate
    subscribers) and is itself called from worker.py via callback; if implementor
    adds `from app.harnesses.store import HarnessStore` at module level in worker.py
    the R5 acceptance criterion (no app.harnesses import in worker.py) fails.'
  severity: medium
  mitigation: 'In I3, the worker accepts the callback as Callable[[str, str, str,
    str], Awaitable[None]] typed via TYPE_CHECKING only — no runtime import of app.harnesses
    anywhere in worker.py. In I5, the wiring closure in main.py constructs the callback
    as `async def cb(space_id, task_id, old, new): await fan_out_to_harnesses(EventBusEvent(...),
    harness_store=app.state.harness_store, ...)` and is passed to Worker via worker_pool.
    Validation: add a test that imports worker.py and asserts `''app.harnesses'' not
    in sys.modules` after fresh import (or grep the file for the literal string).'
- description: EventDebouncer in-memory state is per-process; if backend restarts
    mid-debounce window the next duplicate event will fire — producing two harness
    runs from one logical event.
  severity: low
  mitigation: Document the trade-off in triggers.py module docstring (I1); debounce
    windows default to 0.5s, so the window after restart is negligible; acceptance
    criterion R9 only requires same-process behavior; defer persistent dedup to a
    future arc if duplicate-after-restart becomes observable.
- description: watch_spaces_dir() currently reindexes every `.md` file unconditionally;
    adding harness-trigger matching in the same hot path may cause a regression in
    task reindex throughput on busy spaces.
  severity: low
  mitigation: 'In I5, perform the harness-trigger glob match AFTER the existing reindex
    path call (preserving current task throughput) and behind a fast early-exit (`if
    harness_store.count_triggers(space_id, kind=''file-change'') == 0: continue`);
    benchmark in I6''s e2e test by emitting 50 .md changes and asserting total elapsed
    under 2s.'
metrics:
  tool_calls: 9
  files_read: 8
  memory_hits: 3
  iterations_planned: 6
---

## Summary

This design adds three event Trigger kinds to the harnesses subsystem behind a shared `EventBusEvent`/`EventDebouncer`/`fan_out_to_harnesses()` core at `backend/app/harnesses/triggers.py`. The DAG splits into three independent leaves — the triggers module (I1), the validator/model extension (I2), and the worker callback hook (I3) — which converge into the webhook endpoint (I4) and the file-change watcher extension (I5), and finally an end-to-end integration test (I6). Worker stays decoupled from `app.harnesses` via a typed callback wired in `main.py`; the existing `watch_spaces_dir()` is extended in place (no second `awatch()`); the existing `enqueue_harness_run()` remains the sole run-creation interface. Plaintext Bearer tokens in harness YAML are an accepted trade-off documented inline (R7).

## Components

### Data
- `EventBusEvent` (Pydantic v2 BaseModel in `backend/app/harnesses/triggers.py`): immutable event with `event_id`, `kind` Literal[`task-state-change`,`webhook`,`file-change`], `space_id`, `payload: dict`, `timestamp: str` (ISO-8601 UTC).
- HarnessNode `data` schema additions documented in `model.py` docstring: `webhook` requires `webhook_path` + `auth_token`; `file-change` requires `watch_pattern`, defaults `debounce_seconds` to 0.5; `task-state-change` defaults `watched_state` to `DONE`.

### Backend
- `EventDebouncer` (class in `triggers.py`): in-memory `dict[str, float]` keyed by event_id; `should_fire(event_id, debounce_seconds) -> bool` uses `time.monotonic()` with lazy expiry sweep.
- `fan_out_to_harnesses(event, *, harness_store, task_store, worker_pool, space_dir) -> list[str]`: enumerates harnesses with a trigger node whose `data.kind == event.kind`, applies per-harness dedup on `event_id`, calls `enqueue_harness_run()` per match, returns the list of created `run_ids`.
- `validator.py::validate_graph` extended with `_validate_trigger_nodes(harness)` enforcing per-kind `data` requirements and applying defaults via a pure helper (no in-place mutation of caller's dict).
- `worker.py::Worker.__init__` gains optional kw-only `on_task_state_change: Callable[[str, str, str, str], Awaitable[None]] | None = None`; invoked from `_finalize()` after `store.finalize_run()` and before the autopilot_pr block, inside try/except. Worker has zero runtime import of `app.harnesses`.
- `api/harnesses.py` new endpoint `POST /api/spaces/{space_id}/harnesses/{name}/webhook`: extracts Bearer token from Authorization header, looks up the harness, locates its single webhook trigger node, compares `data.auth_token`, builds an `EventBusEvent(kind='webhook', payload=body, ...)`, calls `fan_out_to_harnesses()`, returns HTTP 202 with `{run_ids: [...]}`. 401 on missing/wrong token; 404 when no webhook trigger node exists.
- `main.py::watch_spaces_dir()` extended in place: after existing reindex paths, for each changed file in a Cronos space, build an `EventBusEvent(kind='file-change', payload={path, ...})` and call `fan_out_to_harnesses()`; pattern-matching uses `pathlib.PurePath.match()` on the trigger node's `data.watch_pattern` relative to `space_dir`; per-(space, pattern, path) dedup via `EventDebouncer` with `data.debounce_seconds` (default 0.5).
- `main.py::lifespan` wires the worker callback: when starting each `Worker` via `WorkerPool`, inject a closure that calls `fan_out_to_harnesses()` with the live `harness_store`, `task_store`, and `worker_pool` references.

### Frontend
<!-- Omitted: has_ui=false per analysis report. -->

## Implementation plan

| ID  | Type    | Depends on    | Scope files (abridged)                                                        | Validation                                                                                       |
|-----|---------|---------------|-------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------|
| I1  | backend | -             | backend/app/harnesses/triggers.py, backend/tests/harnesses/test_triggers_module.py | cd backend && pytest tests/harnesses/test_triggers_module.py -v                                  |
| I2  | backend | -             | backend/app/harnesses/validator.py, backend/app/harnesses/model.py, tests/harnesses/test_validator_triggers.py | cd backend && pytest tests/harnesses/test_validator_triggers.py -v                              |
| I3  | backend | -             | backend/app/worker.py, backend/tests/test_worker_event_callback.py            | cd backend && pytest tests/test_worker_event_callback.py -v                                      |
| I4  | backend | I1, I2        | backend/app/api/harnesses.py, backend/tests/api/test_harnesses_webhook.py      | cd backend && pytest tests/api/test_harnesses_webhook.py -v                                      |
| I5  | backend | I1, I2, I3    | backend/app/main.py, backend/tests/test_main_watch_file_change_trigger.py     | cd backend && pytest tests/test_main_watch_file_change_trigger.py tests/test_worker_event_callback.py -v |
| I6  | backend | I1, I2, I3, I4, I5 | backend/tests/integration/test_event_triggers_e2e.py                     | cd backend && pytest tests/integration/test_event_triggers_e2e.py -v && pytest tests/ --cov=app --cov-fail-under=60 |

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Watcher loop blocking on fan-out / harness-store enumeration on file events | medium | I5 dispatches fan-out via `asyncio.create_task()`; watcher never awaits store reads; test asserts watcher returns within 10ms even when fan-out is slowed |
| Callback exception in _finalize() skipping downstream hooks (autopilot_pr, merge task, propagate_to_parent) | high | I3 wraps callback in try/except mirroring autopilot_pr block; regression test feeds raising callback and asserts autopilot_pr still runs |
| Plaintext Bearer tokens in harness YAML leak via filesystem reads / backups | medium | I4 documents trade-off (R7); log.warning once-per-process when token <16 chars; secrets-API migration flagged as follow-up |
| Circular import risk between worker.py and app.harnesses if implementor adds an import to worker.py | medium | I3 uses Callable typed via TYPE_CHECKING only; I5 builds the closure in main.py; verification test asserts `'app.harnesses' not in worker.py` imports |
| EventDebouncer in-memory state lost on restart → duplicate events fire | low | Documented in triggers.py docstring (I1); sub-second windows make post-restart duplicate window negligible; defer persistent dedup |
| Reindex regression from harness-trigger matching in watcher hot path | low | I5 fast early-exit when no file-change triggers in space; benchmark in I6 (50 .md changes < 2s) |

## Assumptions

- `fan_out_to_harnesses()` is an `async` coroutine awaiting `enqueue_harness_run()` directly when called from `_finalize()` (already async) and the webhook endpoint (already async). In `watch_spaces_dir()` it is dispatched via `asyncio.create_task()` so the watcher loop is never blocked on harness-store enumeration (open question 1 from analysis).
- Webhook routing uses the per-harness URL form `/api/spaces/{space_id}/harnesses/{name}/webhook` (analysis open question 2) — chosen for route locality with existing `/{name}/run` and to avoid a full harness scan on every webhook request. The `data.webhook_path` field is retained as a node-level identifier for future flat-routing migration but is not used in URL dispatch in this iteration.
- The webhook auth_token comparison uses constant-time `secrets.compare_digest()` to avoid timing side-channels even though tokens are plaintext.
- HarnessStore.list_all(space_id) or equivalent enumeration is fast enough for ≤10 harnesses per space (scout finding); no caching layer is added.
- `pathlib.PurePath.match()` is sufficient for the `data.watch_pattern` glob (e.g. `.cronos/tasks/*.md`); recursive `**` patterns are supported via PurePath semantics. Negation patterns (`!.cronos/tmp/**`) are deferred per analysis scope.
- The Worker callback signature `(space_id, task_id, old_state, new_state)` passes state values as strings (TaskState.value), not enum members, so worker.py needs no harness-side enum awareness.
- Event_id construction: `f"{kind}:{space_id}:{stable_key}"` where stable_key is `task_id` for task-state-change, `webhook_path` + content-hash for webhook (so dedup applies per identical body), and `watch_pattern` + `file_path` for file-change.

## Open questions

- Follow-up goal recommendation: migrate plaintext webhook auth_tokens to a space-scoped secrets API (deferred per analysis, called out in risk register).

## Next consumer brief

Implementors should read these YAML fields first: `iterations[]` (each entry is a complete unit of work), `iterations[].scope_files` (hard diff boundary — do not touch any other file), `iterations[].validation_command` (the tester will run this verbatim), and `risks[]` (each risk has a concrete mitigation pinned to a specific iteration). Two cross-iteration invariants are not derivable from the YAML and must be honoured:

1. The `EventBusEvent.kind` literal values are `"task-state-change"`, `"webhook"`, `"file-change"` — exact strings, hyphenated, lowercase. I1 defines them; I2, I3, I4, I5 must use these literals verbatim (no `task_state_change` underscore variant, no `TaskStateChange` camelCase).
2. The webhook endpoint URL is `POST /api/spaces/{space_id}/harnesses/{name}/webhook` — I4 implements it, I6's e2e test calls it; the literal segment `/webhook` is shared.

Unresolved before starting: none — open questions in the analysis report have been resolved in `## Assumptions` (async dispatch via create_task in watcher; per-harness URL routing for webhook).
