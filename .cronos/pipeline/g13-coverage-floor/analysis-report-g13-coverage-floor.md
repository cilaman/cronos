---
cc_version: '1.0'
agent: pipeline-analyst
slug: g13-coverage-floor
phase: analysis
status: done
confidence: 0.97
inputs_used:
- memory:project-remediation-board-setup
- memory:project-test-coverage
- memory:project-g02-ci-pipeline-impl
- .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
- .cronos/workspaces/2026-06-20-1427-create-remedy-goals/REMEDIATION-PLAN.md
- backend/pyproject.toml
outputs_produced:
- .cronos/pipeline/g13-coverage-floor/analysis-report-g13-coverage-floor.md
blockers: []
next_consumer: implementation
request: 'G13: Raise coverage floor 60 → 80


  Files: pyproject.toml (line ~39, addopts = "... --cov-fail-under=60").

  The actual coverage as of a724133 is ~85.15%, so raising to 80 leaves ~5% headroom.

  Setting to 85 would leave no headroom and cause flaky CI on minor churn.'
has_ui: false
coverage_summary:
  searched:
  - backend/pyproject.toml (line 39, --cov-fail-under value)
  - .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
    (G13 findings)
  - .cronos/workspaces/2026-06-20-1427-create-remedy-goals/REMEDIATION-PLAN.md (G13
    section)
  excluded:
  - frontend/: backend-only config change; no frontend coverage threshold involved
  - backend/app/: no source code changes required
  - backend/tests/: no new tests required (floor change is self-validating)
  strategies:
  - memory_retrieval
  - read_targeted
traceability:
- requirement_id: R1
  statement: The pytest coverage floor in backend/pyproject.toml must be changed from
    60 to 80 (the --cov-fail-under flag in [tool.pytest.ini_options] addopts).
  acceptance_criteria:
  - Given backend/pyproject.toml, the addopts value contains --cov-fail-under=80 (not
    60).
  - No other value for --cov-fail-under exists anywhere in pyproject.toml.
  verifying_phase: test
  confidence: 0.99
- requirement_id: R2
  statement: The full pytest suite must pass at the new 80% floor without failures
    (validates that current actual coverage provides sufficient headroom).
  acceptance_criteria:
  - Given the change from R1 applied, running pytest tests/ in backend/ exits 0 (all
    tests pass, coverage >= 80%).
  - The coverage report shows actual coverage >= 80% (expected ~85% based on remediation
    plan baseline).
  verifying_phase: test
  confidence: 0.95
metrics:
  tool_calls: 6
  files_read: 4
  memory_hits: 3
---

## Summary

G13 raises the pytest coverage enforcement floor in `backend/pyproject.toml` from 60% to 80%. This is a single-line config change — `--cov-fail-under=60` → `--cov-fail-under=80` — that makes the CI gate reflect the project's actual quality (85.15% baseline). The 5% headroom at 80 prevents red builds from minor churn while still protecting against regression. No source code, tests, or non-config files are touched. This goal is XS effort, backend-only, and routes directly to the implementation phase.

## Scope

### In scope
- Change `--cov-fail-under=60` to `--cov-fail-under=80` in `backend/pyproject.toml` line 39
- Validate that `pytest tests/` exits 0 at the new floor

### Out of scope
- Frontend coverage thresholds (vitest has no `--coverage-lines-threshold` set; a separate concern not in G13)
- Adding new tests to raise coverage above the floor (G13 is a floor adjustment, not a coverage improvement goal)
- Mypy or ruff configuration changes (G02 scope)

### Deferred
- Ratcheting the floor upward over time (G13 Remediation Plan note: "ratchet upward over time"); can be done as a follow-on when coverage naturally improves
- Setting the floor to 85 or higher (explicitly rejected in the source brief to avoid flaky CI on minor churn)

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | Change `--cov-fail-under` from 60 to 80 in `backend/pyproject.toml` |
| R2 | Full pytest suite passes at the new 80% floor |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). The body summary below mirrors them in compact form for the human reader.

- R1 — `backend/pyproject.toml` contains exactly `--cov-fail-under=80` in the addopts line; no other `--cov-fail-under` value exists
- R2 — `pytest tests/` exits 0 in backend/ with the new floor applied; coverage report shows ≥ 80%

## Traceability

The full requirement → acceptance criteria → verifying_phase map is the YAML `traceability[]` array. Downstream agents read the YAML directly; this section exists so a human reader sees the same routing table without parsing YAML.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | Change `--cov-fail-under` from 60 to 80 in `backend/pyproject.toml` |
| R2 | test | Full pytest suite passes at the new 80% floor |

## Assumptions

- `has_ui: false` rationale: this is a pure backend config change in `pyproject.toml`; no React/TS/UI code is touched.
- `next_consumer: implementation` rationale: the change is a trivial one-line edit (XS effort per remediation plan); no design-phase architecture work is required.
- The remediation plan baseline of 85.15% actual coverage is correct as of commit `a724133`. The implementor must verify `pytest tests/` exits 0 at 80% before marking R2 done — coverage can drift between commits.
- G02 (CI pipeline) is already implemented (committed to `feature/cronos-remediation-plan`). The `--cov-fail-under` value in `pyproject.toml` is what CI reads at test time; changing it here is sufficient for CI enforcement without additional changes.
- The scope of `backend/pyproject.toml` line 39 was confirmed by both the scout report (G13 findings) and a direct read of the file (actual line 39: `addopts = "--cov=app --cov-report=term-missing --cov-fail-under=60"`).

## Open questions

None.

## Next consumer brief

**Implementor reads:** `traceability[]` (2 requirements, both `verifying_phase: test`), `## Scope` (out-of-scope list confirms no test additions needed).

**Scope file (hard boundary):** `backend/pyproject.toml` — change only the `--cov-fail-under` value on line 39; no other files.

**Validation command:** `cd backend && pytest tests/ --cov=app --cov-report=term-missing --cov-fail-under=80`

**Key decision already made:** Value is 80 (not 85). The remediation plan explicitly rejects 85 because it leaves no headroom and causes flaky CI on minor churn. Do not set it higher without a new request.

**Risk:** If coverage has dropped below 80% since the a724133 baseline (e.g., due to G02 ruff/mypy module additions), the implementor must surface this as a blocker — do not force-pass validation. The expected headroom is ~5% (85.15% actual minus 80% floor).
