Spec 3 — Lift the condition grammar to the package

The condition evaluator `eval_condition` lives in `backend/app/harnesses/decision.py` (Cronos-coupled). The workflow's `when` edges depend on it. But `_eval_single_clause` (decision.py:303) is PURE — `(clause, scope) -> bool`, no app imports (verified).

Current grammar supports: `==`, `!=`, `in`, `&&` — NO `||` (forces duplicate edges in delivery.workflow.yaml).

### Action
1. Lift pure evaluator (`_eval_single_clause` + `&&` splitter) to `packages/delivery-workflow/lib/conditions.py`
2. Add `||` operator there
3. Collapse duplicate delivery workflow edges (e.g. two `g-security → implement` edges for `code` vs `dependency`) into single `||` edges
4. Re-export from `app.harnesses.decision` via a shim so visual-harness tests stay green
5. Runner will call `lib/conditions` directly (keep `evalCondition` as thin ExecutorInterface pass-through for backward compat)

### References
- `backend/app/harnesses/decision.py` — `_eval_single_clause` at line 303, `_eval_single_clause` is the pure core
- `packages/delivery-workflow/` — the package with enforced `.importlinter` boundary
- `packages/delivery-workflow/lib/` — where the new file goes
- `delivery.workflow.yaml` — the workflow spec with duplicate edges to collapse

### Tests
Parity tests for all operators: `==`, `!=`, `in`, `&&`, `||`; importlinter check (`app` must not be imported in lib); existing visual-harness decision tests stay green.

