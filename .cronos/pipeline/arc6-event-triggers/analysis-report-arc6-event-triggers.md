---
cc_version: '1.0'
agent: pipeline-analyst
slug: arc6-event-triggers
phase: analysis
status: done
confidence: 0.9
inputs_used:
- memory:project_arc6_board_setup
- memory:project_arc6_64_run_lifecycle_review
- .cronos/pipeline/arc6-event-triggers/scout-report-arc6-event-triggers.md
- backend/app/pipeline/CONTRACT.md
- backend/app/pipeline/verify.py
- backend/app/pipeline/schemas/analysis.schema.yaml
- backend/app/harnesses/model.py
- backend/app/harnesses/run_trigger.py
outputs_produced:
- .cronos/pipeline/arc6-event-triggers/analysis-report-arc6-event-triggers.md
blockers: []
next_consumer: design
request: "Add the three event Trigger kinds (`backend/app/harnesses/triggers.py`).\n\
  \n- **task-state-change:** emit from the worker finalise/transition path without\
  \ coupling\n  the worker to harnesses (publish an event the harness subsystem subscribes\
  \ to).\n- **webhook:** an external route mapping a payload to a run (document the\
  \ auth scheme --\n  Caddy `_auth` may not apply).\n- **file-change:** coexist with\
  \ `watch_spaces_dir` (main.py:90); reuse its events, don't\n  double-watch.\n- De-dup/debounce;\
  \ fan out when multiple harnesses subscribe to one event.\n\nAcceptance: moving\
  \ a task to DONE fires a subscribed harness; a webhook POST starts its\nrun; a watched\
  \ file change triggers its harness; duplicates within the debounce window\nfire\
  \ once."
has_ui: false
coverage_summary:
  searched:
  - backend/app/harnesses/
  - backend/app/worker.py
  - backend/app/main.py
  - backend/app/api/harnesses.py
  excluded:
  - 'frontend/: all three trigger kinds are backend subsystem concerns with no new
    UI needed'
  strategies:
  - memory_retrieval
  - read_targeted
traceability:
- requirement_id: R1
  statement: A new module backend/app/harnesses/triggers.py exists defining EventBusEvent
    (kind, space_id, payload, timestamp, event_id), EventDebouncer (in-memory expiry
    tracker), and fan_out_to_harnesses() (enqueue matching harness runs).
  acceptance_criteria:
  - Given the module is imported, when inspected, then EventBusEvent, EventDebouncer,
    and fan_out_to_harnesses are all importable from app.harnesses.triggers.
  - EventBusEvent.kind accepts exactly the values task-state-change, webhook, and
    file-change.
  - EventBusEvent contains event_id (str), space_id (str), payload (dict), and timestamp
    (ISO-8601 UTC str).
  verifying_phase: test
  confidence: 0.95
- requirement_id: R2
  statement: EventDebouncer.should_fire(event_id, debounce_seconds) returns True the
    first time an event_id is seen, False for duplicates within the window, and True
    again after the window expires.
  acceptance_criteria:
  - Given a fresh EventDebouncer, when should_fire('e1', 0.5) is called, then it returns
    True.
  - When should_fire('e1', 0.5) is called a second time within 0.5 seconds, then it
    returns False.
  - When should_fire('e1', 0.5) is called after 0.5 seconds have elapsed, then it
    returns True again.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R3
  statement: fan_out_to_harnesses() enqueues exactly one harness run per harness with
    a matching trigger node kind, and returns the list of created run_ids.
  acceptance_criteria:
  - Given two harnesses each with a trigger node of kind task-state-change, when a
    task-state-change event is fanned out, then two run_ids are returned (one per
    harness).
  - Given a harness with a trigger node of kind file-change only, when a task-state-change
    event is fanned out, then zero run_ids are returned.
  - Each enqueued run is created via enqueue_harness_run() with a brief containing
    the event payload serialized as JSON.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R4
  statement: 'The harness node validator is extended so that trigger nodes validate
    three new kind values: webhook requires data.webhook_path and data.auth_token;
    file-change requires data.watch_pattern and defaults data.debounce_seconds to
    0.5; task-state-change defaults data.watched_state to DONE.'
  acceptance_criteria:
  - 'Given a trigger node data={kind: webhook, webhook_path: /hook, auth_token: secret},
    when persisted via the harness store, then validation passes without error.'
  - 'Given a trigger node data={kind: webhook} with no webhook_path or auth_token,
    when persisted, then a ValidationError is raised identifying both missing fields.'
  - 'Given a trigger node data={kind: file-change, watch_pattern: .cronos/tasks/*.md},
    when persisted, then validation passes and debounce_seconds defaults to 0.5.'
  - 'Given a trigger node data={kind: task-state-change}, when persisted, then validation
    passes and watched_state defaults to DONE.'
  verifying_phase: test
  confidence: 0.9
- requirement_id: R5
  statement: After worker._finalize() successfully transitions a task to TaskState.DONE,
    a task-state-change event is emitted via an injected callback without any direct
    import of app.harnesses in worker.py.
  acceptance_criteria:
  - Given a Worker instantiated with an on_task_state_change callback, when a task
    transitions to DONE via _finalize(), then the callback is called with (space_id,
    task_id, old_state, new_state).
  - Given no callback is registered, when a task transitions to DONE, then _finalize()
    completes without error.
  - The import graph of worker.py does NOT contain any direct import from app.harnesses.
  - Given the callback raises an exception, then _finalize() catches it, logs a warning,
    and does not propagate the exception.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R6
  statement: A new endpoint POST /api/spaces/{space_id}/harnesses/{name}/webhook accepts
    a JSON body, validates a Bearer token against the trigger node data.auth_token,
    and enqueues a harness run returning HTTP 202.
  acceptance_criteria:
  - 'Given a harness with a webhook trigger node data.auth_token=tok123, when POST
    /webhook is called with Authorization: Bearer tok123 and a JSON body, then HTTP
    202 is returned and a run is created.'
  - When POST /webhook is called with a wrong token, then HTTP 401 is returned and
    no run is created.
  - When POST /webhook is called with no Authorization header, then HTTP 401 is returned.
  - When the harness has no trigger node of kind webhook, then HTTP 404 is returned
    with a message indicating no webhook trigger is configured.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R7
  statement: The webhook endpoint in backend/app/api/harnesses.py contains an inline
    comment block documenting that Caddy HTTP Basic Auth does not apply to webhook
    callers and that per-harness Bearer tokens stored in plaintext YAML are the auth
    layer.
  acceptance_criteria:
  - The file backend/app/api/harnesses.py contains a comment block at the webhook
    endpoint explaining the Bearer token auth scheme.
  - The comment notes the Caddy Basic Auth limitation and the plaintext-token trade-off.
  verifying_phase: review
  confidence: 0.85
- requirement_id: R8
  statement: watch_spaces_dir() in main.py is extended to match each file-change event
    against harness trigger nodes with data.kind=file-change; when a match is found,
    fan_out_to_harnesses() is called; no second watchfiles.awatch() call is added.
  acceptance_criteria:
  - 'Given a harness in space S with a trigger node data={kind: file-change, watch_pattern:
    .cronos/tasks/*.md}, when a matching file is modified, then the harness is enqueued
    exactly once.'
  - Given the existing tools-manifest SHA-throttle logic, when a file-change event
    fires, then the existing SHA-throttle behavior is unchanged.
  - The implementation does NOT call watchfiles.awatch() a second time for harness
    file triggers.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R9
  statement: File-change events are debounced per (space_id, watch_pattern, file_path)
    using EventDebouncer with the trigger node data.debounce_seconds (default 0.5s);
    duplicate events within the window are dropped.
  acceptance_criteria:
  - Given a file-change trigger with debounce_seconds=0.5, when the same file is modified
    twice within 0.5 seconds, then fan_out_to_harnesses() is called exactly once.
  - Given the same trigger, when the file is modified again after 0.5 seconds, then
    fan_out_to_harnesses() is called a second time.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R10
  statement: Fan-out enqueues one run per matching harness per event; de-duplication
    applies within a single harness but not across distinct harnesses.
  acceptance_criteria:
  - Given harness A and harness B both with file-change trigger nodes matching *.md,
    when a .md file changes, then harness A gets one run and harness B gets one run
    (total 2 runs).
  - Given a single harness receives the same event_id twice in rapid succession, then
    only one run is enqueued for that harness.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R11
  statement: 'End-to-end: moving a task to DONE fires a subscribed harness; a webhook
    POST starts a run; a watched file change triggers a harness; duplicates within
    the debounce window fire exactly once.'
  acceptance_criteria:
  - Given a harness with a task-state-change trigger in space S, when a task in S
    transitions to DONE, then the harness has an active or done run within 2 seconds.
  - Given a harness with a webhook trigger and token T, when POST /webhook with Bearer
    T is called, then a run is created.
  - Given a harness with a file-change trigger for .cronos/tasks/*.md, when a task
    file is written, then a run is created.
  - Given the same file is written twice within the debounce window, then exactly
    one run (not two) is created.
  verifying_phase: manual
  confidence: 0.8
metrics:
  tool_calls: 9
  files_read: 6
  memory_hits: 2
---

## Summary

This feature adds three event-driven trigger kinds to the harnesses subsystem -- `task-state-change`, `webhook`, and `file-change` -- backed by a shared `EventBusEvent` / `EventDebouncer` / `fan_out_to_harnesses()` module at `backend/app/harnesses/triggers.py`. The worker `_finalize()` path emits task-state-change events via an injected callback (no direct harness import), `watch_spaces_dir()` in `main.py` is extended in-place to match file events against harness trigger nodes, and a new `POST /{name}/webhook` endpoint handles externally-originating runs with per-harness Bearer token auth. All three paths converge on the same debounce + fan-out core, and the existing `enqueue_harness_run()` helper is reused as the sole run-creation interface.

## Scope

### In scope
- New module `backend/app/harnesses/triggers.py` with `EventBusEvent`, `EventDebouncer`, `fan_out_to_harnesses()`
- Extension of `backend/app/harnesses/validator.py` to validate the three new trigger node data schemas (webhook, task-state-change, file-change)
- Extension of `backend/app/harnesses/model.py` docstring to document the three new trigger node `data` conventions
- Injection of an `on_task_state_change` callback into `backend/app/worker.py` Worker `__init__` (no direct harness import added to worker.py)
- Wiring of the callback in `backend/app/main.py` (where both Worker and HarnessStore are already instantiated)
- New API endpoint `POST /api/spaces/{space_id}/harnesses/{name}/webhook` in `backend/app/api/harnesses.py`
- Extension of `watch_spaces_dir()` in `backend/app/main.py` to match file events against harness trigger nodes and call `fan_out_to_harnesses()`
- Inline documentation of the webhook auth scheme in `backend/app/api/harnesses.py`

### Out of scope
- Frontend UI for configuring trigger nodes (trigger node configuration is done in harness YAML; no visual editor for trigger properties required)
- Persistent event queue or message broker (in-memory debounce only)
- Harness-level secrets management (auth tokens stored in plaintext YAML; secrets API deferred)
- SSE / streaming changes for trigger events (runs are enqueued; no new SSE events)
- Webhook path routing at the Caddy layer (no Caddy config changes)

### Deferred
- Negation patterns for file-change watch_pattern (e.g., `!.cronos/tmp/**`)
- Configurable per-harness payload validation schema for webhook payloads
- Condition predicates on task-state-change triggers (e.g., fire only if task title matches a pattern)
- Task-state-change trigger for states other than DONE (WAITING, ACTIVE)
- Migration of plaintext auth tokens to a space-scoped secrets API

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | New triggers.py module defines EventBusEvent, EventDebouncer, and fan_out_to_harnesses() |
| R2 | EventDebouncer.should_fire() correctly gates duplicate events within and outside the window |
| R3 | fan_out_to_harnesses() enqueues one run per matching harness and returns run_ids |
| R4 | Harness node validator extended for webhook, task-state-change, and file-change trigger data schemas |
| R5 | Worker emits task-state-change events via injected callback without direct harness import |
| R6 | New POST /{name}/webhook endpoint validates Bearer token and enqueues run |
| R7 | Webhook auth scheme documented in api/harnesses.py (Caddy limitation + plaintext trade-off) |
| R8 | watch_spaces_dir() extended to match file events against trigger nodes without a second watcher |
| R9 | File-change events debounced per (space, pattern, path); duplicates within window dropped |
| R10 | Fan-out sends one run per harness per event; dedup is per-harness, not cross-harness |
| R11 | End-to-end: all three trigger kinds fire correctly; debounce fires exactly once per window |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). The body summary below mirrors them in compact form for the human reader.

- R1 -- EventBusEvent, EventDebouncer, fan_out_to_harnesses importable; kind constrained to three values; payload fields present
- R2 -- First call returns True; duplicate within window returns False; call after expiry returns True
- R3 -- Two harnesses with matching kind yield two run_ids; mismatched kind yields zero; brief contains payload
- R4 -- Valid webhook/file-change/task-state nodes pass; missing webhook fields raise ValidationError; defaults applied
- R5 -- Callback called with (space_id, task_id, old_state, new_state); absent callback does not error; no app.harnesses import in worker.py; callback exception does not abort finalize
- R6 -- Correct token yields 202 + run; wrong token yields 401; no token yields 401; no webhook trigger yields 404
- R7 -- api/harnesses.py contains comment block documenting Bearer scheme and Caddy limitation
- R8 -- File match enqueues harness once; existing SHA-throttle unmodified; no second awatch() call
- R9 -- Same file twice within window yields one fan_out call; after window expires yields second call
- R10 -- Two harnesses yield two runs; same event_id twice yields one run per harness
- R11 -- DONE task fires harness; webhook POST fires harness; file write fires harness; duplicate fires once

## Traceability

The full requirement to acceptance criteria to verifying_phase map is the YAML `traceability[]` array. Downstream agents read the YAML directly; this section exists so a human reader sees the same routing table without parsing YAML.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | New triggers.py module defines EventBusEvent, EventDebouncer, and fan_out_to_harnesses() |
| R2 | test | EventDebouncer.should_fire() correctly gates duplicate events within and outside the window |
| R3 | test | fan_out_to_harnesses() enqueues one run per matching harness and returns run_ids |
| R4 | test | Harness node validator extended for webhook, task-state-change, and file-change trigger data schemas |
| R5 | test | Worker emits task-state-change events via injected callback without direct harness import |
| R6 | test | New POST /{name}/webhook endpoint validates Bearer token and enqueues run |
| R7 | review | Webhook auth scheme documented in api/harnesses.py |
| R8 | test | watch_spaces_dir() extended without a second watcher |
| R9 | test | File-change events debounced per (space, pattern, path) |
| R10 | test | Fan-out sends one run per harness per event |
| R11 | manual | End-to-end: all three trigger kinds fire correctly with debounce |

## Assumptions

- `has_ui: false` rationale: all three trigger kinds are backend subsystem concerns; trigger node configuration is done via harness YAML; no new UI surface is required.
- Task-state-change emits only on DONE transition by default (not WAITING or ACTIVE) to minimize event volume; configurable via data.watched_state on the trigger node (R4).
- In-memory EventDebouncer (no persistent store): process restart clears the debounce window; acceptable because debounce windows are sub-second.
- Webhook auth tokens are stored in plaintext in harness YAML (scouted assumption confirmed); secrets API is a deferred concern.
- Caddy HTTP Basic Auth does NOT apply to webhook endpoint callers; the per-harness Bearer token is the sole auth layer for external webhook callers. Documented in-code (R7).
- Fan-out to harnesses happens in the event emission async context; enqueue_harness_run() is idempotent and fast enough that no persistent event queue is needed.
- The callback injection pattern for worker.py (R5) adds one optional keyword parameter to Worker.__init__; existing callers in main.py and tests are unaffected.
- fan_out_to_harnesses() queries active harnesses at event-emission time; no cache invalidation is needed.

## Open questions

- Should fan_out_to_harnesses() be an async coroutine (await enqueue_harness_run) or dispatch to a background task? Design agent should decide based on whether blocking the watcher loop is acceptable for the expected fan-out cardinality (likely <10 harnesses per space).
- Should the webhook endpoint be nested under /{name}/webhook (per-harness URL) or under a flat /webhook/{path} route where path resolves to the harness via data.webhook_path? Design agent should choose one and ensure no route ambiguity with existing endpoints.

## Next consumer brief

Read `traceability[]` as the ground truth for all 11 requirements. Key decision points:

1. **Module placement**: `backend/app/harnesses/triggers.py` is the proposed home. Confirm no circular imports given that `run_trigger.py` already imports from `storage.py` and `models.py`.

2. **Worker callback injection** (R5): proposed signature is `Worker.__init__(..., on_task_state_change: Callable | None = None)`. Wiring site is `main.py` where both Worker and HarnessStore are instantiated together.

3. **Webhook routing** (R6, open question 2): per-harness `/{name}/webhook` vs. flat `/webhook/{path}`. Per-harness URL is simpler and avoids a full harness scan on every request; recommend unless flat model is needed.

4. **fan_out_to_harnesses async** (open question 1): called from async contexts (watch_spaces_dir, worker callback wrapper) so plain await is viable; confirm no blocking harness-store read on the watcher hot path.

5. **Files to create or modify**: create `backend/app/harnesses/triggers.py`; modify `backend/app/harnesses/validator.py` (R4), `backend/app/harnesses/model.py` docstring (R4), `backend/app/worker.py` (R5 callback param), `backend/app/main.py` (R5 wiring + R8 file-event extension), `backend/app/api/harnesses.py` (R6 endpoint + R7 docs).

6. **Risk**: the watch_spaces_dir() extension (R8) must not introduce a blocking harness-store read on every file event; design should ensure the subscription lookup is cached or fast enough for the watcher hot path.
