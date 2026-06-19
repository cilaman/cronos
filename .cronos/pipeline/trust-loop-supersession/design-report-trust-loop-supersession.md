---
cc_version: '1.0'
agent: pipeline-architect
slug: trust-loop-supersession
phase: design
status: done
confidence: 0.85
inputs_used:
- memory:project-memory-system
- memory:project-memory-lifecycle
- memory:project-architecture
- memory:project-pipeline-foundation
- .cronos/pipeline/trust-loop-supersession/analysis-report-trust-loop-supersession.md
- .cronos/pipeline/trust-loop-supersession/scout-report-trust-loop-supersession.md
- backend/app/trace_parser.py
- backend/app/memory_store.py
- backend/app/memory_retrieval.py
- backend/app/worker.py
outputs_produced:
- .cronos/pipeline/trust-loop-supersession/design-report-trust-loop-supersession.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - backend/app/trace_parser.py
  - backend/app/memory_store.py
  - backend/app/memory_retrieval.py
  - backend/app/worker.py
  excluded:
  - frontend/: backend-only feature, has_ui=false in analysis
  - deploy/: no deployment surface for confidence nudging
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
iterations:
- id: I1
  type: backend
  scope_files:
  - backend/app/trace_parser.py
  validation_command: cd backend && pytest tests/test_memory_trust_loop.py::test_memory_used_no_extension
    -v --override-ini="addopts="
  max_diff_lines: 60
  depends_on: []
- id: I2
  type: backend
  scope_files:
  - backend/app/memory_store.py
  validation_command: cd backend && pytest tests/test_memory_trust_loop.py::test_nudge_confidence_up
    tests/test_memory_trust_loop.py::test_nudge_confidence_down tests/test_memory_trust_loop.py::test_nudge_confidence_missing
    tests/test_memory_trust_loop.py::test_nudge_confidence_persisted_for_retrieval
    -v --override-ini="addopts="
  max_diff_lines: 120
  depends_on: []
- id: I3
  type: backend
  scope_files:
  - backend/app/worker.py
  validation_command: cd backend && pytest tests/test_memory_trust_loop.py::test_worker_done_nudges_up
    tests/test_memory_trust_loop.py::test_worker_blocked_nudges_down tests/test_memory_trust_loop.py::test_worker_done_empty_memory_used
    tests/test_memory_trust_loop.py::test_worker_done_nudge_failure_non_blocking -v
    --override-ini="addopts="
  max_diff_lines: 180
  depends_on:
  - I1
  - I2
- id: I4
  type: backend
  scope_files:
  - backend/tests/test_memory_trust_loop.py
  validation_command: cd backend && pytest tests/test_memory_trust_loop.py -v --override-ini="addopts="
  max_diff_lines: 400
  depends_on:
  - I1
  - I2
  - I3
risks:
- description: Changing _memory_slug() to strip the .md extension may break existing
    trace-parser or worker tests that assert memory_used entries still contain .md.
    Sibling fixtures in test_pipeline_state_writer.py pass raw .md-suffixed strings
    directly (not via _memory_slug), so they are safe, but a hidden assertion elsewhere
    could regress.
  severity: medium
  mitigation: Before the I1 diff lands, the implementor must grep backend/tests for
    the string '.md' in proximity to 'memory_used' (rg 'memory_used.*\.md|\.md.*memory_used'
    backend/tests/) and rerun the full backend test suite without -k narrowing as
    the final validation on I4. The new test_memory_used_no_extension test in I4 explicitly
    pins the bare-slug contract going forward.
- description: The trace-computation guard at worker.py:1113 (`if self.trace_store
    is not None or bool(memory_injected) or self.stats_store is not None`) leaves
    computed_trace == None when none of those signals is active. The trust-loop nudge
    hook depends on computed_trace.memory_used, so without widening the condition
    the hook will silently skip in production scenarios where stats_store and trace_store
    are unconfigured but memory_store is.
  severity: high
  mitigation: 'I3 widens the guard to include `or self.memory_store is not None` so
    the trace is always computed when memory was retrievable. I3 also keeps the nudge
    block defensive: if computed_trace is still None for any reason, log at debug
    and skip without raising. The I3 test test_worker_done_nudges_up exercises a worker
    fixture with only memory_store wired (no trace/stats) to pin this behaviour.'
- description: MemoryStore.update() raises MemoryNotFound when the item file is absent.
    R1 mandates that nudge_confidence returns None instead of raising. A naive implementation
    that just delegates to update() will leak the exception to the worker.
  severity: medium
  mitigation: 'I2 implements nudge_confidence as a two-step: first MemoryStore.get(scope,
    id); if None, return None; otherwise compute clamped confidence and call update()
    inside a try/except MemoryNotFound that returns None on race. The test_nudge_confidence_missing
    case in I4 pins this behaviour for a fully-missing item; the implementor should
    also add an inline comment noting the race window.'
- description: Get() in MemoryStore mutates score/ref_count/last_used_at on every
    read. Calling get() inside nudge_confidence just to check existence would silently
    boost the item and could push it past CONFIRM_MIN_USES, mutating user-visible
    confirmed state.
  severity: medium
  mitigation: I2's nudge_confidence must use a non-mutating existence check — open
    self._item_path(scope, item_id).exists() under self._lock — rather than calling
    get(). The I4 test test_nudge_confidence_no_side_effects pins that ref_count and
    confirmed are unchanged after a nudge.
- description: The post-DONE hook block in _finalize is long (worker.py:1029–1102
    plus subsequent trace/stats blocks). Inserting the nudge hook at the wrong location
    — for example before computed_trace assignment — would access None or stale memory_used,
    silently no-op'ing the feature.
  severity: low
  mitigation: 'I3''s design places the nudge block strictly between the trace persistence
    (after line 1193) and the MEMORY: block capture (before line 1196). The implementor
    must verify by reading worker.py once before patching that computed_trace is non-None
    at the insertion line, and the I3 acceptance test test_worker_done_nudges_up asserts
    the nudge happens after trace persist by mocking trace_store.save_run and checking
    call order.'
metrics:
  tool_calls: 14
  files_read: 6
  memory_hits: 4
  iterations_planned: 4
---

## Summary

This design wires a trust-loop on top of the existing memory system: completed tasks reinforce the memory items they actually consumed, blocked tasks penalise them. The plan splits cleanly along module boundaries — one prerequisite fix in `trace_parser._memory_slug()` (R2), one new atomic method `MemoryStore.nudge_confidence` (R1, R5), and one post-trace hook in `worker._finalize()` (R3, R4) — with a fourth iteration assembling the new `test_memory_trust_loop.py` covering all paths (R6). The DAG is wide at layer 0 (I1 and I2 are independent), funnels into I3 which depends on both, and ends with I4 as the consolidated test artifact whose validation command exercises every R<N> path. The key cross-iteration invariant the implementor must respect is the trace-condition widening in I3 (`or self.memory_store is not None`) without which the hook silently no-ops — captured as the highest-severity risk.

## Components

### Data

- `MemoryItem.confidence` (existing field on `backend/app/models.py:364`): the float in `[0.0, 1.0]` whose value the trust loop mutates; no schema change.
- Memory item file (`.cronos/memory/items/{id}.md`): the atomic-write target of `nudge_confidence`; no new file format.
- `RunTrace.memory_used` (existing field on `backend/app/trace_parser.py:150`): the list of bare memory IDs the worker iterates; semantic fix only (R2 strips `.md` from list entries).

### Backend

- `trace_parser._memory_slug()`: return bare IDs without `.md` so they round-trip through `MemoryStore.get/update`. One-line regex change plus the helper signature stays identical (R2).
- `MemoryStore.nudge_confidence(scope, memory_id, delta) -> MemoryItem | None`: new atomic method. Existence check via `_item_path(scope, id).exists()` under `self._lock`, then compute `clamped = max(0.0, min(1.0, item.confidence + delta))`, call `self.update(scope, id, confidence=clamped)`, swallow `MemoryNotFound` to return None (R1, R5).
- `worker._finalize()`: new post-trace nudge block placed AFTER the `computed_trace` assignment and trace persist (after current line 1193, before line 1196). Iterates `computed_trace.memory_used`; on `Status.DONE` calls `nudge_confidence(..., +0.05)`, on `Status.BLOCKED` calls `nudge_confidence(..., -0.1)`; tries `space:{task.space_id}` scope first, falls back to `global` when the first returns None; each item wrapped in `try/except` so nudge failures log and continue without aborting the state transition (R3, R4). The condition guarding `computed_trace` computation at line 1113 is widened with `or self.memory_store is not None` so the trace is computed whenever memory was retrievable.

## Implementation plan

| ID  | Type    | Depends on | Scope files (abridged)             | Validation                                                                |
|-----|---------|------------|------------------------------------|---------------------------------------------------------------------------|
| I1  | backend | -          | backend/app/trace_parser.py        | pytest tests/test_memory_trust_loop.py::test_memory_used_no_extension -v  |
| I2  | backend | -          | backend/app/memory_store.py        | pytest tests/test_memory_trust_loop.py::test_nudge_confidence_* -v        |
| I3  | backend | I1, I2     | backend/app/worker.py              | pytest tests/test_memory_trust_loop.py::test_worker_* -v                  |
| I4  | backend | I1, I2, I3 | backend/tests/test_memory_trust_loop.py | pytest tests/test_memory_trust_loop.py -v                            |

## Risks

| Risk                                                                                                | Severity | Mitigation                                                                                                                |
|-----------------------------------------------------------------------------------------------------|----------|---------------------------------------------------------------------------------------------------------------------------|
| `.md` strip may regress existing tests asserting suffixed `memory_used`                             | medium   | Pre-I1 grep of backend/tests; I4 pins bare-slug contract; full backend suite as final gate                                |
| trace-computation guard skips when only memory_store is wired → hook silently no-ops                | high     | I3 widens the guard with `or self.memory_store is not None`; nudge block defensive against None trace                     |
| `MemoryStore.update()` raises `MemoryNotFound`; naive nudge_confidence leaks it                     | medium   | I2 wraps in try/except MemoryNotFound → return None; test_nudge_confidence_missing pins behaviour                          |
| Using `get()` for existence check mutates score/ref_count, can flip `confirmed` flag                | medium   | I2 uses `_item_path(scope, id).exists()` under lock instead of get(); test_nudge_confidence_no_side_effects pins invariant |
| Nudge block inserted before computed_trace assignment would silently no-op                          | low      | I3 places block strictly after line 1193 trace-persist; test asserts call order vs. trace_store.save_run                  |

## Assumptions

- The "rework" path (ACTIVE→BACKLOG) is out of scope per analysis (`## Scope > Deferred`). The trust loop only fires on terminal `Status.DONE` and `Status.BLOCKED` results inside `_finalize`, not on user-initiated state transitions.
- `confidence` clamping uses `max(0.0, min(1.0, current + delta))` rather than `Field` validation; the field validator on `MemoryItem.confidence` is `ge=0.0, le=1.0`, so any non-clamped value would also raise — clamping eagerly inside `nudge_confidence` is the simpler contract.
- Scope fallback is space-first, global-second per analysis Decision Point 3, and is inlined in the worker nudge loop (not exposed as a public helper) — the two-call pattern is local and not reused elsewhere.
- Default deltas (+0.05 / -0.1) are hardcoded constants in `worker.py` for this iteration; the deferred "configurable per task type" item from analysis is explicitly out of scope.
- Error isolation is per-memory-ID: a single failed `nudge_confidence` call must not abort the loop over the remaining IDs nor block the state transition; each failure is logged via `log.exception` with task_id and memory_id context.

## Open questions

- None.

## Next consumer brief

For implementation: read `iterations[]` and `iterations[].scope_files` from the YAML header — those are hard boundaries. Cross-iteration invariants the YAML cannot encode:

1. **I1 ↔ I4 contract**: the regex change in I1 MUST emit bare IDs (no `.md`); the `test_memory_used_no_extension` case in I4 is the binding spec. If you make I1 do something cleverer (e.g. parse out the slug differently), the I4 test text is the source of truth.
2. **I2 ↔ I3 helper contract**: `nudge_confidence` returns `None` when the memory item is absent (never raises), so I3's worker loop relies on `None` to trigger the space→global fallback. Do not change the return contract in I2 without also patching the fallback condition in I3.
3. **I3 trace-guard widening**: the condition at worker.py line 1113 MUST gain `or self.memory_store is not None`. Without this, the hook silently no-ops in deployments where only memory is wired. This is the highest-severity risk in the register.
4. **I3 insertion point**: the nudge block sits strictly AFTER the existing trace-persist block (current line 1193) and BEFORE the MEMORY: block capture (current line 1196). Line numbers will shift once you edit; the semantic anchor is "computed_trace is non-None and has been persisted".

Unresolved: none — all six requirements have concrete iteration coverage and no analyst open questions remain.
