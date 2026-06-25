# Delivery/v1 Gate Engine

> **Status**: Implemented and shipped (2026-06-24). Reference: `backend/app/pipeline/gate.py`

## Overview

The **gate engine** (`runGate`) is the CC-v1 maturation feature that distinguishes _outcome checks_ from _contract checks_:

- **Contract checks** read artifacts to verify they are well-formed and self-consistent (schema, traceability, acceptance criteria).
- **Outcome checks** re-execute the claim to verify it actually works (build, lint, types, test, diff_vs_acceptance, review verdict).

The core invariant: an outcome check **must re-execute**. A self-reported `validation_command_passed: true` over a genuinely failing command is **caught and downgraded to `needs_fix`** — never trusted.

---

## API

```python
from app.pipeline.gate import runGate, GateResult

result: GateResult = runGate(
    gate,              # dict with ordered checks[] list (from state.json)
    artifact_paths,    # { "class": "path/to/artifact.md", ... }
    *,
    space,             # Cronos space directory (for artifact lookup)
    gate_id,           # node_id from harness (for state.json write)
    state_path,        # path/to/state.json (for atomic result write)
)

# GateResult.decision ∈ {"proceed", "needs_fix", "fail", "retry"}
# GateResult.errors: list[str] — gate-blocking error messages
# GateResult.evidence: dict[str, Any] — check outputs and diagnostic data
```

---

## Check Families

### Contract Checks (read-only; trust the artifact structure)

#### `schema` — Validates artifact structure

Checks that the artifact header validates against its class schema (`analysis.schema.yaml`, `implementation.schema.yaml`, etc.) and passes cross-field rules (R-rules) from the verifier.

**When it fails:**
- Required fields missing (e.g., artifact has no `slug`)
- Field type mismatch (e.g., `status` is not one of the enum values)
- Cross-field rule violated (e.g., `files_changed` present but empty on a non-stub phase)

**Evidence keys:**
- `schema_errors`: list of validation failures
- `schema_class`: artifact class (e.g., `"implementation"`)

---

#### `traceability` — Checks that id-links resolve

Verifies that all required `id_links` entries in the artifact are present and point to resolvable identifiers. A traceability section like:

```
[TRACEABILITY]
REQ-001 -> DD-001 -> [TC-001, TC-002] -> code/file.py -> docs/feature.md
```

is parsed to extract the links. Missing or broken links trigger failure.

**When it fails:**
- Required id-link missing from traceability matrix
- An id-link references a non-existent upstream artifact
- Circular dependencies in the link chain

**Evidence keys:**
- `traceability_errors`: list of missing/broken links
- `linked_ids`: dict of resolved ids (where available)

---

#### `acceptance` — Checks that acceptance criteria are present and testable

Scans all `acceptance_criteria` fields in the artifact. Each AC must:
1. Be non-empty (not `""`)
2. Be non-placeholder (not `"TBD"`, `"TODO"`, `"pending"`, etc.)
3. Contain at least one quantifiable term (e.g., `"must"`, `"should"`, `">=50%"`, a number)

**When it fails:**
- AC is empty or placeholder text
- AC is unmeasurable (e.g., `"nice to have"` with no metric)
- No AC defined for a requirement

**Evidence keys:**
- `acceptance_errors`: list of untestable/missing criteria
- `affected_reqs`: list of requirement ids with issues

---

### Outcome Checks (re-execute; never trust reported flags)

All outcome checks invoke `_run_command(cmd, cwd, timeout=300)`, which:
- Runs the command via `subprocess.run(shell=True, cwd=cwd)`
- Captures exit code, stdout (last 50 lines), stderr (last 50 lines)
- Times out after 300s → `needs_fix` with timeout evidence
- **Never fabricates a result** — if the command fails, the gate fails

#### `build` — Re-runs the build

Runs the `build_command` from the gate spec (e.g., `"cd backend && python setup.py build"`).

**When it fails:**
- Build command exits non-zero
- Build command times out

**Evidence keys:**
- `exit_code`: subprocess exit code
- `stdout_tail`: last 50 lines of stdout
- `stderr_tail`: last 50 lines of stderr

---

#### `lint` / `types` — Re-runs linter / type-checker

Runs the `lint_command` or `types_command` (e.g., `"cd frontend && npm run lint"` or `"cd backend && mypy app/"`).

**When it fails:**
- Linter/type-checker exits non-zero
- Command times out

**Evidence keys:**
- `exit_code`, `stdout_tail`, `stderr_tail` (same as build)

---

#### `test` — Re-runs the test suite

Runs the `test_command` (e.g., `"cd backend && pytest tests/ --cov=app"`). Reads the subprocess exit code AND attempts to parse coverage from pytest output.

**Coverage parsing:** Looks for the pytest `term-missing` format TOTAL line:
```
TOTAL    200    10    95%
```
Extracts the coverage percentage and gates on it if a `coverage_floor` threshold is set.

**When it fails:**
- Test command exits non-zero
- Command times out
- Coverage percentage (if parsed) is below `coverage_floor`

**Evidence keys:**
- `exit_code`: subprocess exit code
- `stdout_tail`, `stderr_tail`: last 50 lines
- `coverage_pct`: parsed coverage percentage (or `None` if not found)
- `coverage_floor`: threshold from gate spec
- `coverage_message`: "PASS" | "FAIL" (if threshold set)

**Coverage regex limitation (F2):** The regex only matches the 2-column `term-missing` TOTAL line. With branch coverage enabled (`Stmts Miss Branch BrPart Cover`), the regex returns `None` and the gate skips the coverage floor check (falls back to exit-code-only). This is by design — expand the regex when branch coverage is enabled.

---

#### `diff_vs_acceptance` — Checks that the diff covers claimed criteria

Compares the actual file diff against acceptance criteria in the artifact. This is a **heuristic check** with limitations:

1. Parses `acceptance_criteria` from the artifact
2. Extracts requirement ids from the criteria (e.g., `REQ-001`, `AC-002`)
3. Runs `git diff HEAD~1..HEAD` to get the diff
4. For each criterion, checks if the diff contains any mention of relevant files or code patterns
5. Computes a `coverage_ratio = covered_reqs / total_reqs`

**Advisory vs gating:** The threshold is a gate-spec parameter `diff_check_threshold` (default 0.5, range 0.0–1.0). If threshold is 0.0, this is an advisory check (passes regardless). If >0.0, fails if `coverage_ratio < threshold`.

**When it fails:**
- `coverage_ratio` is below the threshold
- Traceability source is unavailable and threshold >0.0 (advisory fallback: proceed anyway, log in evidence)

**Evidence keys:**
- `coverage_ratio`: fraction of reqs covered by diff
- `covered_req_ids`: list of reqs with diff coverage
- `uncovered_req_ids`: list of reqs without diff coverage
- `diff_snippet`: truncated diff for inspection
- `traceability_source_available`: whether analysis artifact was found

**Limitation (F1, non-blocking):** The granularity check counts per-requirement (any AC in a REQ → REQ is covered), not per-AC. The analyst spec (R10) calls for per-AC ratio. This is configurable via algorithm change; the current implementation is more lenient.

---

#### `g-review` — Routes on the review artifact verdict field

For review gates, reads the verdict field inside the review artifact (e.g., `verdict: pass` or `verdict: needs_fix`) and maps it to a gate decision:

- `verdict: pass` → `GateResult.proceed`
- `verdict: needs_fix` → `GateResult.needs_fix` (loop continues; NOT fail)
- `verdict: fail` → `GateResult.fail`
- `verdict: invalid` or missing → `GateResult.fail` (treat unknown as fail-closed)

**When it fails:**
- `verdict` field is missing from artifact
- `verdict` is not a recognized value

**Evidence keys:**
- `verdict`: the parsed verdict field
- `finding_ids`: list of finding ids (if present)
- `blocking_findings`: count of blocking findings (severity > low)

---

## Decision Precedence

When multiple checks run, the final decision is computed as:

```
if any check is "fail":    decision = "fail"
elif any check is "needs_fix":   decision = "needs_fix"
else:    decision = "proceed"
```

`retry` short-circuits before any check runs (artifact unreadable/missing → return `retry` immediately, no other checks).

---

## State Persistence

The gate result is written atomically to `state.json` under the node id:

```json
{
  "nodes": {
    "g-review": {
      "gate": {
        "decision": "proceed",
        "errors": [],
        "evidence": {
          "verdict": "pass",
          "blocking_findings": 0
        }
      }
    }
  }
}
```

Write uses the `tempfile + os.replace` pattern for atomicity (same as `state_writer._atomic_write_json`).

---

## Test Coverage

The implementation includes **85 tests** in `backend/tests/test_pipeline_gate.py`, organized by test class:

- **TestGateResult** — dataclass construction and validation
- **TestRunGate** — dispatcher logic, decision precedence
- **TestStateWrite** — atomic state.json writes
- **TestSchema** — schema validation against fixtures
- **TestAcceptance** — placeholder/empty AC detection
- **TestTraceability** — id-link resolution and circular-dep detection
- **TestBuild**, **TestLint**, **TestTypes**, **TestTestOutcome** — subprocess invocation and exit-code gating
- **TestDiffVsAcceptance** — diff parsing and coverage ratio computation
- **TestGReview** — verdict field routing and loop routing (needs_fix ≠ fail)

Test fixtures in `backend/tests/fixtures/gate/`:
- `analysis-report-good.md` — valid analysis artifact
- `analysis-report-bad-*.md` — schema/AC failures
- `impl-report-good.md` — validation_command exits 0
- `impl-report-lying.md` — validation_command exits 1 despite `validation_command_passed: true` (the R6 invariant is tested)
- `review-report-*.md` — verdict=pass/needs_fix/fail routing

---

## Known Limitations

### F1: `diff_vs_acceptance` granularity (non-blocking quality note)

The implementation counts coverage at the **per-requirement** level (any AC in a req → req covered). The analyst spec (R10) calls for **per-AC** level (each AC individually covered). This makes the heuristic more lenient.

**Workaround:** Tighten the heuristic by iterating per-AC instead of per-req when enabled for a gate spec. Current advisory-only default (threshold 0.0) makes this moot in practice.

### F2: Coverage regex assumes non-branch output (non-blocking quality note)

The coverage percentage regex (`r'TOTAL\s+\d+\s+\d+\s+(\d+)%'`) only matches the pytest `term-missing` format with two leading integer columns (Stmts, Miss). When branch coverage is enabled (`Stmts Miss Branch BrPart Cover`), the regex returns `None` and the gate skips the coverage floor check (falls back to exit-code-only gating).

**Workaround:** Broaden the regex to tolerate extra numeric columns: `r'TOTAL\s+(?:\d+\s+)+(\d+)%'`. Enable when branch coverage is required by the test runner config.

---

## Integration Points

1. **harness executor** (`backend/app/harnesses/executor.py`) — invokes `runGate` for gate nodes
2. **pipeline-gate skill** (`.claude/skills/pipeline-gate/`) — calls `runGate` from agent context
3. **state_writer** (`backend/app/pipeline/state_writer.py`) — shares atomic write pattern
4. **verify** (`backend/app/pipeline/verify.py`) — shares `split_frontmatter` parser

---

## See Also

- **Spec:** `docs/delivery-pipeline/delivery-v1-docs/delivery-v1-spec.md` § 5 (Gate semantics)
- **Analysis report:** `.cronos/pipeline/delivery-v1-gates/analysis-report-delivery-v1-gates.md`
- **Design report:** `.cronos/pipeline/delivery-v1-gates/design-report-delivery-v1-gates.md`
- **Implementation report:** `.cronos/pipeline/delivery-v1-gates/impl-report-delivery-v1-gates.md`
- **Review report:** `.cronos/pipeline/delivery-v1-gates/review-report-delivery-v1-gates--attempt1.md`
- **Test report:** `.cronos/pipeline/delivery-v1-gates/test-report-delivery-v1-gates.md`
