---
cc_version: "1.0"
agent: pipeline-reviewer
slug: arc6-event-triggers--attempt1
phase: review
status: done
confidence: 0.88
inputs_used:
  - memory:project_arc6_event_triggers_impl
  - memory:project_arc6_64_run_lifecycle_review
  - memory:observation_importlib_reload_test_pollution
  - .cronos/pipeline/arc6-event-triggers/design-report-arc6-event-triggers.md
  - .cronos/pipeline/arc6-event-triggers/analysis-report-arc6-event-triggers.md
  - .cronos/pipeline/arc6-event-triggers/request.md
  - .cronos/pipeline/arc6-event-triggers/impl-report-arc6-event-triggers--i1.md
  - .cronos/pipeline/arc6-event-triggers/impl-report-arc6-event-triggers--i2.md
  - .cronos/pipeline/arc6-event-triggers/impl-report-arc6-event-triggers--i3.md
  - .cronos/pipeline/arc6-event-triggers/impl-report-arc6-event-triggers--i4.md
  - .cronos/pipeline/arc6-event-triggers/impl-report-arc6-event-triggers--i5.md
  - .cronos/pipeline/arc6-event-triggers/impl-report-arc6-event-triggers--i6.md
  - .cronos/pipeline/arc6-event-triggers/test-report-arc6-event-triggers.md
  - backend/app/harnesses/triggers.py
  - backend/app/harnesses/validator.py
  - backend/app/harnesses/model.py
  - backend/app/worker.py
  - backend/app/main.py
  - backend/app/api/harnesses.py
  - backend/tests/harnesses/test_triggers_module.py
  - backend/tests/harnesses/test_validator_triggers.py
  - backend/tests/test_worker_event_callback.py
  - backend/tests/test_main_watch_file_change_trigger.py
  - backend/tests/api/test_harnesses_webhook.py
  - backend/tests/integration/test_event_triggers_e2e.py
outputs_produced:
  - .cronos/pipeline/arc6-event-triggers/review-report-arc6-event-triggers--attempt1.md
blockers: []
next_consumer: doc
metrics:
  tool_calls: 16
  files_read: 24
  memory_hits: 3
  diff_lines_reviewed: 3871
verdict: pass
attempt: 1
findings:
  - id: F1
    severity: low
    file: backend/tests/harnesses/__init__.py
    evidence: "Empty package marker created alongside test files in I1/I4/I6 (also backend/tests/api/__init__.py and backend/tests/integration/__init__.py) but not listed in design iterations[].scope_files. Each impl report flagged this as a structural prerequisite for pytest discovery."
    blocking: false
    suggested_action: "No code change required. In the next pipeline cycle, the architect should explicitly include __init__.py package markers in scope_files when proposing a new tests/ subdirectory, so the implementor's files_changed[] stays a strict subset of scope_files[] without informal carve-outs."
  - id: F2
    severity: medium
    file: backend/app/main.py:443
    evidence: "Callback injection uses `worker._on_task_state_change = _on_task_state_change` after `worker_pool.start_for_space(space.id)` inside the lifespan() loop. WorkerPool.start_for_space() itself does not forward the callback, so any space created via the spaces API after lifespan boot will start a Worker with on_task_state_change=None and silently never fire task-state-change triggers for tasks in that space (I5 Next-consumer-brief point 2 acknowledges this gap)."
    blocking: false
    suggested_action: "Follow-up goal: thread on_task_state_change through WorkerPool.start_for_space() so callback injection happens at every worker construction site, not just lifespan boot. Until then, document the runtime limitation in the harness operator docs so users do not silently observe missing fan-outs on dynamically-created spaces."
  - id: F3
    severity: low
    file: backend/app/api/harnesses.py:454
    evidence: "Short-token warning (`if len(auth_token) < 16 and warn_key not in _SHORT_TOKEN_WARNED`) fires on the first POST to /webhook for that harness, not at harness YAML load time. Design risk mitigation specified 'log.warning emitted once-per-process if any harness YAML stores a webhook auth_token shorter than 16 characters' — strict reading would emit the warning on every store load, surfacing weak tokens without waiting for the first webhook hit."
    blocking: false
    suggested_action: "Either accept the current at-first-use semantics (low impact since the warning still fires before any sustained webhook traffic) or move the short-token scan into HarnessStore.create / reload so weak tokens are flagged at config time. Cheap follow-up; non-blocking."
  - id: F4
    severity: low
    file: backend/app/harnesses/validator.py:133
    evidence: "Design specifies `task-state-change` defaults `watched_state` to DONE and the validator applies that default via `_apply_trigger_defaults`. The worker callback (worker.py:825) hard-codes `if new_state == TaskState.DONE` and never reads `watched_state` from the trigger node, so a harness with `watched_state: ACTIVE` validates clean but never fires. Analyst explicitly defers non-DONE watched_state to follow-up (analysis report `## Deferred` line 225), so behaviour is consistent with the contract but the `watched_state` field is currently inert."
    blocking: false
    suggested_action: "Either document `watched_state` as accepted-but-currently-DONE-only in model.py docstring and validator messages, or implement state matching in fan_out_to_harnesses / the worker callback. Tracking item; non-blocking under the explicit deferral."
  - id: F5
    severity: low
    file: backend/app/main.py:223
    evidence: "Watcher hot path imports `from datetime import UTC, datetime as _wdt` (line 256) and `from pathlib import PurePath` (line 181) inside the function body for every change batch. These are cheap but constant overhead in a hot path the design explicitly wants kept tight."
    blocking: false
    suggested_action: "Hoist these two imports to module top (`from datetime import UTC` / `from pathlib import PurePath` are already imported transitively but rebinding inside the loop is unnecessary). Style-only; no behaviour change."
---

## Summary

All six iterations (I1-I6) land within their designed `scope_files` boundaries; the only files modified outside scope are three empty `tests/<subdir>/__init__.py` package markers (`harnesses/`, `api/`, `integration/`) which every implementor flagged as structural prerequisites for pytest discovery (F1 — non-blocking, advisory). The tester gate is green (2841 passed, 0 failed, 84.28% coverage, exit 0), and a code-level walk of `triggers.py`, `validator.py`, `worker.py`, `api/harnesses.py`, and `main.py` confirms every headline acceptance criterion from `request.md` is satisfied: task-state-change fires from `_finalize()` via the injected callback when `new_state == DONE`; `POST /api/spaces/{space_id}/harnesses/{name}/webhook` returns 202 with run_ids on valid Bearer auth; file-change events from the existing single `awatch()` loop are pattern-matched and dispatched via `asyncio.create_task()` (no double-watch); and `EventDebouncer` collapses duplicate `event_id`s within the per-harness debounce window. Two medium/low concerns are real but non-blocking and explicitly scoped: F2 — workers started by `WorkerPool.start_for_space()` after lifespan boot do not receive the callback (acknowledged in I5 brief; would need WorkerPool changes that were out of I5's scope); F4 — `watched_state` field is validated but inert because non-DONE transitions are explicitly deferred per the analysis report. Verdict: pass; proceed to doc.

## Findings

- F1 (low, non-blocking): three empty `__init__.py` package markers created outside `scope_files[]` as a structural prerequisite for pytest collection.
- F2 (medium, non-blocking): on_task_state_change callback only injected in `lifespan()`; spaces created mid-process via WorkerPool.start_for_space() will not have the callback set.
- F3 (low, non-blocking): short-token warning fires lazily at first webhook hit rather than at harness load time (design said "if any harness YAML stores ...").
- F4 (low, non-blocking): `watched_state` field validates but is unused — worker hard-codes DONE-only invocation; explicitly deferred per analysis `## Deferred`.
- F5 (low, non-blocking): cosmetic — hoist in-loop `from datetime` / `from pathlib` imports to module top in watch_spaces_dir().

## Verdict

pass. No finding carries `blocking: true`; scope conformance is clean modulo three empty package markers; all four headline acceptance criteria from request.md verify against the diff and against the integration test suite; test gate is green at 2841p/0f and 84.28% coverage.

## Assumptions

- Scope contract taken from design `iterations[].scope_files[]` union; three empty `__init__.py` files outside that union are treated as structural prerequisites consistent with `arc6-control-flow` / `arc6-harness-model` precedent rather than scope escapes.
- The tester report's gate decision (`gate_decision: pass`, 0 failed) is authoritative; the pre-existing flaky failures in `test_worker_lifecycle.py` mentioned by I6 did not surface in the full-suite gate run.
- The `validation_command_passed: true` status from every iteration despite non-zero exit from `--cov-fail-under=60` on single-file runs is treated as accurate per established codebase precedent — the failure mode is exclusively the pyproject.toml addopts coverage gate, not a test logic failure.
- The "no runtime import of app.harnesses in worker.py" R5 invariant is verified both by source grep in `test_worker_has_no_runtime_harnesses_import` and by direct inspection: the only `harnesses` reference at module scope is inside a `TYPE_CHECKING` block; the two intra-function imports (lines 468, 554) pre-date I3.
- Memory entry `observation_importlib_reload_test_pollution` justifies the deliberately grep-only no-import test (no `importlib.reload()`), matching the global rule.

## Open questions

- None.

## Next consumer brief

Doc agent: the three event trigger kinds (`task-state-change`, `webhook`, `file-change`) and the new `POST /api/spaces/{space_id}/harnesses/{name}/webhook` endpoint are now part of the harness public surface. User-visible behaviour to document:

1. Harness operators can author trigger nodes with `data.kind` set to one of three literal hyphenated strings: `task-state-change`, `webhook`, `file-change`. Per-kind required fields and defaults are documented in `backend/app/harnesses/model.py`.
2. Webhook authentication uses a per-harness Bearer token stored in plaintext in the harness YAML; Caddy HTTP Basic Auth does NOT gate `/webhook` callers — the inline comment block in `api/harnesses.py` explains the trade-off.
3. Known limitation worth surfacing in operator docs (F2): only spaces that exist when the backend starts have task-state-change triggers wired; spaces created via the spaces API at runtime will not fire task-state-change harnesses until the backend restarts. A follow-up goal will close this gap.
4. Debounce default is 0.5 s; configurable per trigger node via `data.debounce_seconds`. In-memory state is per-process and is lost on restart.

No findings are blocking; no implementor revision is required. Proceed to doc-sync.
