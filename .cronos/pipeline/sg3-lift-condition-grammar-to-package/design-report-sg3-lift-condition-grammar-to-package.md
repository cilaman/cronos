---
cc_version: '1.0'
agent: pipeline-architect
slug: sg3-lift-condition-grammar-to-package
phase: design
status: done
confidence: 0.88
inputs_used:
- .cronos/pipeline/sg3-lift-condition-grammar-to-package/analysis-report-sg3-lift-condition-grammar-to-package.md
- .cronos/pipeline/sg3-lift-condition-grammar-to-package/scout-report-sg3-lift-condition-grammar-to-package.md
- backend/app/harnesses/decision.py
- packages/delivery-workflow/.importlinter
- packages/delivery-workflow/pyproject.toml
- packages/delivery-workflow/tests/test_import_boundary.py
- packages/delivery-workflow/adapters/cronos/adapter.py
- packages/delivery-workflow/delivery.workflow.yaml
- packages/delivery-workflow/lib/
- backend/tests/test_harness_decision.py
outputs_produced:
- .cronos/pipeline/sg3-lift-condition-grammar-to-package/design-report-sg3-lift-condition-grammar-to-package.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - backend/app/harnesses/decision.py
  - packages/delivery-workflow/lib/
  - packages/delivery-workflow/tests/
  - packages/delivery-workflow/adapters/cronos/adapter.py
  - packages/delivery-workflow/delivery.workflow.yaml
  - packages/delivery-workflow/.importlinter
  - packages/delivery-workflow/pyproject.toml
  excluded:
  - frontend/: backend-only condition evaluator; has_ui=false
  - packages/delivery-workflow/runner/: stub-only; deferred per scout findings
  - 'backend/tests/test_harness_decision.py: read-only reference; the shim must keep
    it passing without modification (R4)'
  strategies:
  - memory_retrieval
  - read_targeted
iterations:
- id: I1
  type: data
  scope_files:
  - packages/delivery-workflow/lib/conditions.py
  validation_command: cd packages/delivery-workflow && pytest tests/test_import_boundary.py
    -v
  max_diff_lines: 200
  depends_on: []
- id: I2
  type: backend
  scope_files:
  - packages/delivery-workflow/tests/test_conditions.py
  validation_command: cd packages/delivery-workflow && pytest tests/test_conditions.py
    -v
  max_diff_lines: 250
  depends_on:
  - I1
- id: I3
  type: backend
  scope_files:
  - backend/app/harnesses/decision.py
  validation_command: pytest backend/tests/test_harness_decision.py -v
  max_diff_lines: 80
  depends_on:
  - I1
- id: I4
  type: backend
  scope_files:
  - packages/delivery-workflow/adapters/cronos/adapter.py
  validation_command: pytest backend/tests/test_cronos_adapter_condition.py -v
  max_diff_lines: 30
  depends_on:
  - I1
- id: I5
  type: data
  scope_files:
  - packages/delivery-workflow/delivery.workflow.yaml
  validation_command: pytest backend/tests/test_harness_routing_delivery.py -v
  max_diff_lines: 20
  depends_on: []
risks:
- description: _EVAL_SINGLE_RE regex copied non-verbatim into lib/conditions.py would
    silently diverge from the canonical pattern at decision.py lines 275-284, causing
    latent behavioural drift between the shim and the package.
  severity: high
  mitigation: Implementor MUST copy the regex string by reading decision.py lines
    275-284 directly and pasting into lib/conditions.py with zero whitespace/escape
    edits; reviewer MUST diff the two literals byte-by-byte during review.
- description: Adding `||` support by splitting on ` || ` could mis-tokenise a literal
    `||` inside a quoted string in some future condition, mirroring the documented
    `&&` V1 limitation.
  severity: low
  mitigation: Document the limitation in lib/conditions.py docstring identically to
    the existing `&&` note (decision.py lines 361-364); defer the quoting-aware tokeniser
    to v2 explicitly in the docstring.
- description: The shim in decision.py may introduce an import-time circularity if
    lib.conditions is imported at module top of decision.py while some test fixture
    imports decision.py before sys.path includes packages/delivery-workflow.
  severity: medium
  mitigation: Use a top-level `from lib.conditions import eval_condition` import (the
    editable install puts packages/delivery-workflow on sys.path; backend/app/pipeline/gate.py
    already uses `from lib.security import ...` successfully). If CI surfaces an import-order
    failure, fall back to a lazy import inside the shim body.
- description: Collapsing the two g-security → implement edges with the `in` operator
    changes only the right-hand value list semantics, but a typo (e.g. `code, dependency`
    with a literal space or quoting) would break routing silently — `eval_condition`
    returns False on unmatched grammar.
  severity: medium
  mitigation: Use the exact form `security.fields.finding_class in code,dependency`
    (comma-separated, no spaces in the literal list per the `in` grammar at decision.py
    line 338 which strips whitespace per item). Validate by running test_harness_routing_delivery.py
    against the edited YAML in I5 — that test exercises the full routing path with
    `eval_condition`.
- description: I3 (shim) and I4 (adapter import swap) might race on PR-merge order
    if the adapter swap lands before the shim and a stale test caches `app.harnesses.decision.eval_condition`
    at module scope; in practice both depend on I1 so should land atomically but the
    orchestrator runs them in parallel.
  severity: low
  mitigation: 'Both I3 and I4 declare `depends_on: [I1]` and run in the same layer;
    either ordering within that layer is safe because (a) I3''s shim preserves the
    legacy import path verbatim and (b) I4''s adapter swap imports from lib.conditions
    which I1 has already shipped. No test imports both paths simultaneously.'
- description: test_import_boundary.py auto-scans every .py file under packages/delivery-workflow/
    (except tests/ and adapters/cronos/), so any forbidden import line accidentally
    introduced into lib/conditions.py would surface only at I1's validation — but
    a violation caught here would correctly fail I1 before downstream iterations run.
  severity: low
  mitigation: lib/conditions.py imports only `re` and `logging` per R1 AC; implementor
    MUST NOT add convenience imports from app.*, backend.*, or other lib siblings
    beyond stdlib. This risk is self-mitigating by virtue of I1's validation command
    exercising the boundary check.
metrics:
  tool_calls: 11
  files_read: 9
  memory_hits: 1
  iterations_planned: 5
---

## Summary

Lift the pure condition evaluator (`_EVAL_SINGLE_RE` + `_eval_single_clause`) from `backend/app/harnesses/decision.py` to `packages/delivery-workflow/lib/conditions.py`, extend the public `eval_condition` with a `||` (OR) operator using OR-of-ANDs precedence, replace the legacy implementation in `decision.py` with a thin shim, swap the adapter to import from `lib.conditions` directly, and collapse the duplicate `g-security → implement` edges in `delivery.workflow.yaml`. The DAG is wide and shallow (3 layer-0 iterations and 4 layer-1 iterations after I1; effectively layer 0 = {I1, I5}, layer 1 = {I2, I3, I4}), so the orchestrator can parallelise I3/I4 once I1 has shipped. The principal load-bearing invariant is that `_EVAL_SINGLE_RE` is copied byte-identically — that is captured as a high-severity risk with reviewer-side diff mitigation.

## Components

### Data
- `packages/delivery-workflow/lib/conditions.py` (new): pure evaluator module. Contains `_EVAL_SINGLE_RE` (byte-identical to decision.py:275-284), `_eval_single_clause(clause, scope) -> bool` (byte-identical body from decision.py:303-343), and a new top-level `eval_condition(condition, scope) -> bool` that splits on ` || ` first, then ` && ` within each OR-group (OR-of-ANDs precedence; no parens; parens-aware tokeniser deferred to v2). Stdlib-only imports (`re`, `logging`).
- `packages/delivery-workflow/delivery.workflow.yaml` (modified): single edit at lines 211-212 — collapse the two `g-security → implement` edges into one edge using the `in` operator (`security.fields.finding_class in code,dependency`). Existing `in` semantics handle this without runtime dependency on `||` shipping.

### Backend
- `backend/app/harnesses/decision.py` (modified): replace the body of `eval_condition` (lines 346-379) with a thin delegating shim that calls `lib.conditions.eval_condition`. Public signature `(condition: str, scope: dict[str, str]) -> bool` is preserved. `_eval_single_clause` (lines 303-343) MUST either be deleted (preferred) or rewritten to delegate to `lib.conditions._eval_single_clause` — it MUST NOT carry a divergent copy. `_EVAL_SINGLE_RE` and `_VAR_COND_RE` may be removed from decision.py if no other module imports them (scout confirmed none do); if retained for API surface continuity, they MUST be re-exported from `lib.conditions`, not redefined. `_eval_variable_condition` (legacy wrapper at lines 382-388) delegates via the public `eval_condition` so it continues to work.
- `packages/delivery-workflow/adapters/cronos/adapter.py` (modified, lines ~391-401): change the lazy import in `evalCondition` from `from app.harnesses.decision import eval_condition` to `from lib.conditions import eval_condition`. Preserve the scope coercion `flat: dict[str, str] = {k: str(v) for k, v in scope.items()}` verbatim per R8 AC3. The other public methods of adapter.py are untouched.

### Tests
- `packages/delivery-workflow/tests/test_conditions.py` (new): parity tests covering all 5 operators (`==`, `!=`, `in`, `&&`, `||`). MUST import `from lib.conditions import eval_condition` only — no `app.harnesses.decision` import (R5 AC3). Required cases: positive + negative for each operator (10 minimum), one multi-clause `&&`, one mixed `&&`+`||`, one empty-string returns False, one unsupported-operator clause returns False. The new file lives under `tests/`, which `test_import_boundary.py` excludes from its boundary scan (line 32-33), so the new test file does not need to be portable.

## Implementation plan

| ID | Type    | Depends on | Scope files (abridged)                                              | Validation                                                              |
|----|---------|------------|----------------------------------------------------------------------|-------------------------------------------------------------------------|
| I1 | data    | -          | packages/delivery-workflow/lib/conditions.py                         | cd packages/delivery-workflow && pytest tests/test_import_boundary.py -v |
| I2 | backend | I1         | packages/delivery-workflow/tests/test_conditions.py                  | cd packages/delivery-workflow && pytest tests/test_conditions.py -v      |
| I3 | backend | I1         | backend/app/harnesses/decision.py                                    | pytest backend/tests/test_harness_decision.py -v                         |
| I4 | backend | I1         | packages/delivery-workflow/adapters/cronos/adapter.py                | pytest backend/tests/test_cronos_adapter_condition.py -v                 |
| I5 | data    | -          | packages/delivery-workflow/delivery.workflow.yaml                    | pytest backend/tests/test_harness_routing_delivery.py -v                 |

Topology: layer 0 = {I1, I5} (parallel); layer 1 = {I2, I3, I4} (parallel, all depend on I1). Five iterations total; well under the 12-cap. R6 (I5) runs parallel to I1 per analyst guidance — collapsing the YAML with the existing `in` operator does not require the new `||` operator to be wired first.

Requirement → iteration coverage map (all 8 covered; R7 is verification folded into I1's validation as analyst directed):

| Requirement | Covered by iteration(s) | How |
|-------------|-------------------------|-----|
| R1 (lib/conditions.py exists, byte-identical regex, stdlib-only)         | I1       | File created with verbatim regex + clause logic |
| R2 (`||` operator with OR-of-ANDs precedence)                            | I1, I2   | I1 implements; I2 verifies the 4 AC cases     |
| R3 (decision.py shim delegates, max ~5-line body)                        | I3       | Shim body replaces existing eval_condition    |
| R4 (all 79 existing test_harness_decision.py tests pass unchanged)       | I3       | Validation command runs the full file         |
| R5 (parity tests at packages/delivery-workflow/tests/test_conditions.py) | I2       | New test file with 5-operator coverage         |
| R6 (collapse duplicate g-security → implement edges)                     | I5       | Single edit at lines 211-212                  |
| R7 (importlinter boundary holds)                                         | I1       | I1's validation runs test_import_boundary.py  |
| R8 (adapter imports from lib.conditions)                                 | I4       | One-line import swap; coercion preserved      |

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Non-verbatim `_EVAL_SINGLE_RE` copy → silent grammar drift | high   | Read decision.py:275-284 and paste exactly; reviewer diffs the two literals during review |
| `||` mis-tokenises a literal `||` inside a quoted string  | low    | Document the limitation in lib/conditions.py docstring identically to existing `&&` note; defer parens-aware tokeniser to v2 |
| Import-time circularity if shim top-imports `lib.conditions` before sys.path is ready | medium | Use `from lib.conditions import eval_condition` (precedent: backend/app/pipeline/gate.py uses `from lib.security import ...`); fall back to lazy import inside shim body if CI surfaces an issue |
| YAML edge collapse typo silently breaks routing (`in` returns False on grammar miss) | medium | Use exact form `security.fields.finding_class in code,dependency`; validate via `test_harness_routing_delivery.py` which exercises the full routing path through `eval_condition` |
| I3 / I4 parallel race in same layer                       | low    | Both depend on I1; shim and adapter import paths are independent; no test imports both simultaneously |
| Forbidden import slip into `lib/conditions.py`            | low    | I1 validation is the boundary scanner itself (test_import_boundary.py); a slip fails I1 before downstream iterations run |

## Assumptions

- `packages/delivery-workflow` is on sys.path via the editable install used by the backend test environment (`backend/app/pipeline/gate.py:27` already does `from lib.security import evaluate_security as _evaluate_security`, confirming the import form works from backend code).
- The 79 existing tests in `backend/tests/test_harness_decision.py` exercise the public surface of `eval_condition` only; lifting `_eval_single_clause` into `lib.conditions` and deleting the in-place copy is safe (scout verified no other module imports `_eval_single_clause` directly).
- `_EVAL_SINGLE_RE` is the canonical regex; `_VAR_COND_RE` (legacy, decision.py:287-300) is documented "kept for backward compat reference only" and has no live imports — implementor MAY delete it from decision.py but is not required to.
- The `in` operator's existing behaviour (`[v.strip() for v in rhs.split(",")]` at decision.py:338) handles `code,dependency` correctly; this is the chosen collapse form for I5 because it does not require `||` to be wired at runtime (analyst guidance and scout recommendation align).
- Adding `||` support uses OR-of-ANDs precedence (`a && b || c && d` ≡ `(a && b) || (c && d)`); this matches C/Python convention and is sufficient for the delivery.workflow.yaml collapse case. Parens-aware parsing is explicitly out of scope (deferred to v2).
- The new `packages/delivery-workflow/tests/test_conditions.py` may use `from lib.conditions import eval_condition` because `tool.pytest.ini_options.pythonpath = ["."]` in `packages/delivery-workflow/pyproject.toml` puts the package root on sys.path when pytest is invoked from there.
- Memory hit: the project memory entry `project_pipeline_foundation_merged.md` documents that the pipeline foundation (including the `.importlinter` boundary discipline) is merged to main; this confirms `lib/` is the canonical destination for portable workflow code and the boundary check is enforced in CI.

## Open questions

- None.

## Next consumer brief

Implementor agents should read `iterations[]` first — each entry's `scope_files` is a hard diff boundary and `validation_command` is the exact shell line the tester will run. Key cross-iteration invariants NOT derivable from the YAML alone:

1. **`_EVAL_SINGLE_RE` must be byte-identical** between `lib/conditions.py` (I1) and the original at `backend/app/harnesses/decision.py:275-284`. Read the source file, paste the regex literal, do not re-key it. The high-severity risk in `risks[]` is exactly this.
2. **`eval_condition` precedence**: split on ` || ` (space-pipe-pipe-space) FIRST, then split each sub-expression on ` && ` (space-amp-amp-space). Each leaf clause goes through `_eval_single_clause`. Short-circuit on the first AND-group whose clauses all evaluate True.
3. **Shim form for I3**: prefer `from lib.conditions import eval_condition` at module top (precedent: `backend/app/pipeline/gate.py:27` uses `from lib.security import ...`). If circularity surfaces in CI, fall back to a lazy import inside the `eval_condition` body — both forms satisfy R3 AC2 (≤5 lines).
4. **R6 YAML edit (I5) MUST use the `in` operator** (`security.fields.finding_class in code,dependency`) — NOT the new `||` operator. This decouples I5 from I1's runtime semantics and lets I5 run parallel to I1 in layer 0. The `||` operator exists in I1 for future YAML evolution and is exercised by I2's parity tests.
5. **R7 has no dedicated iteration**: the analyst folded the importlinter boundary check into R1's acceptance; I1's `validation_command` runs `test_import_boundary.py` which AST-scans `lib/conditions.py` for forbidden imports. A separate `lint-imports` CLI invocation is NOT required at this layer.

Open question for the implementor: none. All routing decisions (shim placement, adapter import form, YAML collapse operator) are pinned above.
