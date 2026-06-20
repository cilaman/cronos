---
cc_version: '1.0'
agent: pipeline-architect
slug: g09-timed-wait-fix
phase: design
status: done
confidence: 0.9
inputs_used:
- memory:project-remediation-board-setup
- .cronos/pipeline/g09-timed-wait-fix/analysis-report-g09-timed-wait-fix.md
- backend/app/harnesses/wait.py
- backend/app/harnesses/run_state.py
- backend/app/harnesses/executor.py
outputs_produced:
- .cronos/pipeline/g09-timed-wait-fix/design-report-g09-timed-wait-fix.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - backend/app/harnesses/wait.py
  - backend/app/harnesses/run_state.py
  - backend/app/harnesses/executor.py
  excluded:
  - 'frontend/: backend-only fix, has_ui=false'
  - 'backend/app/worker.py: re-enters executor.execute() unchanged; no change needed'
  strategies:
  - memory_retrieval
  - read_targeted
iterations:
- id: I1
  type: data
  scope_files:
  - backend/app/harnesses/run_state.py
  - backend/tests/test_harness_run_state.py
  validation_command: cd backend && pytest tests/test_harness_run_state.py -v
  max_diff_lines: 120
  depends_on: []
- id: I2
  type: backend
  scope_files:
  - backend/app/harnesses/wait.py
  - backend/tests/test_harness_wait.py
  validation_command: cd backend && pytest tests/test_harness_wait.py -v
  max_diff_lines: 150
  depends_on: []
- id: I3
  type: backend
  scope_files:
  - backend/app/harnesses/executor.py
  - backend/tests/test_harness_executor.py
  validation_command: cd backend && pytest tests/test_harness_executor.py -k wait
    -v
  max_diff_lines: 200
  depends_on:
  - I1
  - I2
- id: I4
  type: backend
  scope_files:
  - backend/tests/test_harness_executor.py
  validation_command: cd backend && pytest tests/test_harness_executor.py -k timed_wait
    -v
  max_diff_lines: 180
  depends_on:
  - I3
risks:
- description: _execute_wait_node (executor.py line ~1037) unconditionally assigns
    NodeState(status='in_progress') on every entry, which discards any wake_at restored
    from a resumed RunState. If I3 overwrites the node state before reading the prior
    wake_at, the resume case silently re-sleeps the full duration and R2/R3 fail despite
    the field existing.
  severity: high
  mitigation: I3 must read the prior node state (state.nodes_executed.get(node_id))
    and reuse its wake_at if present BEFORE constructing the new NodeState; only compute
    now+duration when no prior wake_at exists. I4's restart-before-wake test asserts
    the sleep is shorter than the configured duration, catching any clobber regression.
- description: Legacy RunState JSON files persisted before this change have no wake_at
    key; from_dict() must tolerate the missing key or resume will raise KeyError and
    crash the executor on the first restart after deploy.
  severity: medium
  mitigation: I1 uses ns.get('wake_at') (default None) in RunState.from_dict() and
    adds a test loading a NodeState dict with no wake_at key, asserting it returns
    None without error (R1 acceptance criterion 3).
- description: Tests use real asyncio.sleep with sub-second durations; CI scheduling
    jitter could make a strict equality assertion (elapsed == duration) flaky.
  severity: medium
  mitigation: All R5 tests assert bounded inequalities (elapsed <= upper_bound) with
    generous tolerance (e.g. <= 0.1s for a 0.05s wake offset), never equality; durations
    stay <= 0.1s so the suite remains fast.
- description: wake_at stored as a timezone-naive or local-time string would compute
    a wrong remaining sleep across processes in different TZs.
  severity: low
  mitigation: I2/I3 standardise on datetime.datetime.now(datetime.timezone.utc) for
    both the write (now+duration) and the read (wake_at - now), and serialise via
    .isoformat() so the offset is explicit; parse with datetime.fromisoformat().
metrics:
  tool_calls: 10
  files_read: 4
  memory_hits: 1
  iterations_planned: 4
---

## Summary

G09 fixes the timed-Wait re-sleep bug by persisting an absolute UTC wake time
so restarts sleep only the remaining interval. The change splits into four
iterations: a data iteration adding `NodeState.wake_at` with backward-compatible
round-trip (I1), a pure refactor of `await_timed_wait` to accept a `wake_at`
string and sleep `max(0, wake_at - now)` (I2), the executor wiring that computes
and persists `wake_at` before the sleep while preserving any restored value
(I3), and a dedicated three-path integration test iteration (I4). I1 and I2 are
independent (DAG layer 0); I3 depends on both; I4 depends on I3. The load-bearing
risk is the executor clobbering a restored `wake_at` when it re-initialises the
node state on resume — mitigated by reading the prior state first and verified by
I4's restart-before-wake test.

## Components

### Data
- `NodeState.wake_at: str | None` (run_state.py): optional ISO-8601 UTC absolute wake time for a timed Wait node; defaults to None for non-timed/legacy nodes.
- `RunState.from_dict()` (run_state.py): reads `wake_at` via `ns.get("wake_at")` so pre-existing JSON files load cleanly; `to_dict()` already serialises via `asdict()` so the new field round-trips automatically.

### Backend
- `await_timed_wait(node, wake_at)` (wait.py): refactored to accept the persisted `wake_at`; computes remaining sleep as `max(0.0, (wake_at - now).total_seconds())`; sleeps full `duration_seconds` only when `wake_at` is None (defensive fallback). Removes the stale arc6.3 MVP "re-sleep full duration" limitation note.
- `_execute_wait_node` timed branch (executor.py ~1051–1058): on entry, reads any prior `wake_at` from the restored node state; if absent computes `wake_at = now + duration_seconds` (UTC); writes it to `NodeState.wake_at`; persists RunState atomically (`_maybe_save`) BEFORE awaiting; passes `wake_at` to `await_timed_wait`; on completion marks the node done.

<!-- Frontend sub-section omitted: has_ui=false in the analysis report. -->

## Implementation plan

| ID  | Type    | Depends on | Scope files (abridged)                                              | Validation                                              |
|-----|---------|------------|--------------------------------------------------------------------|--------------------------------------------------------|
| I1  | data    | -          | run_state.py, test_harness_run_state.py                            | cd backend && pytest tests/test_harness_run_state.py -v |
| I2  | backend | -          | wait.py, test_harness_wait.py                                      | cd backend && pytest tests/test_harness_wait.py -v      |
| I3  | backend | I1, I2     | executor.py, test_harness_executor.py                             | cd backend && pytest tests/test_harness_executor.py -k wait -v |
| I4  | backend | I3         | test_harness_executor.py                                          | cd backend && pytest tests/test_harness_executor.py -k timed_wait -v |

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Executor clobbers restored `wake_at` on resume by re-initialising NodeState | high | I3 reads prior node state and reuses its `wake_at` before constructing the new NodeState; I4 restart-before-wake test asserts shortened sleep |
| Legacy RunState JSON lacks `wake_at` → KeyError on resume | medium | I1 uses `ns.get("wake_at")` default None + test for missing-key load |
| Real-sleep timing assertions flaky under CI jitter | medium | All R5 tests use bounded inequalities with generous tolerance, durations ≤ 0.1s |
| Timezone-naive `wake_at` produces wrong remaining sleep | low | Standardise on `datetime.now(timezone.utc)` + `.isoformat()` write and `fromisoformat()` read on both sides |

## Assumptions

- `NodeState` is the correct carrier for `wake_at` (per-node, not run-level), confirmed by the analysis report's assumption and the existing per-node `nodes_executed` keying.
- `await_timed_wait` keeps a defensive full-duration fallback when `wake_at` is None, so the function remains correct even if a caller forgets to pass it; the executor (I3) is the sole production caller and always passes it.
- `_maybe_save` is the existing executor helper for persisting RunState; the pre-sleep save reuses it (no new persistence primitive needed).
- The implementor will use `datetime.datetime.fromisoformat()` to parse the stored string; Python 3.12 (per CLAUDE.md) parses ISO-8601 with offset natively.

## Open questions

- None.

## Next consumer brief

Read `iterations[]`, each iteration's `scope_files`, and `validation_command` —
these are the hard boundaries and the exact tester commands. Critical
cross-iteration invariant NOT derivable from the YAML: the `wake_at` value is an
**ISO-8601 UTC string with explicit offset** (`datetime.now(timezone.utc).isoformat()`);
I2 (`await_timed_wait` reader) and I3 (executor writer) MUST use the same
representation and parse with `datetime.fromisoformat()`. I3's most important
detail: read the prior `state.nodes_executed.get(node_id)` and reuse its
`wake_at` if set BEFORE assigning a fresh `NodeState`, otherwise the resume case
re-sleeps the full duration (see the high-severity risk). Persist via `_maybe_save`
BEFORE the await. I2 sleeps `max(0.0, wake_at - now)`; full duration only when
`wake_at` is None. No new files; no frontend work.
