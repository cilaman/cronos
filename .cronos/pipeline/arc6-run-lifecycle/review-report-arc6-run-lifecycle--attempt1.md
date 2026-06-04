---
cc_version: "1.0"
agent: pipeline-reviewer
slug: arc6-run-lifecycle--attempt1
phase: review
status: done
confidence: 0.88
inputs_used:
  - .cronos/pipeline/arc6-run-lifecycle/design-report-arc6-run-lifecycle.md
  - .cronos/pipeline/arc6-run-lifecycle/impl-report-arc6-run-lifecycle--i1.md
  - .cronos/pipeline/arc6-run-lifecycle/impl-report-arc6-run-lifecycle--i2.md
  - .cronos/pipeline/arc6-run-lifecycle/impl-report-arc6-run-lifecycle--i3.md
  - .cronos/pipeline/arc6-run-lifecycle/impl-report-arc6-run-lifecycle--i4.md
  - .cronos/pipeline/arc6-run-lifecycle/impl-report-arc6-run-lifecycle--i5.md
  - .cronos/pipeline/arc6-run-lifecycle/impl-report-arc6-run-lifecycle--i6.md
  - .cronos/pipeline/arc6-run-lifecycle/impl-report-arc6-run-lifecycle--i7.md
  - .cronos/pipeline/arc6-run-lifecycle/impl-report-arc6-run-lifecycle--i8.md
  - .cronos/pipeline/arc6-run-lifecycle/test-report-arc6-run-lifecycle.md
  - backend/app/harnesses/run_state.py
  - backend/app/harnesses/run_index.py
  - backend/app/harnesses/executor.py
  - backend/app/worker.py
  - backend/app/api/harnesses.py
  - backend/app/api/harness_runs.py
  - backend/app/main.py
  - backend/tests/test_api_harnesses.py
  - backend/tests/test_api_harness_runs.py
  - backend/tests/test_api_harness_runs_sse.py
  - backend/tests/test_harness_executor_e2e.py
  - frontend/src/router.tsx
outputs_produced:
  - .cronos/pipeline/arc6-run-lifecycle/review-report-arc6-run-lifecycle--attempt1.md
blockers: []
next_consumer: implementation
metrics:
  tool_calls: 18
  files_read: 22
  memory_hits: 0
  diff_lines_reviewed: 3876
verdict: needs_fix
attempt: 1
findings:
  - id: F1
    severity: critical
    file: backend/app/worker.py:402
    evidence: "`_resume_harness_run` is the *only* call site of `HarnessExecutor.execute()` in production code (worker.py:471). It short-circuits with `return False` when `run_state.waiting_node_id is None`, which is always true for a freshly-triggered run. `_run_task` then proceeds to `run_agent(task_id, ...)` — invoking the Claude Code CLI on a task that has no agent association. POST /api/spaces/{space_id}/harnesses/{name}/run therefore creates a task, appends a RunSummary, transitions to ACTIVE, enqueues it, and the worker tries to spawn an agent process instead of running the harness DAG. Acceptance criterion 'POST /run executes' is not met. The 5 trigger/list/cancel tests in test_api_harnesses.py mock the worker entirely; no e2e test verifies that enqueue → executor.execute() actually runs."
    blocking: true
    suggested_action: "In backend/app/worker.py, add an initial-run branch to `_run_task` (or refactor `_resume_harness_run` into a generic `_maybe_run_harness` that handles both initial and resume). Detection: query `worker.lookup_space_id(task_id)` (or check that the task id appears in the run index for some harness in the same space). When matched, build the HarnessExecutor with `event_worker=self` (see F2) and call `executor.execute(task_id, harness, space)` instead of falling through to `run_agent`. Add an integration test in tests/test_harness_executor_e2e.py that calls `worker.enqueue(run_id)` after POST /run and asserts the run_state.json transitions through `running` → `done` without ever invoking run_agent."
  - id: F2
    severity: high
    file: backend/app/worker.py:471
    evidence: "`executor = HarnessExecutor(self.store, _WorkerProtocolAdapter(self), _tools_resolver)` omits the 4th positional/keyword argument `event_worker`, which defaults to `None`. The executor's `_publish_event` method (executor.py:669) is a no-op when `self._worker is None`. Consequently all `node_transition`, `edge_chosen`, and `run_status` events that I3 added at lines 327, 488, 538, 592, 656, 776, 795, 833, 867, 910, 929 (etc.) are silently dropped. The SSE endpoint (`GET /api/harness-runs/{run_id}/stream`) will receive only the legacy `run_start`/`run_end` events from `Worker._publish` — the discriminated harness envelope the design risk register relied on is never emitted in production. Acceptance 'SSE replays prior transitions to a late subscriber' is not met for harness-specific transitions."
    blocking: true
    suggested_action: "Change worker.py:471 to `executor = HarnessExecutor(self.store, _WorkerProtocolAdapter(self), _tools_resolver, event_worker=self)`. Verify with an integration test (extend tests/test_harness_executor_e2e.py): run a small harness end-to-end via the Worker and assert that `worker._run_buffer[run_id]` contains at least one `{type: 'node_transition'}` event. Apply the same fix to any new initial-run call site introduced for F1."
  - id: F3
    severity: high
    file: frontend/src/router.tsx:13
    evidence: "Commit 9e6d915 modifies `frontend/src/router.tsx` (`import { HarnessRunsPage } from './pages/HarnessRunsPage'` plus the `<Route path=\"spaces/:spaceId/harnesses/:name/runs\" element={<HarnessRunsPage />} />` line) — but `router.tsx` does NOT appear in any iteration's `scope_files[]`. The design assigned `frontend/src/App.tsx` to I8 (which routes in this project no longer live in). I8's impl report explicitly disclosed this gap as an `out_of_scope_findings` entry and stated 'App.tsx was left unchanged'. Yet the commit edits router.tsx anyway — a scope escape relative to the design contract."
    blocking: true
    suggested_action: "Either (a) revert the router.tsx hunk and have the architect re-scope a follow-up iteration with `frontend/src/router.tsx` in `scope_files[]` to re-apply the route, or (b) emit a one-iteration design revision that adds `frontend/src/router.tsx` to a new (or amended) I8 scope so the existing edit becomes contract-compliant. Note: the change itself is required for the page to be reachable; the issue is purely the scope contract. Recommended: option (b) — patch the design to legitimise the existing hunk and replace App.tsx in I8's scope_files with router.tsx."
  - id: F4
    severity: medium
    file: backend/app/api/harness_runs.py:106
    evidence: "`cancel_harness_run` writes `status='cancelled'` to RunState, calls `target_worker.stop_current(run_id)`, bulk-marks nodes failed, and updates the run index — but does NOT call `target_worker._publish(run_id, {'type': 'run_status', 'status': 'cancelled', ...})`. SSE subscribers connected to `/api/harness-runs/{run_id}/stream` therefore never see a cancellation event in the live stream. They learn of the cancellation only when the executor's next BFS boundary fires `run_status: cancelled` (which won't happen if the executor has already returned, e.g. cancel between nodes after a fast run) or when they poll `GET /api/harness-runs/{run_id}`. The cancel test in test_api_harness_runs.py only asserts the file state, not SSE emission."
    blocking: false
    suggested_action: "After save_atomic on line 176, call `await target_worker._publish(run_id, {'type': 'run_status', 'run_id': run_id, 'status': 'cancelled', 'timestamp': now_iso})` so subscribers see the cancellation immediately. Add an assertion to test_api_harness_runs_sse.py that subscribing then cancelling produces a `run_status: cancelled` frame on the stream."
  - id: F5
    severity: low
    file: backend/app/api/harness_runs.py:214
    evidence: "`if len(replay) >= _RUN_BUFFER_CAP: emit buffer_truncated`. Worker._publish trims with `if len(buf) > _RUN_BUFFER_CAP: del buf[: len(buf) - _RUN_BUFFER_CAP]`. After a single overflow the buffer is left at exactly `_RUN_BUFFER_CAP`, so `>=` is correct for overflow. But a buffer that has reached exactly 2000 events without overflow (i.e. exactly capacity) will also trigger the badge — a false positive. The design specified an explicit `_overflow` flag for this reason; I6 substituted a length check (documented in its assumptions)."
    blocking: false
    suggested_action: "Either (a) introduce a per-task-id `_overflow: dict[str, bool]` flag in Worker that is set in `_publish` when the trim branch executes, and check that flag in `_sse_harness_run_events` instead of `len(replay) >= cap`; or (b) accept the edge case and document it in the SSE docstring. Option (a) matches the original design and is ~6 lines of code in worker.py plus a 1-line check change here."
---

## Summary

Implementation completes the data layer (I1-I2), executor + worker cache (I3-I4), REST API surface (I5), SSE stream (I6), and frontend hooks/UI (I7-I8) with comprehensive unit coverage. The test report records 2709 tests green and 83.2% coverage. However, two integration-level wiring gaps make the core acceptance criteria fail in production: (F1) the Worker has no code path that invokes `HarnessExecutor.execute()` for an *initial* run — only the WAITING-resume path exists, so `POST /run` enqueues a task that the worker tries to execute as a regular agent; and (F2) the one harness executor instantiation in the worker omits `event_worker=self`, so all harness SSE events are silently dropped. A scope escape (F3) was also introduced in `frontend/src/router.tsx` outside any iteration's `scope_files[]`. Two non-blocking findings (F4 missing SSE cancel event, F5 buffer_truncated edge case) are noted for follow-up.

## Findings

- **F1 critical blocking** — Production worker has no initial-run path that calls `HarnessExecutor.execute()`. POST /run creates a task and enqueues it; the worker treats it as a regular agent task and tries `run_agent`. Tests mock the worker so this defect is invisible to the unit suite.
- **F2 high blocking** — `worker.py:471` omits `event_worker=self`, leaving all executor SSE events as no-ops in production. The new unit tests at `test_harness_executor.py:1255/1370/1396` pass `event_worker=worker` but production never does.
- **F3 high blocking** — `frontend/src/router.tsx` was modified outside any iteration's `scope_files[]`. I8's report explicitly listed router.tsx as an out-of-scope concern then the commit edits it anyway. Scope escape.
- **F4 medium non-blocking** — Cancel handler does not publish a `run_status: cancelled` SSE event. Live subscribers won't see cancellation unless the executor's BFS-boundary check fires.
- **F5 low non-blocking** — `buffer_truncated` heuristic is `len(replay) >= _RUN_BUFFER_CAP`, a false-positive when buffer is exactly at capacity without overflow.

## Verdict

needs_fix. Three blocking findings (F1 critical, F2/F3 high) prevent the goal's acceptance criteria from being met in production despite a fully green unit suite; the test architecture mocked out the worker→executor path so the defects were not caught by tests.

## Assumptions

- Scope contract taken from design `iterations[].scope_files[]` union; tests/ paths counted as in-scope only for their listed iteration.
- The gate decision in the test report (`pass`, 2709p/0f/0e, coverage 83.2%) is taken at face value; I did not re-run the suite.
- "Scope escape" is judged against the design's literal `scope_files[]` lists, not against what would have been a sensible scope (router.tsx clearly should have been listed).
- `HarnessExecutor` does have an `event_worker` keyword parameter (verified at executor.py:268) and the real `Worker` class implements `_publish` matching the WorkerProtocol (verified at worker.py:1229), so the F2 fix is a single-line change at the production instantiation site.

## Open questions

- None.

## Next consumer brief

Implementor: address F1, F2, F3 to clear the blocking gates. The minimum diff is roughly:
1. **F1** — In `backend/app/worker.py`, generalise `_resume_harness_run` to handle initial runs (or add a sibling `_maybe_run_initial_harness` invoked from `_run_task` before `run_agent`). Detection cue: the task's id is in `self._run_id_to_space_id` (the cache populated by `register_run` on POST /run). Build the executor with `event_worker=self`. Add an e2e test in `tests/test_harness_executor_e2e.py` that enqueues a freshly-triggered run and asserts the run_state.json terminal status is `done` and that `_run_buffer[run_id]` contains node_transition events.
2. **F2** — Single-line fix at worker.py:471 (add `event_worker=self`). Same fix in the new initial-run path added for F1.
3. **F3** — Architect should patch the design to either include `frontend/src/router.tsx` in I8's `scope_files[]` (replacing or augmenting App.tsx) and produce a thin design-revision report. The implementor then re-asserts the existing router.tsx hunk as contract-compliant without further edits.

F4 and F5 are non-blocking — bundle them with the F1/F2/F3 fix attempt or defer to a separate clean-up iteration.
