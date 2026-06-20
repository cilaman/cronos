---
cc_version: '1.0'
agent: pipeline-analyst
slug: g09-timed-wait-fix
phase: analysis
status: done
confidence: 0.95
inputs_used:
- memory:project-remediation-board-setup
- .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
- .cronos/workspaces/2026-06-20-1427-create-remedy-goals/REMEDIATION-PLAN.md
- backend/app/harnesses/wait.py
- backend/app/harnesses/run_state.py
- backend/app/harnesses/executor.py
outputs_produced:
- .cronos/pipeline/g09-timed-wait-fix/analysis-report-g09-timed-wait-fix.md
blockers: []
next_consumer: design
request: 'G09: Timed-wait resume fix (sleep remaining, not full duration). Fix a single-function
  bug in timed harness waits. After: A harness node that entered a 6-hour wait at
  T=0, restarted at T=5h59m, wakes at T=6h (1 minute remaining), not at T+6h (duplicate
  full wait). Tests confirm the fix with a short duration. This is a high-confidence
  single-function fix with clear acceptance criteria.'
has_ui: false
coverage_summary:
  searched:
  - backend/app/harnesses/wait.py
  - backend/app/harnesses/run_state.py
  - backend/app/harnesses/executor.py (lines 1040–1058)
  excluded:
  - frontend/: backend-only fix, no UI changes
  - backend/app/worker.py: not in scope; executor handles wait dispatch
  strategies:
  - memory_retrieval
  - read_targeted
traceability:
- requirement_id: R1
  statement: NodeState gains an optional wake_at field (ISO-8601 UTC string) so the
    target absolute wake time for a timed Wait node is persisted to RunState and survives
    a process restart.
  acceptance_criteria:
  - Given a NodeState dict round-tripped through to_dict()/from_dict(), when wake_at
    is present, it is preserved exactly.
  - When wake_at is absent (legacy or non-timed nodes), from_dict() returns None without
    error.
  - RunState.from_dict() handles a JSON file that pre-dates this field (missing key)
    cleanly.
  verifying_phase: test
  confidence: 0.97
- requirement_id: R2
  statement: When a timed Wait node is first entered, the executor computes wake_at
    = now + duration_seconds (UTC), writes it to nodes_executed[node_id].wake_at,
    and persists RunState atomically before the sleep begins.
  acceptance_criteria:
  - Given a fresh run (no existing wake_at for the node), when the executor reaches
    a timed Wait node, the persisted RunState JSON contains wake_at for that node
    before asyncio.sleep is called.
  - The stored wake_at is approximately now + duration_seconds (within 1 second tolerance).
  verifying_phase: test
  confidence: 0.93
- requirement_id: R3
  statement: On resume when RunState already contains wake_at for the node, the sleep
    duration is max(0.0, wake_at − now) seconds, not the full configured duration_seconds.
  acceptance_criteria:
  - Given a RunState with wake_at 2 seconds in the future, when await_timed_wait is
    invoked with that wake_at, the actual sleep is ≤ 2 seconds (not the original duration_seconds).
  - The configured duration_seconds value is not read or used when wake_at is already
    present on the node state.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R4
  statement: If wake_at has already passed at resume time (wake_at − now ≤ 0), the
    timed wait completes immediately without sleeping.
  acceptance_criteria:
  - Given a RunState with wake_at 10 seconds in the past, when await_timed_wait is
    invoked with that wake_at, the coroutine returns in under 0.1 seconds.
  verifying_phase: test
  confidence: 0.97
- requirement_id: R5
  statement: 'Tests cover the three distinct paths: first-entry (no wake_at), restart-before-wake
    (wake_at in future), and restart-after-wake (wake_at in past).'
  acceptance_criteria:
  - A test asserts that on first entry with duration=0.1s the node sleeps approximately
    0.1s and wake_at is recorded.
  - A test asserts that on resume with wake_at 0.05s in the future the total elapsed
    time is ≤ 0.1s (not a repeat of the original duration).
  - A test asserts that on resume with wake_at already passed the elapsed time is
    < 0.05s.
  - All three tests pass against the modified code without mocking asyncio.sleep (use
    a short duration so tests run fast).
  verifying_phase: test
  confidence: 0.92
metrics:
  tool_calls: 7
  files_read: 6
  memory_hits: 1
---

## Summary

G09 fixes a single-function MVP bug in timed harness Wait nodes: `await_timed_wait` in `backend/app/harnesses/wait.py` always sleeps the full configured `duration_seconds` regardless of how much time has already elapsed, so a process restart during a multi-hour wait causes the full wait to repeat. The fix requires persisting an absolute UTC wake time to `RunState` (via `NodeState.wake_at`) before the sleep begins, then computing remaining sleep as `max(0.0, wake_at − now)` on every entry including resume. Scope is tight: three files, one new field, one refactored coroutine, one executor call-site change. No UI work is needed.

## Scope

### In scope
- Add optional `wake_at: str | None` field to `NodeState` in `backend/app/harnesses/run_state.py`
- Update `RunState.to_dict()` / `from_dict()` / `NodeState` serialisation to round-trip `wake_at` (backward-compatible: missing key → None)
- Modify executor timed-wait path (`backend/app/harnesses/executor.py`, lines ~1051–1058) to compute and persist `wake_at` before sleeping
- Refactor `await_timed_wait` in `backend/app/harnesses/wait.py` to accept the persisted `wake_at` and compute remaining sleep
- Tests for all three paths: first-entry, restart-before-wake, restart-after-wake

### Out of scope
- Human-mode Wait nodes (`enter_wait`) — unaffected by this change
- Harness executor BFS logic beyond the timed-Wait dispatch block
- `worker.py` — worker calls `executor.execute()` unchanged; no changes needed there
- UI / frontend
- Other `RunState` fields (status, waiting_node_id, etc.)

### Deferred
- Millisecond-precision monotonic clock for sub-second durations (UTC datetime arithmetic is sufficient for the minute-to-hour durations this feature targets)
- Notification / SSE event when timed wait fires early on resume (nice-to-have observability, not required by the acceptance criteria)

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | NodeState gains optional wake_at field, round-tripped through serialisation |
| R2 | Executor writes wake_at before first sleep and persists RunState atomically |
| R3 | On resume with existing wake_at, sleep is max(0, wake_at − now) not full duration |
| R4 | If wake_at is already past at resume, timed wait fires immediately (zero sleep) |
| R5 | Tests cover first-entry, restart-before-wake, and restart-after-wake paths |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array. Summary below for human readers.

- R1 — NodeState.wake_at round-trips through to_dict/from_dict; absent key loads as None without error
- R2 — After entering timed wait for the first time, the persisted RunState JSON contains wake_at ≈ now + duration before asyncio.sleep executes
- R3 — Resume with wake_at 2s in future sleeps ≤ 2s, not the original duration_seconds
- R4 — Resume with wake_at already past returns in < 0.1s
- R5 — Three test cases (first-entry / before-wake / after-wake) all pass with a short duration (≤ 0.1s) without mocking asyncio.sleep

## Traceability

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | NodeState gains optional wake_at field, round-tripped through serialisation |
| R2 | test | Executor writes wake_at before first sleep and persists RunState atomically |
| R3 | test | On resume with existing wake_at, sleep is max(0, wake_at − now) not full duration |
| R4 | test | If wake_at is already past at resume, timed wait fires immediately (zero sleep) |
| R5 | test | Tests cover first-entry, restart-before-wake, and restart-after-wake paths |

## Assumptions

- has_ui=false rationale: the fix is entirely in the harness executor/wait backend; no frontend component observes or displays timed-wait progress.
- `NodeState` is the right carrier for `wake_at` (not a top-level `RunState` field), because each Wait node has its own independent wake time and RunState already keyed per-node data in `nodes_executed`.
- UTC datetime arithmetic (Python `datetime.datetime.now(tz=datetime.timezone.utc)`) is the correct clock; monotonic clocks are not usable for cross-restart persistence.
- Backward compatibility is required: existing RunState JSON files (without `wake_at`) must load cleanly via `from_dict()`. Missing key → None, treated as first-entry case.
- The scout confirmed (wait.py lines 16–20, 139–141) that the limitation is explicitly documented in the codebase as an intentional deferral — this goal removes that deferral.
- The executor's existing `_maybe_save(state, run_state_path)` call at line 1056 can be moved or duplicated to before the sleep; the design agent will decide exact placement.

## Open questions

None.

## Next consumer brief

**Design agent should:**

1. Read `traceability[]` for the 5 requirements; all have `verifying_phase: test` — every requirement needs a test.
2. Read `has_ui: false` — no frontend iteration needed.
3. Decide signature for `await_timed_wait`: options include `(node, wake_at: str | None)` receiving pre-computed UTC string, or `(node, node_state: NodeState)` receiving the full node state. Either satisfies R3/R4; choose whichever keeps the function pure and testable.
4. Decide where `wake_at` is set: either in the executor before calling `await_timed_wait` (clearest call-site), or inside `await_timed_wait` itself on first call. Note that the executor already calls `_maybe_save` at line 1056 — a pre-sleep save must come before `asyncio.sleep`.
5. The three test paths (R5) should share a helper that builds a minimal RunState with a controlled `wake_at` offset. No mocking of `asyncio.sleep` — use real sleep with durations ≤ 0.1s.
6. No new files are expected: changes land in `wait.py`, `run_state.py`, `executor.py`, and the existing test file(s) for harnesses.
