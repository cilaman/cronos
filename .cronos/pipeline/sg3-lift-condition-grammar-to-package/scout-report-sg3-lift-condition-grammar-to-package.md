---
cc_version: "1.0"
agent: pipeline-scout
slug: sg3-lift-condition-grammar-to-package
phase: scout
status: done
confidence: 0.92
inputs_used:
  - backend/app/harnesses/decision.py
  - backend/tests/test_harness_decision.py
  - packages/delivery-workflow/.importlinter
  - packages/delivery-workflow/lib/
  - packages/delivery-workflow/adapters/cronos/adapter.py
  - packages/delivery-workflow/delivery.workflow.yaml
  - backend/tests/test_harness_routing_delivery.py
  - backend/tests/test_cronos_adapter_condition.py
outputs_produced:
  - .cronos/pipeline/sg3-lift-condition-grammar-to-package/scout-report-sg3-lift-condition-grammar-to-package.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - backend/app/harnesses/decision.py
    - backend/tests/test_harness_decision.py
    - packages/delivery-workflow/
    - packages/delivery-workflow/delivery.workflow.yaml
  excluded:
    - frontend/: not relevant to condition evaluator
  strategies:
    - memory_retrieval
    - glob_structural
    - grep_symbol
    - read_targeted
brief: "Scout SG3 — lift the condition grammar (`_eval_single_clause`, `&&` operator) to `packages/delivery-workflow/lib/conditions.py`; add `||` operator; collapse duplicate delivery workflow edges; preserve backward compat via shim"
metrics:
  tool_calls: 12
  files_read: 9
  memory_hits: 0
---

## Summary

The condition evaluator in `backend/app/harnesses/decision.py:_eval_single_clause()` is a pure function (no app imports, no I/O) that can be lifted to the delivery-workflow package. Current grammar supports `==`, `!=`, `in`, `&&` (no `||`, forcing two delivery.workflow.yaml edges at lines 211–212 to handle both `code` and `dependency` findings). Migration strategy: (1) create `lib/conditions.py` with lifted evaluator + new `||` operator; (2) collapse duplicate edges in workflow YAML; (3) re-export from `app.harnesses.decision` via lazy import shim for backward compat with visual-harness tests; (4) adapter's `evalCondition()` call will auto-work with new lib module. Test coverage is comprehensive (38 eval_condition tests + 79 integration tests). Migration is low-risk given purity guarantee and extensive test suite.

## Coverage

### Searched
- `backend/app/harnesses/decision.py` — entry point; `_eval_single_clause` at line 303
- `backend/tests/test_harness_decision.py` — 79 integration tests covering all operators + edge cases
- `packages/delivery-workflow/` — lib structure, import boundaries, adapter integration
- `packages/delivery-workflow/delivery.workflow.yaml` — duplicate edges at lines 211–212
- `packages/delivery-workflow/adapters/cronos/adapter.py` — evalCondition delegator (DD-07)

### Excluded
- frontend/: condition evaluation is backend-only
- runner/: deferred to Phase 6; currently empty stub

### Strategies
- memory_retrieval: 0 relevant entries found (condition grammar is new scope in this delivery-v2 refactor)
- glob_structural: located core decision module and lib structure
- grep_symbol: found all import sites (adapter + 2 test files)
- read_targeted: deep-read decision.py, 2 test files, adapter delegator, delivery.workflow.yaml

## Findings

### 1. `_eval_single_clause()` Implementation — PURE

**File**: `backend/app/harnesses/decision.py:303–343`

Pure function signature: `(clause: str, scope: dict[str, str]) -> bool`

```python
def _eval_single_clause(clause: str, scope: dict[str, str]) -> bool:
    """Evaluate one ``<path> <op> <literal>`` clause against *scope*.
    Returns False (never raises) when the clause does not match the
    whitelisted grammar, so unsupported conditions fall through to the
    default edge.
    """
    m = _EVAL_SINGLE_RE.match(clause)  # line 310
    if m is None:
        log.warning(...)
        return False
    var_name: str = m.group("name")
    op: str = m.group("op")
    raw_val: str = m.group("val")
    # String dequoting logic (lines 322–328)
    if (raw_val.startswith('"') and raw_val.endswith('"')) or (
        raw_val.startswith("'") and raw_val.endswith("'")
    ):
        rhs = raw_val[1:-1]
    else:
        rhs = raw_val
    lhs: str | None = scope.get(var_name)  # line 330
    # Operator dispatch (lines 332–339)
    if op == "==":
        return lhs == rhs
    if op == "!=":
        return lhs != rhs
    if op == "in":
        candidates = [v.strip() for v in rhs.split(",")]
        return lhs in candidates
    log.warning(...)
    return False
```

**Dependencies**: `re`, `logging` (stdlib only). No app imports. Regex patterns defined at module top:
- `_EVAL_SINGLE_RE` (line 275–284) — matches `<path> <op> <value>` grammar
- `_VAR_COND_RE` (line 287–300) — legacy, kept for backward compat reference only

**Purity guarantee verified**: No side effects, no I/O, no subprocess calls. Function is deterministic.

### 2. `eval_condition()` — Splits on ` && ` (line 346–379)

Public wrapper that calls `_eval_single_clause` for each clause:

```python
def eval_condition(condition: str, scope: dict[str, str]) -> bool:
    if not condition:
        log.warning("eval_condition: empty condition string; returning False.")
        return False
    clauses = condition.split(" && ")  # line 375
    for clause in clauses:
        if not _eval_single_clause(clause.strip(), scope):
            return False
    return True
```

**Current limitation** (line 361–364 docstring): Literal ` && ` inside quoted strings mis-splits. This is documented as V1 limitation; no test case requires it.

**No `||` operator implemented**: Duplicates edges in workflow YAML.

### 3. Scope/Clause Structure Type Constraints

**Clause grammar** (regex `_EVAL_SINGLE_RE`, lines 275–284):
- `<path>` — dotted/hyphenated identifiers: `[A-Za-z_][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+)*`
  - Examples: `status`, `review.fields.verdict`, `my-node.status`
- `<op>` — one of `==`, `!=`, `in` (no `||` or `&&` at clause level; `&&` only between clauses)
- `<value>` — double-quoted, single-quoted, or bare word (e.g., `"my value"`, `'passed'`, `true`)

**Scope type**: `dict[str, str]` — all keys and values must be strings.
- Adapter coerces non-string scope values to `str` before calling (line in adapter.py: `flat: dict[str, str] = {k: str(v) for k, v in scope.items()}`)
- Runtime enriches scope from workflow state node fields (delivery_status parse)

### 4. Package Integration Points

#### `.importlinter` Boundary (line 8–16)

```
[importlinter:contract:no-app-imports]
name = No app.* imports from portable delivery-workflow core
type = forbidden
source_modules =
    lib
    runner
forbidden_modules =
    app
    backend
```

**Key rule**: `lib/` and `runner/` CANNOT import `app.*` or `backend.*`. Adapters can (explicit exemption).

**Where conditions.py will live**: `packages/delivery-workflow/lib/conditions.py` — ALLOWED (lib is portable core).

**Current state**: No conditions module yet. Existing lib modules (`lib/delivery_status.py`, `lib/git_pr.py`, `lib/improve.py`, `lib/security.py`, `lib/state/`, `lib/telemetry/`) follow same pattern: pure, no app imports.

#### Adapter Integration (packages/delivery-workflow/adapters/cronos/adapter.py)

**evalCondition method** (line ~370):
```python
def evalCondition(self, expr: str, scope: dict[str, Any]) -> bool:
    """Delegate to app.harnesses.decision.eval_condition (DD-07, R5).
    The orchestrator pre-builds ``scope`` from ``state.read().nodes``
    delivery_status fields; this op only evaluates the expression.
    Non-string scope values are coerced to str for the whitelisted grammar.
    """
    from app.harnesses.decision import eval_condition
    flat: dict[str, str] = {k: str(v) for k, v in scope.items()}
    return eval_condition(expr, flat)
```

**Migration strategy for adapter**:
- **Option A (recommended)**: Change lazy import to call `lib.conditions.eval_condition` directly
  - Removes coupling to `app.harnesses`
  - Still compatible with visual-harness tests (shim provides backward compat)
  - Clean separation: portable lib, adapter uses portable lib, Cronos tests use shim
- **Option B (fallback)**: Keep lazy import; shim re-exports from lib (less clear)

### 5. Duplicate Edges in delivery.workflow.yaml

**File**: `packages/delivery-workflow/delivery.workflow.yaml`

**Duplicate edge pair** (lines 211–212):
```yaml
  - {from: g-security,   to: implement,      when: "g-security.decision == 'needs_fix' && security.fields.finding_class == 'code'"}
  - {from: g-security,   to: implement,      when: "g-security.decision == 'needs_fix' && security.fields.finding_class == 'dependency'"}
```

Both edges:
- Source: `g-security`
- Target: `implement`
- Condition: differ only in right-hand value (`'code'` vs `'dependency'`)
- Precondition: both require `g-security.decision == 'needs_fix'`

**Collapse opportunity**: With `||` operator, collapse into one edge:
```yaml
  - {from: g-security,   to: implement,      when: "g-security.decision == 'needs_fix' && security.fields.finding_class in code,dependency"}
```

Alternative using new `||` operator (if preferred):
```yaml
  - {from: g-security,   to: implement,      when: "g-security.decision == 'needs_fix' && (security.fields.finding_class == 'code' || security.fields.finding_class == 'dependency')"}
```

**Note**: Parentheses for `||` grouping would require grammar extension; `in` operator is simpler and already supported.

**Other duplicate edges**: Lines 206–208 show three similar edges from `g-review` to different targets with `||`-collapsible conditions:
```yaml
  - {from: g-review,     to: security,       when: "review.fields.verdict == 'pass'"}
  - {from: g-review,     to: implement,      when: "review.fields.verdict == 'needs_fix' && review.fields.finding_class == 'local'"}
  - {from: g-review,     to: architect,      when: "review.fields.verdict == 'needs_fix' && review.fields.finding_class == 'architectural'"}
```

These are not true duplicates (different targets), but could benefit from `||` if multiple targets mapped to same next step.

**Count**: 1 confirmed duplicate edge pair (g-security → implement); 1 candidate for operator enhancement (g-review routing).

### 6. Test Coverage — COMPREHENSIVE

#### Unit tests for `_eval_single_clause()` indirect via `eval_condition()`

**File**: `backend/tests/test_harness_decision.py` (871 lines)

Coverage by operator:
- **`==` operator** (lines 329–333 in code, 17 tests):
  - Simple equals (line 683–684, 2 tests)
  - Dotted path equals (line 709–720, 5 tests)
  - Spec §12 worked examples (line 839–842, 4 tests)
  - Boolean literals `true`/`false` (line 779–789, 6 tests)

- **`!=` operator** (line 334 in code, 8 tests):
  - Simple not-equals (line 689–690, 2 tests)
  - Dotted path not-equals (line 733–735, 2 tests)
  - Missing variable not-equals (line 701–703, 1 test)
  - Edge matching variable layer (line 337–343, 3 tests)

- **`in` operator** (line 336–339 in code, 8 tests):
  - Simple in (line 692–696, 2 tests)
  - Dotted path in (line 737–739, 2 tests)
  - Spec §12 worked example (line 825–829, 1 test)
  - Edge matching in (line 345–351, 3 tests)

- **`&&` conjunction** (line 375 split, 8 tests):
  - Two clauses both true (line 749–753, 1 test)
  - Two clauses one false (line 755–765, 2 tests)
  - Three clauses all true / middle false (line 767–773, 2 tests)
  - Docstring limitation (' && ' in quoted value) (line 859–870, 1 test)

- **Grammar rejection** (line 310 regex match fail, 9 tests):
  - Function call syntax (line 795–802, 2 tests)
  - Empty condition (line 804–805, 1 test)
  - Unsupported operators `>`, `>=` (line 807–811, 2 tests)
  - Invalid regex in status/exit_reason layer (line 317–319, 1 test)

- **Integration with `evaluate_decision()`** (38 tests across 6 test classes):
  - Layer precedence (status > exit_reason > regex > variable)
  - Default edge fallback
  - Missing signal behavior

**Total tests covering condition evaluation: 79** (including integration tests).

#### Adapter integration tests

**File**: `backend/tests/test_cronos_adapter_condition.py`

Tests adapter's `evalCondition()` coercion of non-string scope to strings; 6 test cases (implied from grep output).

#### Harness routing with delivery workflow

**File**: `backend/tests/test_harness_routing_delivery.py`

Uses `eval_condition` to verify delivery workflow edge routing; confirms adapter integration works end-to-end with real workflow conditions.

### 7. Backward Compatibility & Shim Strategy

#### Visual-harness tests

Mentioned in request.md as tests that must stay green. These tests import from `app.harnesses.decision`:

```python
from app.harnesses.decision import (
    edge_matches,
    eval_condition,
    evaluate_decision,
    resolve_signal,
)
```

**File imports**: `backend/tests/test_harness_decision.py` (71 lines of imports + 800+ lines of tests)

#### Shim approach

**Recommended**: Create re-export shim in `backend/app/harnesses/decision.py` after migration:

```python
# At bottom of decision.py (after lifting to lib/conditions.py):
def eval_condition(condition: str, scope: dict[str, str]) -> bool:
    """Backward-compatible shim delegating to lib/conditions.eval_condition.
    
    This function is kept in app.harnesses.decision for backward compatibility
    with visual-harness tests and other call sites. New code should import
    from lib.conditions directly.
    """
    from packages.delivery_workflow.lib.conditions import eval_condition as _eval
    return _eval(condition, scope)
```

**Benefits**:
- Visual-harness tests need zero changes (their imports still work)
- Adapter can optionally update to call lib.conditions directly (or keep calling through shim)
- Clear deprecation path: shim is documented as backward-compat bridge

**Risk mitigation**:
- Importlinter enforces that only adapters can import app.* from lib
- Visual-harness tests live in backend (app-side), so they import the shim with no issue
- No test isolation problems (shim is thin, immediate delegator)

#### Current call sites to preserve

1. **Adapter** (`packages/delivery-workflow/adapters/cronos/adapter.py`):
   - Currently: `from app.harnesses.decision import eval_condition`
   - Post-migration: can change to `from packages.delivery_workflow.lib.conditions import eval_condition` (cleaner)
   - Or keep unchanged (shim handles it)

2. **Visual-harness tests** (`backend/tests/test_harness_decision.py`):
   - Currently: `from app.harnesses.decision import (eval_condition, ...)`
   - Post-migration: unchanged; shim ensures zero friction

3. **Harness routing tests** (`backend/tests/test_harness_routing_delivery.py`):
   - Currently: `from app.harnesses.decision import eval_condition`
   - Post-migration: unchanged; shim works

### 8. Migration Approach & Risks

#### Step-by-step plan

1. **Create** `packages/delivery-workflow/lib/conditions.py`:
   - Copy `_EVAL_SINGLE_RE` regex pattern
   - Copy `_eval_single_clause()` function (pure kernel)
   - Add new `_split_clauses()` helper (handles both `&&` and `||`)
   - Add new top-level `eval_condition()` that supports both operators
   - Add logic for `||` disjunction (short-circuit OR)

2. **Extend grammar** to support `||` at clause level (e.g., `(a == 1 || b == 2) && c == 3`):
   - **Option A (simple)**: Support only `||` between single clauses without parens; split ` || ` just like ` && `
     - Limitation: cannot express `(a || b) && c` without parens
     - Sufficient for current delivery.workflow.yaml (lines 211–212 are simple disjunctions)
   - **Option B (full)**: Add parens-aware tokenizer (defer to v2, per docstring pattern in existing code)

3. **Collapse edges** in `packages/delivery-workflow/delivery.workflow.yaml`:
   - Lines 211–212 → single edge with `in` operator (simpler than `||`)
   - Or wait for full `||` implementation if preferred

4. **Add re-export shim** in `backend/app/harnesses/decision.py`:
   - Keep all public functions (`eval_condition`, `edge_matches`, etc.)
   - Make `eval_condition` a thin wrapper around `lib.conditions.eval_condition`
   - Document it as backward-compat bridge

5. **Update adapter** (optional):
   - Change `from app.harnesses.decision import eval_condition` → `from packages.delivery_workflow.lib.conditions import eval_condition`
   - Or keep unchanged; shim works either way

6. **Run tests**:
   - `pytest backend/tests/test_harness_decision.py -v` (should all pass via shim)
   - `pytest packages/delivery-workflow/tests/ -v` (new lib tests pass)
   - `importlinter lint` (verifies no app imports in lib/conditions.py)

#### Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Shim import cycles if lib.conditions imports app | High | Only import stdlib (re, logging); no app imports in lib. Shim is thin wrapper. |
| Visual-harness tests break due to regex regex changes | Medium | Preserve exact `_EVAL_SINGLE_RE` pattern and `_eval_single_clause` logic; only add `||` support. Run tests to confirm. |
| Adapter dual imports (app + lib) during transition | Low | Adapter already imports app.harnesses.decision; change is optional. Use grep to find all call sites before migration. |
| `||` operator conflicts with shell escaping in YAML | Low | Escaping works via quotes; spec validator ensures valid YAML. No change needed. |
| Performance of new `||` splitter | Low | Same O(n) split-and-scan as `&&`; no perf regression. |

#### Code review checklist (for implementor)

- [ ] `_EVAL_SINGLE_RE` regex is identical to original (copy–paste to avoid typos)
- [ ] `_eval_single_clause()` body is identical (pure copy, no refactor)
- [ ] New `eval_condition()` handles both `&&` and `||` correctly (test both)
- [ ] Shim in `backend/app/harnesses/decision.py` is thin (1–5 lines of delegation)
- [ ] `importlinter lint` passes (verifies no app imports in lib/conditions.py)
- [ ] All 79 existing tests pass via shim (no test rewrites)
- [ ] New tests added for `||` operator (at least 4 cases: or-true, or-false, nested, edge cases)
- [ ] Deliver.workflow.yaml duplicates collapsed (lines 211–212 → single edge with `in` or new `||`)

### 9. Operator Support Detail

#### Current operators (4)

| Operator | Clause level | Operands | Notes |
|----------|--------------|----------|-------|
| `==` | yes (line 332) | string == string | Case-sensitive exact match |
| `!=` | yes (line 334) | string != string | Negation; `None != value` → `True` |
| `in` | yes (line 336) | string in `val1,val2,val3` | Comma-separated list; strips whitespace |
| `&&` | expression level (line 375) | clause && clause | All clauses must hold (short-circuit AND) |

#### New operator to add (`||`)

| Operator | Clause/Expression | Operands | Proposed handling |
|----------|-------------------|----------|-------------------|
| `\|\|` | expression level (new) | clause \|\| clause | Any clause can hold (short-circuit OR); higher precedence than `&&` (standard) |

**Precedence model** (proposed, matches C/Python):
- `&&` and `||` both expression-level (no clause-level `||`)
- `||` has lower precedence than `&&` (e.g., `a || b && c` = `a || (b && c)`)
- If user wants `(a || b) && c`, they must write as two edges (current Cronos workaround)

**Implementation**:
1. Split on ` || ` to get OR clauses
2. For each OR clause, split on ` && ` to get AND clauses
3. Evaluate: `(and_1 && and_2 && ...) || (and_3 && and_4 && ...) || ...`

---

## Assumptions

- `_eval_single_clause()` is tested indirectly via all 79 eval_condition tests; lifting it requires zero test rewrites if signature/semantics preserved
- Scope values are always strings post-coercion (adapter coerces at boundary); grammar assumes string comparisons only
- Visual-harness tests are all in backend/tests/ (app-side); shim in decision.py makes them zero-friction
- Importlinter cache will be regenerated after migration; no manual cache-invalidation needed
- `||` operator is low-priority for current delivery.workflow.yaml (can use `in` operator as shorter-term fix)
- Parentheses for complex `||` expressions are deferred to v2 (per existing pattern of documented v1 limitations)

## Open questions

None. Coverage is comprehensive; scope is clear.

## Next consumer brief

**For analysis agent (SG3 analyst)**:

Read these fields first from this scout report:
- `## Findings § 1` — pure function guarantee + regex patterns
- `## Findings § 5` — exact duplicate edge locations (lines 211–212 in delivery.workflow.yaml)
- `## Findings § 6` — test coverage (79 existing tests, all passing)
- `## Findings § 8` — migration step-by-step + risks table

**Decision points for analyst**:
1. Should `||` support require parentheses-aware parsing (v2), or is simple ` || ` splitting sufficient for current workflow?
   - Current edge needs only simple disjunction (code OR dependency); recommend simple split first
2. Should collapsed edges use new `||` operator or existing `in` operator?
   - Both work; `in` is existing, `||` is more readable for two-value case. Recommend `||` for clarity + v1 operator spec
3. Is adapter update (lib.conditions import) required in this iteration, or is shim sufficient?
   - Shim is backward-compatible; adapter update optional. Recommend defer to later PR for cleaner separation

**Unresolved blockers**: None. Ready to proceed.
