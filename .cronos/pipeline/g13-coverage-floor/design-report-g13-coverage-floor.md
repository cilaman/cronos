---
cc_version: '1.0'
agent: pipeline-architect
slug: g13-coverage-floor
phase: design
status: done
confidence: 0.96
inputs_used:
- memory:project-test-coverage
- memory:project-g02-ci-pipeline-impl
- .cronos/pipeline/g13-coverage-floor/analysis-report-g13-coverage-floor.md
- .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
- backend/pyproject.toml
outputs_produced:
- .cronos/pipeline/g13-coverage-floor/design-report-g13-coverage-floor.md
blockers: []
next_consumer: implementation
iterations:
- id: I1
  type: infra
  scope_files:
  - backend/pyproject.toml
  validation_command: cd backend && pytest tests/ --cov=app --cov-report=term-missing
    --cov-fail-under=80
  max_diff_lines: 5
  depends_on: []
risks:
- description: Actual coverage may have drifted below 80% since the a724133 baseline
    (~85.15%) due to non-test source additions (e.g. G02 ruff/mypy module churn, other
    remediation subgoals), causing the validation command to fail at the new floor.
  severity: medium
  mitigation: The implementor runs the full validation command and reads the coverage
    total before marking R2 done. If coverage is below 80%, surface as a blocker (do
    NOT lower the floor or use --override-ini to mask it) so the gap is addressed
    explicitly rather than the floor being set unrealistically.
- description: A stray or duplicate --cov-fail-under value elsewhere in pyproject.toml
    (or in a CI invocation that re-passes the flag) could shadow the edit, leaving
    the effective floor at 60.
  severity: low
  mitigation: After the edit, grep the whole repo for --cov-fail-under and confirm
    exactly one occurrence, set to 80. CLAUDE.md and CI (G02 ci.yml) both rely on
    the pyproject addopts value, so a single source of truth is sufficient.
- description: Raising the floor too high (85+) would leave no headroom and cause
    red CI builds on trivial churn (the explicit rejection in the source brief).
  severity: low
  mitigation: Value is fixed at 80 by the analysis/brief decision, giving ~5% headroom.
    Do not parameterize or raise without a new request.
coverage_summary:
  searched:
  - .cronos/pipeline/g13-coverage-floor/analysis-report-g13-coverage-floor.md (R1/R2
    traceability, scope, validation command)
  - backend/pyproject.toml (line 39, addopts --cov-fail-under value)
  - backend/app/pipeline/schemas/design.schema.yaml (iterations[]/risks[] contract)
  excluded:
  - frontend/ (no frontend coverage threshold in G13 scope)
  - backend/app/ (no source changes; floor adjustment only)
  - backend/tests/ (no new tests; floor change is self-validating)
  strategies:
  - memory_retrieval
  - read_targeted
metrics:
  tool_calls: 5
  files_read: 4
  memory_hits: 2
  iterations_planned: 1
---

## Summary

G13 raises the pytest coverage enforcement floor in `backend/pyproject.toml` from
60% to 80% — a single-line change to the `--cov-fail-under` flag inside the
`[tool.pytest.ini_options]` `addopts` string (line 39). The analysis routed this
directly to implementation as an XS, backend-only config change with no source or
test edits required. The design therefore collapses to **one atomic infra
iteration** with no internal dependencies: edit the value, then prove it by running
the full suite at the new floor. CI (G02 `ci.yml`) reads the same `addopts` value,
so changing it here is sufficient to enforce the new gate end-to-end. The 80 value
(not 85) is fixed by the source brief to preserve ~5% headroom over the ~85.15%
baseline and avoid flaky red builds on minor churn.

## Components

| Component | Role in this change |
|-----------|---------------------|
| `backend/pyproject.toml` → `[tool.pytest.ini_options].addopts` | Single source of truth for the coverage floor. Local `pytest tests/`, the `cron`/dev workflow, and the G02 CI job all consume this value. Changing `--cov-fail-under=60` → `=80` here is the entire change surface. |
| G02 CI job (`ci.yml`, already on `feature/cronos-remediation-plan`) | Enforces the floor in CI. No edit needed — it inherits the `addopts` value at test time. |

There is no module decomposition: the change is a leaf config value with a single
downstream consumer chain. No new components are introduced.

## Implementation plan

Topologically ordered (single node — no dependency edges):

### I1 — Raise coverage floor 60 → 80 (type: infra)
- **scope_files (hard boundary):** `backend/pyproject.toml`
- **Edit:** On line 39, change `--cov-fail-under=60` to `--cov-fail-under=80` inside
  the `addopts` string. Touch nothing else.
- **depends_on:** none
- **max_diff_lines:** 5
- **validation_command:**
  `cd backend && pytest tests/ --cov=app --cov-report=term-missing --cov-fail-under=80`
- **Done when:** the validation command exits 0 (R2) AND
  `grep -rn -- --cov-fail-under` over the repo shows exactly one occurrence equal to
  80 (R1).

This single iteration satisfies both requirements from the analysis traceability:
R1 (the value is changed) is structurally satisfied by the edit; R2 (suite passes
at the new floor) is satisfied by the validation command exiting 0. Both have
`verifying_phase: test`, so the downstream test phase re-runs the same command as
the authoritative gate.

## Risks

The machine-readable `risks[]` array in the YAML header is the source of truth.
Compact human view:

| Severity | Risk | Mitigation |
|----------|------|------------|
| medium | Coverage drifted below 80% since baseline → validation fails | Run full validation, read the coverage total; surface a blocker rather than masking — never lower the floor or `--override-ini` to force-pass |
| low | Stray/duplicate `--cov-fail-under` shadows the edit | `grep -rn` for the flag; confirm exactly one occurrence = 80 |
| low | Floor set too high (85+) causes flaky CI | Value fixed at 80 by brief; ~5% headroom; do not raise without a new request |

## Assumptions

- The analysis report's scope is authoritative: `backend/pyproject.toml` line 39 is
  the only change site, confirmed against the live file (current value `60`).
- G02 CI is already merged onto `feature/cronos-remediation-plan` and reads the
  `addopts` value at runtime; no CI-file edit is required for enforcement.
- The ~85.15% baseline (commit a724133) holds with enough margin that the suite
  passes at 80. The implementor must verify, not assume, by running the validation
  command — coverage can drift between commits.
- No frontend coverage threshold is in scope (vitest has none configured); this is
  backend-only.

## Open questions

None. The single decision point (floor value = 80, not 85) is settled by the source
brief and the analysis report.

## Next consumer brief

**Implementor reads:** this `iterations[]` array — exactly one entry, **I1**.

- **Iteration:** I1 (type: infra, no dependencies — start immediately).
- **Scope file (hard boundary):** `backend/pyproject.toml` only. `files_changed`
  MUST be exactly `[backend/pyproject.toml]`.
- **Exact edit:** line 39 `addopts` string, `--cov-fail-under=60` → `--cov-fail-under=80`.
  No other token on that line or elsewhere in the file changes.
- **Validation command (run it, do not skip):**
  `cd backend && pytest tests/ --cov=app --cov-report=term-missing --cov-fail-under=80`
  Set `validation_command_passed: true` only if it genuinely exits 0.
- **If validation fails because coverage < 80%:** STOP and emit a blocker. Do NOT
  lower the floor, do NOT use `--override-ini`, do NOT add filler tests outside
  scope. Report the actual coverage number so the gap can be addressed as its own
  concern.
- **Post-edit sanity check:** `grep -rn -- --cov-fail-under` across the repo →
  exactly one match, value 80.
