---
cc_version: "1.0"
agent: pipeline-implementor
slug: sg3-lift-condition-grammar-to-package--i3
phase: impl
status: done
confidence: 0.97
inputs_used:
  - .cronos/pipeline/sg3-lift-condition-grammar-to-package/design-report-sg3-lift-condition-grammar-to-package.md
  - backend/app/harnesses/decision.py
  - packages/delivery-workflow/lib/conditions.py
  - backend/tests/test_harness_decision.py
iteration_id: I3
files_changed:
  - backend/app/harnesses/decision.py
validation_command_passed: true
out_of_scope_findings: []
outputs_produced:
  - .cronos/pipeline/sg3-lift-condition-grammar-to-package/impl-report-sg3-lift-condition-grammar-to-package--i3.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 6
  files_read: 4
  memory_hits: 0
  diff_lines_added: 4
  diff_lines_removed: 113
---

## Summary

Replaced the local condition evaluator in `backend/app/harnesses/decision.py` with a thin shim. Added `from lib.conditions import eval_condition` at the module top (consistent with `backend/app/pipeline/gate.py:27` which uses `from lib.security import ...`). Deleted `_EVAL_SINGLE_RE`, `_VAR_COND_RE`, `_eval_single_clause`, and the local `eval_condition` body (113 lines removed). Retained `_eval_variable_condition` as the backward-compatible wrapper that delegates to the imported `eval_condition`. All 97 existing `test_harness_decision.py` tests pass unchanged — `edge_matches` at line 186 calls the imported `eval_condition` transparently.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| backend/app/harnesses/decision.py | modified | +4 / -113 | Replaced local evaluator with `from lib.conditions import eval_condition` shim |

## Validation

`pytest backend/tests/test_harness_decision.py -v` — 97 passed.

## Out-of-scope findings

- None.

## Assumptions

- `from lib.conditions import eval_condition` at the module top works because the editable install puts `packages/delivery-workflow` on sys.path (confirmed by existing `from lib.security import ...` at `backend/app/pipeline/gate.py:27`).
- No other module imports `_eval_single_clause`, `_EVAL_SINGLE_RE`, or `_VAR_COND_RE` directly from `decision.py` (verified by the scout report).
- `_eval_variable_condition` backward-compat wrapper is preserved and delegates to the imported `eval_condition`.

## Open questions

- None.

## Next consumer brief

The shim preserves the full public API of `app.harnesses.decision` — `eval_condition`, `edge_matches`, `evaluate_decision`, `resolve_signal` are all present. The 97 existing tests in `test_harness_decision.py` pass without modification.
