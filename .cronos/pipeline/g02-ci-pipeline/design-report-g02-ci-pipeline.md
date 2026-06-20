---
cc_version: '1.0'
agent: pipeline-architect
slug: g02-ci-pipeline
phase: design
status: done
confidence: 0.86
inputs_used:
- memory:project-pipeline-architect-agent
- memory:project-pipeline-foundation-merged
- memory:project-remediation-board-setup
- memory:feedback-pipeline-narrow-k-coverage
- .cronos/pipeline/g02-ci-pipeline/analysis-report-g02-ci-pipeline.md
- .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
- backend/pyproject.toml
- frontend/package.json
outputs_produced:
- .cronos/pipeline/g02-ci-pipeline/design-report-g02-ci-pipeline.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - .cronos/pipeline/g02-ci-pipeline/analysis-report-g02-ci-pipeline.md
  - .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
  - backend/pyproject.toml
  - frontend/package.json
  - .github/ (confirmed absent, will be created)
  - frontend/package-lock.json (confirmed present, enables npm ci)
  excluded:
  - backend/app/: HARD scope boundary — no source mutations in G02 (baseline lint/type
      debt instead)
  - backend/tests/: no test mutations in G02
  - frontend/src/: no source mutations in G02
  strategies:
  - memory_retrieval
  - read_targeted
iterations:
- id: I1
  type: infra
  scope_files:
  - backend/pyproject.toml
  validation_command: cd /data/spaces/cronos-development/backend && python -c "import
    tomllib, pathlib; data = tomllib.loads(pathlib.Path('pyproject.toml').read_text());
    assert 'ruff' in data['tool'], 'missing [tool.ruff]'; assert data['tool']['ruff'].get('target-version')
    == 'py312', 'target-version must be py312'; assert 'line-length' in data['tool']['ruff'],
    'missing line-length'; assert 'mypy' in data['tool'], 'missing [tool.mypy]'; assert
    data['tool']['mypy'].get('python_version') == '3.12', 'python_version must be
    3.12'; print('pyproject.toml ruff/mypy sections OK')"
  max_diff_lines: 120
  depends_on: []
- id: I2
  type: infra
  scope_files:
  - backend/pyproject.toml
  validation_command: cd /data/spaces/cronos-development/backend && pip install -e
    ".[dev]" --quiet && pip install ruff mypy --quiet && ruff check app/ && mypy app/
  max_diff_lines: 250
  depends_on:
  - I1
- id: I3
  type: infra
  scope_files:
  - .github/workflows/ci.yml
  validation_command: cd /data/spaces/cronos-development && python -c "import yaml,
    pathlib; doc = yaml.safe_load(pathlib.Path('.github/workflows/ci.yml').read_text());
    assert 'jobs' in doc, 'no jobs'; assert 'backend' in doc['jobs'], 'missing backend
    job'; assert 'frontend' in doc['jobs'], 'missing frontend job'; on = doc.get('on')
    or doc.get(True); assert 'push' in on and 'pull_request' in on, 'must trigger
    on push and pull_request'; steps_backend = [s.get('run', '') for s in doc['jobs']['backend']['steps']];
    joined_be = ' '.join(steps_backend); assert 'pip install -e' in joined_be and
    '.[dev]' in joined_be, 'backend must use editable dev install'; assert 'ruff check'
    in joined_be, 'backend must run ruff check'; assert 'mypy' in joined_be, 'backend
    must run mypy'; assert 'pytest' in joined_be, 'backend must run pytest'; assert
    '--cov-fail-under' not in joined_be, 'CI must NOT hard-code --cov-fail-under (inherit
    from pyproject.toml)'; steps_fe = [s.get('run', '') for s in doc['jobs']['frontend']['steps']];
    joined_fe = ' '.join(steps_fe); assert 'npm ci' in joined_fe, 'frontend must use
    npm ci (not npm install)'; assert 'tsc -b' in joined_fe, 'frontend must run tsc
    -b as distinct step'; assert 'npm test' in joined_fe or 'vitest' in joined_fe,
    'frontend must run tests'; assert 'npm run build' in joined_fe, 'frontend must
    run production build'; print('ci.yml structural check OK')"
  max_diff_lines: 200
  depends_on:
  - I1
- id: I4
  type: infra
  scope_files:
  - deploy/VPS_SETUP.md
  - README.md
  validation_command: cd /data/spaces/cronos-development && python -c "import pathlib;
    vps = pathlib.Path('deploy/VPS_SETUP.md').read_text(); readme = pathlib.Path('README.md').read_text();
    assert 'branch protection' in vps.lower() or 'branch protection' in readme.lower(),
    'branch protection step must be documented in VPS_SETUP.md or README.md'; assert
    ('main' in vps.lower() and 'protection' in vps.lower()) or ('main' in readme.lower()
    and 'protection' in readme.lower()), 'doc must mention main branch protection';
    print('R10 branch-protection doc OK')"
  max_diff_lines: 80
  depends_on: []
- id: I5
  type: infra
  scope_files:
  - .github/workflows/ci.yml
  - backend/pyproject.toml
  - frontend/package.json
  validation_command: cd /data/spaces/cronos-development && python -c "import yaml,
    pathlib, json; doc = yaml.safe_load(pathlib.Path('.github/workflows/ci.yml').read_text());
    be_steps = ' '.join(s.get('run', '') for s in doc['jobs']['backend']['steps']);
    fe_steps = ' '.join(s.get('run', '') for s in doc['jobs']['frontend']['steps']);
    pkg = json.loads(pathlib.Path('frontend/package.json').read_text()); assert pkg['scripts']['build']
    == 'tsc -b && vite build', 'frontend build must remain tsc -b && vite build';
    assert pkg['scripts']['test'] == 'vitest run', 'frontend test must remain vitest
    run'; print('cross-file invariants OK')" && cd /data/spaces/cronos-development/backend
    && pip install -e ".[dev]" --quiet && pytest -x --no-header --no-summary -q --override-ini="addopts="
    tests/ 2>&1 | tail -5
  max_diff_lines: 60
  depends_on:
  - I2
  - I3
  - I4
risks:
- description: Achieving a green `mypy app/` on the full FastAPI + aiosqlite + async
    codebase at meaningful strict settings is likely to surface dozens of errors that
    cannot be cleanly resolved without source mutations — which are out of scope for
    G02.
  severity: high
  mitigation: 'I2 uses a tracked `[[tool.mypy.overrides]]` baseline pattern: configure
    `[tool.mypy]` with conservative defaults (e.g. `python_version=3.12`, `ignore_missing_imports=true`,
    `warn_unused_ignores=false`) and add per-module `[[tool.mypy.overrides]] module
    = ''<debt-module>'' ignore_errors = true` entries in `pyproject.toml` for every
    module that fails. The validation_command runs `mypy app/` and must exit 0; the
    implementor must extend overrides (NEVER edit `backend/app/**` source) until it
    does. Each override entry MUST carry an inline TOML comment (`# debt: G02 mypy
    baseline`) so G13 can later eliminate them.'
- description: Same scope-creep risk applies to `ruff check app/` — strict default
    rule set may report violations the implementor would be tempted to fix in source.
  severity: high
  mitigation: I1 configures `[tool.ruff]` and `[tool.ruff.lint]` with a deliberately
    narrow `select` (e.g. `E`, `F` only — pyflakes + pycodestyle errors) and an `ignore`
    list for any remaining violations. I2 enforces `ruff check app/` exits 0. The
    implementor MUST extend ignore/exclude config, NEVER edit `backend/app/**` source.
    `scope_files` for every iteration excludes `backend/app/**` to make this boundary
    mechanically enforceable by the reviewer.
- description: R10 (GitHub branch protection on `main`) cannot be enforced via committed
    files — it is a repo-settings action on github.com. A failure to document it leaves
    the requirement unverifiable.
  severity: medium
  mitigation: I4 adds a dedicated section to `deploy/VPS_SETUP.md` (and a one-line
    pointer in README.md if discoverability matters) titled along the lines of 'Enable
    GitHub branch protection on `main`' with explicit steps (Settings → Branches →
    Add rule → require status checks `backend` and `frontend` to pass). Validation_command
    greps for the keyword 'branch protection' so the requirement is mechanically verified.
- description: R4 acceptance criterion forbids hard-coding `--cov-fail-under` in CI
    YAML; an implementor might add it for safety and inadvertently violate the requirement.
  severity: medium
  mitigation: I3's validation_command explicitly asserts that the substring `--cov-fail-under`
    does NOT appear anywhere in `.github/workflows/ci.yml`. The reviewer will see
    this enforced mechanically.
- description: R7 requires `tsc -b` to be a DISTINCT failing step from `vite build`
    (so the failure signal is type-check vs build). An implementor collapsing them
    into one `npm run build` step would hide which gate failed.
  severity: medium
  mitigation: I3's validation_command asserts the substring `tsc -b` appears in the
    frontend job's `steps[].run` text directly (not only as a child of `npm run build`).
    The implementor must add an explicit step `npx tsc -b` BEFORE `npm run build`.
- description: '`pip install -e ".[dev]"` in I2''s validation_command runs against
    the LIVE environment of the verifier host; if that environment lacks network or
    has a pinned/conflicting Python, the command exits non-zero for reasons unrelated
    to the design.'
  severity: low
  mitigation: Iteration I2 will be executed by the test phase inside the CI runner
    itself or in a fresh container; design-time self-verify only runs the static check
    (I1). The reviewer should accept this iteration's pass signal as the green CI
    run on the resulting PR rather than a local-host pytest. Note this expectation
    in the implementation brief.
metrics:
  tool_calls: 7
  files_read: 5
  memory_hits: 4
  iterations_planned: 5
---

## Summary

G02 ships a GitHub Actions CI workflow and the `[tool.ruff]` + `[tool.mypy]` config that supports it, plus a docs hook for the unautomatable branch-protection step (R10). The iteration DAG is two-layer-wide: layer 0 runs the config baseline (I1) and the docs change (I4) in parallel; layer 1 runs the lint/type baseline tightening (I2) and the workflow file (I3) in parallel once I1 lands; layer 2 (I5) is a cross-file invariant check that the CI YAML's commands continue to match `package.json` scripts and `pyproject.toml` pytest config. The single load-bearing tradeoff is recorded as the top-of-register risk: ruff and mypy errors on the existing codebase are baselined via tracked overrides in `pyproject.toml`, NEVER fixed in `backend/app/**` source — that work belongs to follow-on goals (G13 for coverage; future hygiene goals for the override list).

## Components

### Data
- No data model changes. G02 is pure CI/config infrastructure.

### Backend
- `backend/pyproject.toml`: add `[tool.ruff]` (target-version=py312, line-length, narrow `[tool.ruff.lint]` select), `[tool.mypy]` (python_version=3.12, ignore_missing_imports=true), and `[[tool.mypy.overrides]]` entries with `ignore_errors=true` for each module that currently fails — every override carries a `# debt: G02 mypy baseline` comment so G13 can prune them.
- No `backend/app/**` source changes. No `backend/tests/**` changes.

### Infra
- `.github/workflows/ci.yml` (new): a single workflow file with two parallel jobs:
  - `backend`: checkout, setup-python 3.12, `pip install -e ".[dev]"`, `ruff check app/`, `mypy app/`, `pytest tests/` (coverage gate inherited from `pyproject.toml` `addopts`).
  - `frontend`: checkout, setup-node 22, `npm ci`, `npx tsc -b` (distinct step), `npm test`, `npm run build`.
  - Trigger: `on: [push, pull_request]` (all branches).
- `deploy/VPS_SETUP.md`: append a section documenting the manual branch-protection configuration on `main` (Settings → Branches → require status checks `backend` and `frontend`).
- `README.md`: one-line pointer to the VPS_SETUP.md section so the requirement is discoverable from the project root.

## Implementation plan

| ID | Type  | Depends on | Scope files (abridged)                                    | Validation                                                                 |
|----|-------|------------|-----------------------------------------------------------|----------------------------------------------------------------------------|
| I1 | infra | -          | backend/pyproject.toml                                    | python tomllib check for `[tool.ruff]` (target-version=py312, line-length) and `[tool.mypy]` (python_version=3.12) |
| I2 | infra | I1         | backend/pyproject.toml                                    | `ruff check app/` exits 0 AND `mypy app/` exits 0 (achieved via narrow ruff select + tracked mypy overrides, NO source mutations) |
| I3 | infra | I1         | .github/workflows/ci.yml                                  | yaml.safe_load + structural asserts: backend+frontend jobs, push+pull_request trigger, `pip install -e ".[dev]"`, `ruff check`, `mypy`, `pytest` (no hard-coded `--cov-fail-under`), `npm ci`, distinct `tsc -b`, `npm test`, `npm run build` |
| I4 | infra | -          | deploy/VPS_SETUP.md, README.md                            | grep for 'branch protection' + 'main' in either VPS_SETUP.md or README.md |
| I5 | infra | I2, I3, I4 | .github/workflows/ci.yml, backend/pyproject.toml, frontend/package.json | cross-file invariants: CI YAML commands match `package.json` scripts (`vitest run`, `tsc -b && vite build`); full `pytest` smoke run (override-ini, no coverage gate) green |

## Risks

| Risk                                                                                              | Severity | Mitigation                                                                                                                                                |
|---------------------------------------------------------------------------------------------------|----------|-----------------------------------------------------------------------------------------------------------------------------------------------------------|
| mypy strict pass on full codebase likely infeasible without source edits (out of scope)           | high     | Tracked `[[tool.mypy.overrides]] ignore_errors = true` per failing module in pyproject.toml with `# debt: G02 mypy baseline` comments; NO source edits.   |
| ruff default rule set may report violations tempting source edits                                 | high     | Narrow `[tool.ruff.lint]` `select = ["E", "F"]` + `ignore` list; scope_files explicitly excludes `backend/app/**` so reviewer can mechanically enforce.    |
| R10 branch protection is github.com settings, not a file                                          | medium   | Dedicated section in deploy/VPS_SETUP.md + README pointer; validation_command greps for 'branch protection' so requirement is mechanically verifiable.    |
| Implementor may add `--cov-fail-under` to CI YAML, violating R4                                   | medium   | I3 validation_command asserts the substring is ABSENT from `.github/workflows/ci.yml`.                                                                    |
| Implementor may collapse `tsc -b` into `npm run build`, hiding which gate failed (violates R7)    | medium   | I3 validation_command asserts `tsc -b` appears as a top-level `run:` substring in the frontend job steps.                                                 |
| `pip install -e ".[dev]"` in I2 validation may fail on verifier host network/pyenv                | low      | I2 is designed to run in the CI runner / fresh container; design-time self-verify only runs static check I1. Brief implementor on this expectation.       |

## Assumptions

- `frontend/package-lock.json` exists and is current (confirmed by Read; 256 KB on disk). Enables `npm ci` without regenerating the lockfile.
- `backend/pyproject.toml` `[tool.pytest.ini_options].addopts` already contains `--cov-fail-under=60`; CI inherits this (R4 explicitly forbids duplicating it in YAML).
- GitHub Actions runner `ubuntu-latest` with `actions/setup-python@v5` (Python 3.12) and `actions/setup-node@v4` (Node 22) is available — matches local Dockerfile base images.
- The implementor will pin Action versions to major-version tags (`@v4`, `@v5`) rather than `@latest`, for reproducibility.
- `[tool.mypy] ignore_missing_imports = true` is acceptable for the baseline. A stricter setting (`disallow_untyped_defs`, `strict = true`) is deferred — out of G02 scope per analyst.
- The implementor may add pip/npm caching (`actions/cache@v4` or `setup-python`/`setup-node` built-in cache) as a performance improvement — not required for any acceptance criterion. Caching does NOT count as a source change.
- I2's `ruff check app/` and `mypy app/` are run with `cd backend` so that paths resolve correctly relative to `backend/pyproject.toml`.

## Open questions

- None. All 10 requirements have concrete iteration coverage; mypy baseline strategy is explicitly tracked-overrides per analyst Next-consumer-brief item 3 and per the high-severity risk mitigation.

## Next consumer brief

Implementors should read `iterations[]` in YAML order; the orchestrator parallelizes I1+I4 in layer 0, I2+I3 in layer 1 (after I1), I5 in layer 2 (after I2+I3+I4). Read `risks[]` BEFORE starting any iteration — the two high-severity risks define a hard scope boundary: **no implementation may modify any file under `backend/app/**` or `backend/tests/**`**. The two cross-iteration invariants not visible in any single `scope_files`:

1. The substring `--cov-fail-under` MUST NOT appear in `.github/workflows/ci.yml` (R4 — coverage gate inherits from `pyproject.toml` `addopts`).
2. `tsc -b` MUST appear as a standalone `run:` line in the frontend job, NOT only inside `npm run build` (R7 — distinct failing step from `vite build`).

The mypy baseline pattern is non-negotiable: every failing module gets a `[[tool.mypy.overrides]] module = '...' ignore_errors = true` entry with a `# debt: G02 mypy baseline` comment — never a `# type: ignore` in source. Same shape for ruff: narrow the lint `select` and extend `ignore`, do not edit source. The test phase will exercise the CI workflow end-to-end on the resulting PR; design-time self-verify only covers static structural checks.
