# Testing Guide

## Backend

### Install dev dependencies

```bash
cd backend && pip install -e ".[dev]"
```

### Run backend tests

```bash
cd backend && pytest tests/ --cov=app --cov-report=term-missing
```

The suite requires 60% coverage (enforced via `--cov-fail-under=60` in `pyproject.toml`).

### Coverage configuration

Coverage settings live in `backend/pyproject.toml` under `[tool.coverage.run]` and
`[tool.coverage.report]`. The source root is `app/`; `app/__init__.py` is omitted.

---

## Frontend

```bash
cd frontend && npm test
```

---

## Test-architect agent

The `test-architect` subagent maintains the test suite, identifies coverage gaps,
writes new tests, and produces structured test reports.

### Space-level run (manual)

Invoke the test-architect on a space to audit and expand coverage across all tasks
in that space:

```
/test-architect
```

from within the space context in the Cronos UI.

### Task-level run (after implementation)

After completing an implementation task, trigger the test-architect to verify
coverage for the changed code:

```
/test-architect <task-id>
```

The agent reads the task brief and recent changes, then writes or updates tests
and runs the suite.

---

## Where results are stored

| Artifact | Location |
|---|---|
| Test reports (JSON) | `{space}/.cronos/test-reports/` |
| Coverage summary | `{space}/.cronos/test-coverage.md` |

Each report is a structured JSON file named `{run-timestamp}.json` containing
pass/fail counts, coverage percentage, and per-file details.

---

## PAT guard test

The test suite includes a guard that scans all **committed** traces in `.cronos/traces/` for secret patterns
(GitHub PATs, tokens, etc.). This test:

- Uses `git ls-files` to find only committed trace files (ephemeral runtime traces are not scanned)
- Fails the suite if any secret patterns are detected in committed traces
- Includes a canary test that verifies the guard correctly detects a realistic PAT

The test operates in two modes:

1. **Production mode** (default): Scans only committed traces via `git ls-files .cronos/traces/`
2. **Canary mode** (`CRONOS_TRACES_DIR` env override): Used by the canary test to verify detection works on synthetic traces

See `backend/tests/test_no_pat_in_traces.py` and `backend/app/trace_redact.py` for implementation details.
