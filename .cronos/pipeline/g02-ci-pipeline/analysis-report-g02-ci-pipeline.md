---
cc_version: '1.0'
agent: pipeline-analyst
slug: g02-ci-pipeline
phase: analysis
status: done
confidence: 0.93
inputs_used:
- memory:pipeline-analyst-agent
- memory:pipeline-gate-skill
- .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
- .cronos/workspaces/2026-06-20-1427-create-remedy-goals/REMEDIATION-PLAN.md
- .claude/agents/pipeline-analyst.md
- backend/pyproject.toml
- backend/Dockerfile
- frontend/Dockerfile
- frontend/package.json
outputs_produced:
- .cronos/pipeline/g02-ci-pipeline/analysis-report-g02-ci-pipeline.md
blockers: []
next_consumer: design
request: 'CC-v1 analyst phase for: G02: CI pipeline + branch protection + lint config


  Read scout report: `.cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md`

  Agent contract: `.claude/agents/pipeline-analyst.md`

  Artifact: `.cronos/pipeline/g02-ci-pipeline/analysis-report-g02-ci-pipeline.md`
  (class=analysis)


  ## Scope


  Files: `.github/workflows/ci.yml` (new), `pyproject.toml` (new ruff/mypy sections).

  Both Dockerfiles and `docker-compose.yml` should be consulted for the correct

  pip-install and npm-ci invocations to replicate in CI. The coverage gate in CI

  matches `--cov-fail-under` in `pyproject.toml`.


  ## Source


  All requirements derive from the Cronos Remediation Plan:

  `.cronos/workspaces/2026-06-20-1427-create-remedy-goals/REMEDIATION-PLAN.md`


  Decompose the relevant G-number section into testable requirements.

  Emit analysis-report with has_ui flag, scope[], requirements[], and

  traceability[] back to the remediation plan acceptance criteria.'
has_ui: false
coverage_summary:
  searched:
  - .cronos/pipeline/cronos-remediation-plan/ (scout report)
  - .cronos/workspaces/2026-06-20-1427-create-remedy-goals/ (remediation plan)
  - backend/pyproject.toml (existing lint/test config and [tool.*] sections)
  - backend/Dockerfile (pip install invocation for CI reference)
  - frontend/Dockerfile (npm install invocation for CI reference)
  - frontend/package.json (available scripts: build, test)
  - .github/ (confirmed absent — no workflows directory)
  excluded:
  - docker-compose.yml: No CI-relevant invocations beyond what Dockerfiles show; Dockerfile
      installs are the reference
  - frontend/src/: No frontend source changes required by G02
  - backend/app/: No source code changes required by G02
  strategies:
  - memory_retrieval
  - read_targeted
  - glob_structural
traceability:
- requirement_id: R1
  statement: A `.github/workflows/ci.yml` workflow file exists that triggers on `push`
    and `pull_request` events.
  acceptance_criteria:
  - Given a push or PR to any branch, the CI jobs (backend and frontend) are triggered
    automatically.
  - The workflow file is valid GitHub Actions YAML and parseable by the GH Actions
    runner.
  - '`.github/workflows/ci.yml` is present in the repository root.'
  verifying_phase: review
  confidence: 0.95
- requirement_id: R2
  statement: The backend CI job installs Python dev dependencies via `pip install
    -e ".[dev]"` and runs `ruff check` for linting.
  acceptance_criteria:
  - Given the backend job runs on the current codebase, `ruff check` exits 0.
  - The job uses `pip install -e ".[dev]"` (not bare `pip install .`) so pytest, pytest-cov,
    and other dev tools are available.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R3
  statement: The backend CI job runs `mypy` for static type-checking using the `[tool.mypy]`
    config in `pyproject.toml`; if a fully-clean pass is infeasible, a tracked `[[tool.mypy.overrides]]`
    block documents the known-failing modules.
  acceptance_criteria:
  - Given the backend CI job runs, `mypy` exits 0 (either clean pass or with only
    configured-ignore modules).
  - If overrides are used, they are present in `pyproject.toml` under `[[tool.mypy.overrides]]`
    with `ignore_errors = true` per module and a comment marking the debt.
  verifying_phase: test
  confidence: 0.85
- requirement_id: R4
  statement: The backend CI job runs `pytest` with the coverage gate declared in `pyproject.toml`
    and the full test suite passes green.
  acceptance_criteria:
  - Given the backend job runs `pytest`, it exits 0 with all tests passing.
  - Coverage does not fall below the value set in `pyproject.toml` `--cov-fail-under`
    (currently 60).
  - No separate `--cov-fail-under` flag is hard-coded in CI; the value is inherited
    from `pyproject.toml` `addopts`.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R5
  statement: A `[tool.ruff]` configuration section is added to `pyproject.toml` with
    at minimum `target-version` and `line-length` settings.
  acceptance_criteria:
  - '`[tool.ruff]` section is present in `backend/pyproject.toml`.'
  - Running `ruff check backend/` uses the config (not ruff defaults) — verifiable
    via `ruff check --show-settings`.
  - '`target-version` is set to `"py312"` to match `requires-python = ">=3.12"`.'
  verifying_phase: review
  confidence: 0.95
- requirement_id: R6
  statement: A `[tool.mypy]` configuration section is added to `pyproject.toml` with
    at minimum Python version and strictness settings.
  acceptance_criteria:
  - '`[tool.mypy]` section is present in `backend/pyproject.toml`.'
  - '`python_version` is set (e.g. `"3.12"`).'
  - If overrides are needed, they are declared via `[[tool.mypy.overrides]]` in the
    same file rather than a separate `.mypy.ini`.
  verifying_phase: review
  confidence: 0.9
- requirement_id: R7
  statement: The frontend CI job installs Node dependencies via `npm ci` (not `npm
    install`) and runs `tsc -b` TypeScript compilation as a standalone check.
  acceptance_criteria:
  - Given the frontend CI job runs, `npm ci` is used to ensure reproducible installs
    from `package-lock.json`.
  - '`npx tsc -b` (or equivalent) exits 0, confirming no TypeScript errors.'
  verifying_phase: test
  confidence: 0.9
- requirement_id: R8
  statement: The frontend CI job runs `npm test` (`vitest run`) and all existing unit
    tests pass.
  acceptance_criteria:
  - Given the frontend CI job runs, `npm test` (which maps to `vitest run`) exits
    0.
  - No tests are skipped or marked xfail without an explicit reason.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R9
  statement: The frontend CI job runs the production build (`npm run build`) and verifies
    it succeeds without errors.
  acceptance_criteria:
  - Given the frontend CI job runs, `npm run build` (which executes `tsc -b && vite
    build`) exits 0.
  - Build artifacts are produced in `frontend/dist/`.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R10
  statement: GitHub branch protection on `main` is configured so that all CI check
    jobs must pass before a PR can be merged.
  acceptance_criteria:
  - A PR with any failing CI check job cannot be merged via the GitHub UI (merge button
    disabled or blocked).
  - This configuration is documented in the deployment notes (VPS_SETUP.md or README)
    as a post-deploy manual step.
  verifying_phase: manual
  confidence: 0.88
metrics:
  tool_calls: 10
  files_read: 7
  memory_hits: 2
---

## Summary

G02 adds a GitHub Actions CI workflow that catches regressions before they land on `main` — the direct response to `main` currently shipping a red test. The deliverables are two new configuration additions: `.github/workflows/ci.yml` (a backend + frontend jobs matrix) and `[tool.ruff]`/`[tool.mypy]` sections in `pyproject.toml`. The backend job mirrors the `pip install -e ".[dev]"` + `pytest` invocation documented in CLAUDE.md; the frontend job mirrors the `npm ci` + `tsc -b` + `vitest run` + `vite build` chain. Branch protection is a GitHub-side configuration step, not a file change, but is included as R10 (manual) because it is an acceptance criterion. No source code changes are in scope.

## Scope

### In scope
- New file: `.github/workflows/ci.yml` — backend and frontend CI jobs
- Modified file: `backend/pyproject.toml` — add `[tool.ruff]` and `[tool.mypy]` sections
- Backend job: `pip install -e ".[dev]"`, `ruff check`, `mypy`, `pytest` (with existing `--cov-fail-under=60` gate from `pyproject.toml`)
- Frontend job: `npm ci`, `tsc -b`, `vitest run`, `npm run build`
- GitHub branch protection configuration on `main` (documented manual step)

### Out of scope
- Changing the coverage threshold (G13 owns that)
- Source code changes to make mypy or ruff pass (linting/type errors must be fixed or baselined before CI is enabled)
- Pre-commit hooks (additive, not a gate; can follow later)
- Docker Compose `security_opt`/`cap_drop` (G03)
- Secrets management or PAT changes (G11)
- OpenAPI type generation (G14)

### Deferred
- Raising the coverage floor from 60 to ~80 (G13, depends on G02)
- Frontend coverage thresholds (no current vitest coverage config; add after G02)
- Matrix builds across Python/Node versions (personal project, single supported version per pyproject.toml / Dockerfiles)
- Dependency caching (pip/npm) for CI speed — design may add; not an AC

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | `.github/workflows/ci.yml` triggers on push and pull_request |
| R2 | Backend CI: `pip install -e "[dev]"` + `ruff check` passes |
| R3 | Backend CI: `mypy` passes (clean or with tracked overrides) |
| R4 | Backend CI: `pytest` full suite green with `pyproject.toml` coverage gate |
| R5 | `[tool.ruff]` section added to `backend/pyproject.toml` |
| R6 | `[tool.mypy]` section added to `backend/pyproject.toml` |
| R7 | Frontend CI: `npm ci` + standalone `tsc -b` check |
| R8 | Frontend CI: `vitest run` passes |
| R9 | Frontend CI: `npm run build` production build passes |
| R10 | GitHub `main` branch protection requires all CI jobs green (manual step) |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]`
array (the machine-readable source of truth). The body summary below mirrors them
in compact form for the human reader.

- R1 — `.github/workflows/ci.yml` exists, is valid YAML, and triggers on push/PR
- R2 — `ruff check` exits 0 after `pip install -e ".[dev]"` in the backend job
- R3 — `mypy` exits 0 (clean or with `[[tool.mypy.overrides]]` debt documented in `pyproject.toml`)
- R4 — `pytest` exits 0 with full suite green; `--cov-fail-under` inherited from `pyproject.toml`, not duplicated in CI YAML
- R5 — `[tool.ruff]` with `target-version = "py312"` and `line-length` present in `pyproject.toml`
- R6 — `[tool.mypy]` with `python_version = "3.12"` and strictness settings present in `pyproject.toml`
- R7 — `npm ci` used (not `npm install`); `npx tsc -b` exits 0 as a standalone step
- R8 — `npm test` (`vitest run`) exits 0 with all tests passing
- R9 — `npm run build` exits 0 and produces `frontend/dist/` artifacts
- R10 — PR merge blocked when any CI job is red (GitHub branch protection, documented as manual)

## Traceability

The full requirement → acceptance criteria → verifying_phase map is the YAML
`traceability[]` array. Downstream agents read the YAML directly; this section
exists so a human reader sees the same routing table without parsing YAML.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | review | `.github/workflows/ci.yml` triggers on push and pull_request |
| R2 | test | Backend CI: ruff check passes after dev-deps install |
| R3 | test | Backend CI: mypy passes (clean or with tracked overrides) |
| R4 | test | Backend CI: pytest suite green with coverage gate from pyproject.toml |
| R5 | review | `[tool.ruff]` section added to pyproject.toml |
| R6 | review | `[tool.mypy]` section added to pyproject.toml |
| R7 | test | Frontend CI: npm ci + standalone tsc -b passes |
| R8 | test | Frontend CI: vitest run passes |
| R9 | test | Frontend CI: production build passes |
| R10 | manual | GitHub main branch protection requires all CI jobs green |

## Assumptions

- `has_ui = false` rationale: G02 creates CI configuration files (`.github/workflows/ci.yml`, `pyproject.toml` sections) — no UI surfaces are added or modified. Frontend source is *tested by* CI, not changed by it.
- The current codebase at `e6883dc` (plugin frontend I1) is the implementation target; line references in the scout (at `a724133`) may have drifted — the implementor must re-verify before editing.
- `ruff check` can be made to exit 0 on the current codebase with a reasonable `[tool.ruff]` config; if violations exist, the implementor adds `# noqa` or fixes them — **not** disables the entire check.
- A clean `mypy` pass on the full codebase at strict settings is likely infeasible in one pass (FastAPI + SQLite + async code rarely passes strict mypy out of the box). The tracked `[[tool.mypy.overrides]]` path is the expected first-pass approach, not a fallback of last resort.
- `package-lock.json` exists (the frontend Dockerfile copies it via `frontend/package-lock.json*`); CI can therefore use `npm ci`. If it is absent, the implementor must generate it before enabling R7.
- The backend Dockerfile uses `pip install .` (prod-only deps); CI diverges intentionally by using `pip install -e ".[dev]"` to get `pytest`, `pytest-cov`, and related dev tools.
- The frontend Dockerfile uses `npm install`; CI uses `npm ci` intentionally for reproducibility.
- Branch protection (R10) is a GitHub repository settings action — it is not a file committed to the repo. The design agent may produce a deployment note or update `deploy/VPS_SETUP.md` to document this step; the implementor cannot automate it.
- Pip/npm dependency caching in CI is a performance improvement (not a correctness requirement) and is left to the design agent's discretion.

## Open questions

- None. The scout report is `status: done` and all referenced modules were confirmed to exist. The mypy baseline approach (full clean vs. tracked overrides) is a design decision, not an analysis blocker — both paths produce a verifiable, passing CI job.

## Next consumer brief

**Design agent:** read `traceability[]` for all 10 requirements, then focus on these decisions:

1. **Workflow structure** — single workflow with two jobs (backend, frontend) or two separate workflow files? Single file is simpler for branch protection (one workflow to require).
2. **Job trigger scope** — trigger on `push` to any branch or only `main`/`feature/**`? For a personal project, "any branch" is safe and catches regressions early.
3. **Mypy baseline strategy** — design must decide whether to configure `ignore_errors = true` per-module `[[overrides]]` or add per-file `# type: ignore` comments; the former keeps the debt visible in `pyproject.toml`, the latter is harder to audit.
4. **Frontend tsc step** — R7 requires `tsc -b` as a standalone step; `npm run build` (R9) also runs `tsc -b` internally. The design may collapse these into a single `npm run build` step, but must ensure the type errors surface as a distinct failure (not buried in vite build output).
5. **Branch protection doc** — R10 requires documentation; design should add a brief "Step N: Enable branch protection" to `deploy/VPS_SETUP.md`.
6. **Scope boundary is hard**: design and implementor MUST NOT add ruff/mypy fixes to source files as part of G02 — any ruff/mypy violations should be baselined, not cleaned up here (scope creep risk is high).
