---
cc_version: "1.0"
agent: pipeline-implementor
slug: memory-bug-fixing--i2
phase: impl
status: done
confidence: 0.95
inputs_used:
  - .cronos/pipeline/memory-bug-fixing/design-report-memory-bug-fixing.md
  - .cronos/pipeline/memory-bug-fixing/impl-report-memory-bug-fixing--i1.md
  - backend/app/memory_store.py
  - backend/tests/test_memory_store.py
  - backend/app/memory_lifecycle.py
iteration_id: I2
files_changed:
  - backend/app/memory_store.py
  - backend/tests/test_memory_store.py
validation_command_passed: true
out_of_scope_findings:
  - description: "The design report assumed `decay` was already imported in memory_store.py (line: 'The decay symbol is already imported'), but it was not — only boost, should_auto_confirm, should_prune were imported. The missing import was added as part of I2's scope."
    location: "backend/app/memory_store.py:12"
    severity: low
outputs_produced:
  - .cronos/pipeline/memory-bug-fixing/impl-report-memory-bug-fixing--i2.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 14
  files_read: 5
  memory_hits: 0
  diff_lines_added: 54
  diff_lines_removed: 2
---

## Summary

I2 wires `decay()` into `MemoryStore.get()` so that scores are decayed before being boosted on each access. The fix required adding `decay` to the import line in `memory_store.py` (the design assumed it was already imported, but it was not) and inserting `decayed_score = decay(item.score, item.last_used_at, now)` before the existing `boost(decayed_score, ...)` call. Two new tests were added: `test_get_applies_decay_then_boost` (R5) verifies that a 30-day-old item's score reflects decay-then-boost rather than boost-alone, and `test_get_decay_same_day_preserves_score` (R2) confirms that a freshly-created item's score is approximately `original + BOOST_AMOUNT`. All 37 tests pass with exit code 0.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| backend/app/memory_store.py | modified | +3 / -2 | Add `decay` to import; insert `decayed_score = decay(...)` before `boost()` call in `get()` |
| backend/tests/test_memory_store.py | modified | +51 / 0 | Add R5 test (decay-then-boost) and R2 test (same-day preserves score) |

## Out-of-scope findings

- The design report stated "The `decay` symbol is already imported" at line 12 of `memory_store.py`, but the actual import only included `boost`, `should_auto_confirm`, `should_prune`. Adding `decay` to the import was a necessary intra-scope fix (memory_store.py is in scope_files). Noted for accuracy — the design assumption was incorrect but correctable within scope.

## Assumptions

- `decay` import addition is within scope since `backend/app/memory_store.py` is listed in `scope_files`.
- The R5 test uses `loaded.last_used_at` as the `now` reference for computing `expected_decayed`, because `get()` sets `last_used_at = now` on the returned boosted item. This ensures the test does not have timing sensitivity.
- R2 test uses `rel=1e-4` tolerance (rather than exact equality) to accommodate the microseconds elapsed between item creation and `get()` call.
- Scope files read before editing: all listed individually in `inputs_used[]`.

## Open questions

- None.

## Next consumer brief

Rerun validation with: `cd /data/spaces/cronos-development/backend && pytest tests/test_memory_store.py -v --override-ini="addopts="`

All 37 tests pass (exit 0). Key implementation detail for the test agent: the R5 test (`test_get_applies_decay_then_boost`) uses `loaded.last_used_at` as `now` when computing the expected score rather than capturing `datetime.now()` independently — this avoids a timing race and is the correct approach. The R2 same-day test uses a looser `rel=1e-4` tolerance. One design-doc inaccuracy: `decay` was not pre-imported in `memory_store.py` as the design assumed; the import was added as part of this iteration (within scope). I3 (agent.py `build_prompt` full-body fix) and I4 (prune regression test) are independent and can be picked up in either order.
