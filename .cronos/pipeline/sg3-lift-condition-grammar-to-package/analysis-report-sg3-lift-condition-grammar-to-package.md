---
cc_version: '1.0'
agent: pipeline-analyst
slug: sg3-lift-condition-grammar-to-package
phase: analysis
status: done
confidence: 0.92
inputs_used:
- .cronos/pipeline/sg3-lift-condition-grammar-to-package/scout-report-sg3-lift-condition-grammar-to-package.md
- backend/app/harnesses/decision.py
- packages/delivery-workflow/delivery.workflow.yaml
- packages/delivery-workflow/adapters/cronos/adapter.py
outputs_produced:
- .cronos/pipeline/sg3-lift-condition-grammar-to-package/analysis-report-sg3-lift-condition-grammar-to-package.md
blockers: []
next_consumer: design
request: 'Spec 3 — Lift the condition grammar to the package


  The condition evaluator `eval_condition` lives in `backend/app/harnesses/decision.py`
  (Cronos-coupled). The workflow''s `when` edges depend on it. But `_eval_single_clause`
  (decision.py:303) is PURE — `(clause, scope) -> bool`, no app imports (verified).


  Current grammar supports: `==`, `!=`, `in`, `&&` — NO `||` (forces duplicate edges
  in delivery.workflow.yaml).


  ### Action

  1. Lift pure evaluator (`_eval_single_clause` + `&&` splitter) to `packages/delivery-workflow/lib/conditions.py`

  2. Add `||` operator there

  3. Collapse duplicate delivery workflow edges (e.g. two `g-security -> implement`
  edges for `code` vs `dependency`) into single `||` edges

  4. Re-export from `app.harnesses.decision` via a shim so visual-harness tests stay
  green

  5. Runner will call `lib/conditions` directly (keep `evalCondition` as thin ExecutorInterface
  pass-through for backward compat)


  ### References

  - `backend/app/harnesses/decision.py` -- `_eval_single_clause` at line 303, `_eval_single_clause`
  is the pure core

  - `packages/delivery-workflow/` -- the package with enforced `.importlinter` boundary

  - `packages/delivery-workflow/lib/` -- where the new file goes

  - `delivery.workflow.yaml` -- the workflow spec with duplicate edges to collapse


  ### Tests

  Parity tests for all operators: `==`, `!=`, `in`, `&&`, `||`; importlinter check
  (`app` must not be imported in lib); existing visual-harness decision tests stay
  green.'
has_ui: false
coverage_summary:
  searched:
  - backend/app/harnesses/decision.py
  - packages/delivery-workflow/delivery.workflow.yaml
  - packages/delivery-workflow/adapters/cronos/adapter.py
  - packages/delivery-workflow/lib/
  excluded:
  - frontend/: backend-only condition evaluation; no UI surface affected
  - packages/delivery-workflow/runner/: stub-only at this stage; deferred to Phase
      6
  strategies:
  - memory_retrieval
  - read_targeted
  - traceability_mapping
traceability:
- requirement_id: R1
  statement: 'A new module `packages/delivery-workflow/lib/conditions.py` exists containing
    the lifted pure evaluator: `_EVAL_SINGLE_RE` regex, `_eval_single_clause()`, and
    a new `eval_condition()` that supports `==`, `!=`, `in`, `&&`, and `||` operators.'
  acceptance_criteria:
  - Given `packages/delivery-workflow/lib/conditions.py` is present, when `importlinter
    lint` is run, then no `app.*` or `backend.*` imports are flagged in `lib/conditions.py`.
  - The `_EVAL_SINGLE_RE` pattern in `lib/conditions.py` is byte-identical to the
    one in `backend/app/harnesses/decision.py` lines 275-284.
  - '`lib/conditions.py` imports only stdlib modules (`re`, `logging`).'
  verifying_phase: test
  confidence: 0.95
- requirement_id: R2
  statement: 'The `eval_condition()` in `lib/conditions.py` supports the `||` (OR)
    operator using OR-of-ANDs precedence: split on ` || ` at top level, then split
    each sub-expression on ` && `.'
  acceptance_criteria:
  - 'Given `scope = {''a'': ''x''}`, when `eval_condition(''a == x || a == y'', scope)`
    is called, then it returns True.'
  - 'Given `scope = {''a'': ''z''}`, when `eval_condition(''a == x || a == y'', scope)`
    is called, then it returns False.'
  - 'Given `scope = {''a'': ''x'', ''b'': ''1''}`, when `eval_condition(''a == x &&
    b == 1 || a == y && b == 2'', scope)` is called, then it returns True (first AND-group
    matches).'
  - 'Given `scope = {''a'': ''y'', ''b'': ''2''}`, when `eval_condition(''a == x &&
    b == 1 || a == y && b == 2'', scope)` is called, then it returns True (second
    AND-group matches).'
  - Parentheses-aware parsing is NOT required; that is a v2 follow-up.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R3
  statement: '`backend/app/harnesses/decision.py` retains `eval_condition()` as a
    thin shim that delegates to `lib.conditions.eval_condition`, preserving the public
    signature `(condition: str, scope: dict[str, str]) -> bool`.'
  acceptance_criteria:
  - Given any existing test importing `from app.harnesses.decision import eval_condition`,
    when the test suite is run after migration, then all tests pass without modification.
  - 'The shim body is at most 5 lines: an import of `lib.conditions.eval_condition`
    and a delegation call.'
  - '`_eval_single_clause` in `decision.py` is either removed (delegated to lib) or
    kept as a wrapper; it MUST NOT duplicate logic divergently from `lib/conditions.py`.'
  verifying_phase: test
  confidence: 0.9
- requirement_id: R4
  statement: All 79 existing tests in `backend/tests/test_harness_decision.py` pass
    without modification after the migration.
  acceptance_criteria:
  - Given the shim is in place, when `pytest backend/tests/test_harness_decision.py
    -v` is run, then all 79 tests pass.
  - No test file in `backend/tests/` is modified as part of this migration.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R5
  statement: Parity tests for all five operators (`==`, `!=`, `in`, `&&`, `||`) are
    added as a new test file in `packages/delivery-workflow/tests/` that imports exclusively
    from `lib.conditions`.
  acceptance_criteria:
  - A new test file `packages/delivery-workflow/tests/test_conditions.py` (or equivalent)
    covers at least one positive and one negative case each for `==`, `!=`, `in`,
    `&&`, `||`; a multi-clause `&&` test; a mixed `&&` and `||` test; and an empty/invalid
    clause returning False.
  - All new tests pass when run via `pytest packages/delivery-workflow/tests/test_conditions.py
    -v`.
  - The test file imports `from lib.conditions import eval_condition` and does NOT
    import `app.harnesses.decision`.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R6
  statement: The two duplicate edges from `g-security` to `implement` in `packages/delivery-workflow/delivery.workflow.yaml`
    (lines 211-212) are collapsed into a single edge.
  acceptance_criteria:
  - 'After the change, `delivery.workflow.yaml` contains exactly one edge with `from:
    g-security` and `to: implement` bearing a condition that fires when `finding_class`
    is `code` OR `dependency` (using `in` operator or `||` operator).'
  - 'The collapsed edge is functionally equivalent to both originals: routing fires
    for `finding_class == ''code''` and for `finding_class == ''dependency''`.'
  - YAML syntax remains valid (parseable via `yaml.safe_load`).
  verifying_phase: test
  confidence: 0.92
- requirement_id: R7
  statement: 'The `importlinter` boundary check passes after migration: `lib/conditions.py`
    contains no imports from `app.*` or `backend.*`.'
  acceptance_criteria:
  - Running `importlinter lint` (or equivalent) from the `packages/delivery-workflow/`
    directory exits with code 0.
  - A test or CI assertion confirms the boundary holds as part of the delivery-workflow
    test suite.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R8
  statement: The adapter's `evalCondition` method in `packages/delivery-workflow/adapters/cronos/adapter.py`
    is updated to import from `lib.conditions` directly, eliminating the coupling
    to `app.harnesses.decision`.
  acceptance_criteria:
  - After the change, `adapter.py::evalCondition` imports from `lib.conditions` (or
    equivalent package-relative path) rather than from `app.harnesses.decision`.
  - The six existing adapter condition tests in `backend/tests/test_cronos_adapter_condition.py`
    continue to pass without modification.
  - 'The adapter retains the non-string scope coercion (`{k: str(v) for k, v in scope.items()}`)
    unchanged.'
  verifying_phase: test
  confidence: 0.85
metrics:
  tool_calls: 10
  files_read: 4
  memory_hits: 0
---

## Summary

This feature lifts the pure condition evaluator from `backend/app/harnesses/decision.py` into a portable `packages/delivery-workflow/lib/conditions.py` module, adds `||` (OR) operator support using OR-of-ANDs precedence, collapses two duplicate workflow YAML edges into one, and preserves all existing call sites via a thin backward-compatibility shim. The migration is low-risk: `_eval_single_clause` is verified pure (stdlib-only, no I/O), 79 existing tests cover all operators end-to-end, and the shim strategy keeps visual-harness tests green without any test modifications.

## Scope

### In scope
- Create `packages/delivery-workflow/lib/conditions.py` with lifted `_EVAL_SINGLE_RE`, `_eval_single_clause`, and a new `eval_condition` supporting `==`, `!=`, `in`, `&&`, and `||`
- Implement `||` as top-level OR-of-ANDs (split on ` || ` first, then ` && ` within each group)
- Add backward-compatibility shim in `backend/app/harnesses/decision.py` so `eval_condition` delegates to `lib.conditions.eval_condition`
- Collapse the two duplicate `g-security -> implement` edges in `delivery.workflow.yaml` into one edge using `in` operator (or `||`)
- Update the adapter's `evalCondition` to import from `lib.conditions` directly
- Add parity tests for all five operators in `packages/delivery-workflow/tests/`
- Verify `importlinter` boundary holds (no `app.*` in `lib/conditions.py`)

### Out of scope
- Parentheses-aware condition parsing (e.g. `(a || b) && c`) -- deferred to v2
- Lifting `evaluate_decision()`, `edge_matches()`, or `resolve_signal()` from `decision.py` -- those are Cronos-specific and remain in `app.harnesses.decision`
- Modifying `backend/tests/test_harness_decision.py` -- shim must keep them green as-is
- Changes to the runner (stub-only; deferred to Phase 6 per scout findings)
- UI changes of any kind

### Deferred
- Full parentheses-aware tokenizer for complex boolean expressions (e.g. `(a || b) && c`) -- document as v2 follow-up in `lib/conditions.py` docstring
- Additional `g-review` edge consolidation (three edges exist but have different targets; not true duplicates)
- Auto-migration of other consumers calling `app.harnesses.decision.eval_condition` beyond the adapter

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | Create `lib/conditions.py` with lifted pure evaluator (stdlib-only, no app imports) |
| R2 | Add `||` operator with OR-of-ANDs precedence in `lib/conditions.py` |
| R3 | Shim `eval_condition` in `decision.py` to delegate to `lib.conditions` |
| R4 | All 79 existing `test_harness_decision.py` tests pass without modification |
| R5 | Add parity tests for all five operators in `packages/delivery-workflow/tests/` |
| R6 | Collapse duplicate `g-security -> implement` edges in `delivery.workflow.yaml` |
| R7 | `importlinter` boundary check passes: `lib/conditions.py` has no `app.*` imports |
| R8 | Update adapter `evalCondition` to import from `lib.conditions` directly |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). The body summary below mirrors them in compact form for the human reader.

- R1 -- `lib/conditions.py` exists, passes importlinter, uses only stdlib, and has byte-identical `_EVAL_SINGLE_RE`
- R2 -- `||` evaluates as OR-of-ANDs; 4 AC cases covered; parentheses deferred to v2
- R3 -- shim is at most 5 lines; all existing imports of `app.harnesses.decision.eval_condition` continue to work unchanged
- R4 -- `pytest backend/tests/test_harness_decision.py` passes all 79 tests; no test file is modified
- R5 -- new `packages/delivery-workflow/tests/test_conditions.py` covers all 5 operators; imports only from `lib.conditions`
- R6 -- single collapsed edge in YAML; semantically equivalent to original two edges; YAML parses cleanly
- R7 -- `importlinter lint` exits 0 from `packages/delivery-workflow/`
- R8 -- adapter imports from `lib.conditions`; 6 adapter condition tests pass unchanged

## Traceability

The full requirement -> acceptance criteria -> verifying_phase map is the YAML `traceability[]` array. Downstream agents read the YAML directly; this section exists so a human reader sees the same routing table without parsing YAML.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | `lib/conditions.py` created with lifted pure evaluator; no app imports; stdlib-only |
| R2 | test | `||` operator added with OR-of-ANDs precedence; 4+ test cases required |
| R3 | test | Shim in `decision.py` delegates to `lib.conditions`; max 5 lines; existing imports unbroken |
| R4 | test | All 79 existing `test_harness_decision.py` tests pass without modification |
| R5 | test | New parity test file in `packages/delivery-workflow/tests/` covers all 5 operators |
| R6 | test | Duplicate `g-security -> implement` edges collapsed to single edge; YAML valid |
| R7 | test | `importlinter lint` passes; boundary holds in CI |
| R8 | test | Adapter imports from `lib.conditions`; adapter tests pass unchanged |

## Assumptions

- `_eval_single_clause()` purity is confirmed: scout verified stdlib-only imports (`re`, `logging`) at lines 303-343 of `decision.py`; lifting the exact function body is safe.
- has_ui=false rationale: the request and scout findings are entirely backend/package-level; no frontend components, API endpoints, or visual state are involved.
- OR-of-ANDs precedence (`||` lower than `&&`) is the correct choice: this matches C/Python precedence, is the only precedence model needed for the `delivery.workflow.yaml` collapse case, and aligns with the scout's recommendation.
- The collapsed duplicate edge will use the `in` operator (`security.fields.finding_class in code,dependency`) as the preferred form; using `||` is also acceptable and the implementor may choose either.
- The adapter update (R8) is IN scope for this iteration per the request's Action item 5.
- The shim in `backend/app/harnesses/decision.py` may use either a top-level or lazy import of `lib.conditions`; implementor may choose whichever avoids import-time circularity.
- No changes to `_VAR_COND_RE` (legacy regex, kept for backward-compat reference) are required.
- Memory context was scanned; zero relevant prior memory entries were found for this scope (condition grammar lift is new work with no prior memory entries).

## Open questions

- None.

## Next consumer brief

Design agent: read `traceability[]` for the full 8-requirement list, `has_ui=false` (backend and package only), and `## Scope` for explicit in/out-of-scope boundaries.

Critical path for the implementation DAG: R1 (create `lib/conditions.py`) is the root dependency; R2, R3, R5, R7, and R8 all depend on it. R2 (`||` operator) gates R5 (parity tests must cover `||`). R3 (shim) and R8 (adapter) can be parallelized after R1; both gate R4. R6 (`delivery.workflow.yaml` collapse) is an independent file edit that can be parallelized using `in` operator to avoid a runtime dependency on `||` being wired. R7 (`importlinter`) is a verification step, not a code change; treat as part of R1 acceptance.

Risk areas for design: the Python import path for `lib.conditions` from `backend/` code (shim) depends on how `packages/delivery-workflow` is installed (editable install via pyproject.toml or sys.path); implementor must confirm the import form. The `_EVAL_SINGLE_RE` regex must be a byte-identical copy; reviewer should diff the two copies to confirm no silent behavioral divergence.
