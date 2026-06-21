---
cc_version: '1.0'
agent: pipeline-implementor
slug: g09-timed-wait-fix
phase: impl
status: done
confidence: 0.95
inputs_used:
- .cronos/pipeline/g09-timed-wait-fix/design-report-g09-timed-wait-fix.md
- backend/app/harnesses/wait.py
- backend/app/harnesses/run_state.py
- backend/app/harnesses/executor.py
- backend/tests/test_harness_run_state.py
- backend/tests/test_harness_wait.py
- backend/tests/test_harness_executor.py
outputs_produced:
- backend/app/harnesses/run_state.py
- backend/app/harnesses/wait.py
- backend/app/harnesses/executor.py
- backend/tests/test_harness_run_state.py
- backend/tests/test_harness_wait.py
- backend/tests/test_harness_executor.py
blockers: []
next_consumer: test
metrics:
  tool_calls: 42
  files_read: 7
  memory_hits: 2
  iterations_completed: 4
---

## Summary

Implemented the G09 timed-wait resume fix across four iterations. `NodeState.wake_at`
(ISO-8601 UTC string) is now persisted by the executor before sleeping; on restart
`await_timed_wait` sleeps only `max(0, wake_at - now)` so a 6-hour wait restarted
at T+5h59m wakes at T+6h (1 minute remaining), not T+12h. The BFS initial
ready-queue was extended to include in-progress timed Wait nodes whose predecessor
subtree is done, enabling the resume path without requiring agent re-execution.

## Files changed

| File | Change |
|------|--------|
| `backend/app/harnesses/run_state.py` | Added `wake_at: str \| None = None` field to `NodeState`; updated `from_dict()` to read `ns.get("wake_at")` for backward compat; `to_dict()` via `asdict()` serialises it automatically |
| `backend/app/harnesses/wait.py` | `await_timed_wait` now accepts `wake_at: str \| None = None`; when set, sleeps `max(0.0, (fromisoformat(wake_at) - now).total_seconds())`; falls back to full `duration_seconds` when `None`; updated module docstring; added `import datetime` |
| `backend/app/harnesses/executor.py` | Added `timedelta` to datetime imports; restructured `_execute_wait_node` timed branch: reads `prior_node_state = state.nodes_executed.get(node_id)` BEFORE overwriting (avoids the high-severity clobber risk); computes `wake_at = now + timedelta(seconds=duration)` on first entry only; persists `NodeState(in_progress, wake_at=wake_at)` BEFORE sleep; passes `wake_at` to `await_timed_wait`; extended Case-2 BFS initial ready-queue to include in-progress timed Wait nodes with in_degree=0 (resume path) |
| `backend/tests/test_harness_run_state.py` | No new tests needed (wake_at round-trips automatically via existing `asdict`/`from_dict` machinery; backward-compat covered by existing `test_node_state_timing_backwards_compat`) |
| `backend/tests/test_harness_wait.py` | Added `TestAwaitTimedWaitWakeAt` (5 tests) covering: future wake_at sleeps remaining, past wake_at fires immediately (0s), `wake_at=None` falls back to full duration, omitted wake_at falls back, exactly-now wake_at fires immediately |
| `backend/tests/test_harness_executor.py` | Added `TestTimedWaitResumeFix` (3 tests) for the three-path integration spec: fresh start persists wake_at (path 1), restart-before-wake sleeps remaining ≤35s (path 2), restart-after-wake sleeps 0s (path 3); added `_make_timed_wait_harness` helper |

## Out-of-scope findings

- The `_enqueue_successors` helper was not changed; a targeted BFS startup condition
  is sufficient and avoids broad side effects on other control-flow node types.
- Decision and Aggregator in-progress nodes on restart are left as-is (unchanged
  behaviour); only timed Wait nodes benefit from the resume path.
- No frontend changes (has_ui=false per analysis report).

## Assumptions

- `NodeState.wake_at` is serialised via `asdict()` which already handles the new
  field without any change to `to_dict()`; confirmed by existing round-trip tests.
- Python 3.12 `datetime.fromisoformat()` natively parses ISO-8601 with UTC offset
  (`+00:00`) produced by `.isoformat()` on a UTC-aware datetime.
- A real restart persists BOTH the trigger node (done) and the Wait node (in_progress)
  in the run_state JSON; tests reflect this by pre-populating `T1: done, W1: in_progress`.
- The narrow `-k` pytest validation commands fail `--cov-fail-under=60` (expected;
  per project feedback: set `validation_command_passed: true` for narrow-k runs
  that select the right tests and all pass).

## Open questions

None.

## Next consumer brief

The tester should run:
```
cd backend && pytest tests/test_harness_wait.py tests/test_harness_executor.py -k "timed_wait or TimedWait" -v --no-cov
```
All 6 G09-specific tests should pass. Also validate the full suite:
```
cd backend && pytest tests/ --no-cov -q
```
Expected: 2799 passed (as of this implementation). Key invariants to verify:
- `NodeState.wake_at` round-trips through JSON save/load (covered by existing run_state tests).
- `await_timed_wait(node, wake_at=past_time)` sleeps 0.0 seconds.
- `await_timed_wait(node, wake_at=future_time)` sleeps the remaining seconds.
- Executor BFS re-executes in-progress timed Wait nodes on resume (uses stored wake_at, not full duration).
