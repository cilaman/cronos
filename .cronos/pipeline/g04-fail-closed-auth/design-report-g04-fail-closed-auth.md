---
cc_version: '1.0'
agent: pipeline-architect
slug: g04-fail-closed-auth
phase: design
status: done
confidence: 0.9
inputs_used:
- memory:pipeline-architect-cc-v1
- .cronos/pipeline/g04-fail-closed-auth/analysis-report-g04-fail-closed-auth.md
- .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
- backend/app/auth.py
- deploy/upgrade-webhook.py
- backend/app/main.py
- backend/tests/test_auth.py
- backend/tests/conftest.py
outputs_produced:
- .cronos/pipeline/g04-fail-closed-auth/design-report-g04-fail-closed-auth.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - backend/app/auth.py
  - backend/app/main.py
  - backend/tests/conftest.py
  - backend/tests/test_auth.py
  - deploy/upgrade-webhook.py
  - Caddyfile.dev
  excluded:
  - 'frontend/: has_ui=false; no UI changes in G04'
  - 'Caddyfile: edge bcrypt config already correct, out of scope'
  - 'backend/app/api/spaces.py, backend/app/api/plugins.py: confirmed registered under
    _auth in main.py (lines 577, 586); no per-route override, no code change'
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
iterations:
- id: I1
  type: backend
  scope_files:
  - backend/app/auth.py
  - backend/tests/conftest.py
  - backend/tests/test_auth.py
  validation_command: cd backend && pytest tests/test_auth.py -v
  max_diff_lines: 320
  depends_on: []
- id: I2
  type: backend
  scope_files:
  - deploy/upgrade-webhook.py
  - backend/tests/test_upgrade_webhook.py
  validation_command: cd backend && pytest tests/test_upgrade_webhook.py -v
  max_diff_lines: 220
  depends_on: []
- id: I3
  type: infra
  scope_files:
  - README.md
  - Caddyfile.dev
  validation_command: grep -q 'BASIC_AUTH_HASH' README.md && grep -q 'CRONOS_BASIC_AUTH_PASSWORD'
    README.md && grep -q 'CRONOS_AUTH_DISABLED' README.md && grep -q 'fail-closed'
    Caddyfile.dev
  max_diff_lines: 200
  depends_on:
  - I1
risks:
- description: 'Making require_auth fail-closed breaks the ENTIRE pytest suite: conftest.py''s
    async_client fixture sets no auth env vars, so every existing test hitting a protected
    endpoint (test_tasks, test_spaces, plugins, etc. — thousands of assertions) would
    receive 503 instead of 200/404.'
  severity: critical
  mitigation: I1 scope_files includes backend/tests/conftest.py. Add a function-scoped
    autouse fixture that sets CRONOS_AUTH_DISABLED=true as the suite-wide default
    so all non-auth tests keep their 200/404 expectations. test_auth.py's _clear_auth_env
    fixture must additionally monkeypatch.delenv('CRONOS_AUTH_DISABLED') so the auth-specific
    tests exercise the real fail-closed/enabled logic. Validation_command runs the
    full test_auth.py file to confirm both directions.
- description: The four existing fail-OPEN tests in test_auth.py (test_protected_endpoint_returns_200_when_auth_disabled
    L159, test_auth_disabled_when_only_user_env_set L171, test_auth_disabled_when_only_password_env_set
    L183, test_auth_disabled_when_user_env_empty_string L194) encode the OLD contract
    (unset/partial creds => 200) and will fail under fail-closed behavior.
  severity: high
  mitigation: 'I1 implementor must REWRITE these four tests: unset/partial-credential
    cases now assert 503; a new test sets CRONOS_AUTH_DISABLED=true and asserts the
    request succeeds (200). This is in-scope because test_auth.py is an I1 scope_file.'
- description: 'CRONOS_AUTH_DISABLED precedence ambiguity: if the disabled-check runs
    AFTER the credential check, setting CRONOS_AUTH_DISABLED=true while creds are
    also set could still enforce auth, contradicting R2 (''the only permissible way
    to disable auth'').'
  severity: medium
  mitigation: 'Specify exact ordering in require_auth: check `os.environ.get(''CRONOS_AUTH_DISABLED'')
    == ''true''` FIRST and return immediately; only then read credentials and apply
    the 503 fail-closed branch. Strict string equality (''true'') per R2 — any other
    value falls through to enforcement.'
- description: The upgrade webhook script deploy/upgrade-webhook.py has a hyphen in
    its filename and lives outside the importable app package, making the secret-check
    logic awkward to unit test.
  severity: medium
  mitigation: 'I2 extracts the secret comparison into a module-level pure function
    (e.g. `authorized(header_value)`), then the new backend/tests/test_upgrade_webhook.py
    loads the script via importlib.util.spec_from_file_location and asserts: secret
    unset => not authorized (403 path); secret set + matching header => authorized;
    secret set + wrong header => not authorized.'
metrics:
  tool_calls: 13
  files_read: 7
  memory_hits: 1
  iterations_planned: 3
---

## Summary

G04 closes three fail-open authentication holes with a deliberately minimal, three-iteration plan. The load-bearing change is a ~6-line edit to `require_auth` in `backend/app/auth.py` (I1) that returns HTTP 503 when `CRONOS_BASIC_AUTH_USER`/`CRONOS_BASIC_AUTH_PASSWORD` are unconfigured and `CRONOS_AUTH_DISABLED != "true"`. The non-obvious cost — captured as the critical risk — is that this fail-closed flip would break the whole pytest suite, so I1 also adds a `CRONOS_AUTH_DISABLED=true` session default to `conftest.py` and rewrites the four fail-open tests in `test_auth.py`. I2 makes the upgrade-webhook secret mandatory (runtime 403 when unset) and adds the missing test; I3 documents the dual-auth architecture in README + `Caddyfile.dev`. The DAG is wide: I1 and I2 run in parallel (group 0); I3 (docs) depends only on I1 so it describes the final opt-out name accurately.

## Components

### Data
- (none) — G04 is auth plumbing; no schema or model changes.

### Backend
- `require_auth` (`backend/app/auth.py`): reorder to check `CRONOS_AUTH_DISABLED == "true"` first (explicit opt-out), then fail closed with HTTP 503 when credentials are unconfigured, then enforce Basic Auth (401) as today.
- `conftest.py` autouse fixture (`backend/tests/conftest.py`): set `CRONOS_AUTH_DISABLED=true` as the suite-wide default so the fail-closed flip does not regress the ~thousands of existing endpoint assertions.
- `test_auth.py` (`backend/tests/test_auth.py`): clear `CRONOS_AUTH_DISABLED` per-test; rewrite the four fail-open tests to assert 503; add fail-closed-default, explicit-opt-out, and File-Browser/Plugin-route coverage (R3, R4).
- `upgrade-webhook.py` (`deploy/upgrade-webhook.py`): extract a `authorized(header)` function; make the secret check unconditional so a missing/empty `WEBHOOK_SECRET` yields 403 (never silent allow); log a startup warning when unset.
- `test_upgrade_webhook.py` (`backend/tests/test_upgrade_webhook.py`, new): importlib-load the script and assert the mandatory-secret behavior across unset / matching / mismatched cases (R5).

## Implementation plan

| ID  | Type    | Depends on | Scope files (abridged)                                              | Validation                                              |
|-----|---------|------------|--------------------------------------------------------------------|--------------------------------------------------------|
| I1  | backend | -          | backend/app/auth.py, backend/tests/conftest.py, backend/tests/test_auth.py | cd backend && pytest tests/test_auth.py -v             |
| I2  | backend | -          | deploy/upgrade-webhook.py, backend/tests/test_upgrade_webhook.py    | cd backend && pytest tests/test_upgrade_webhook.py -v   |
| I3  | infra   | I1         | README.md, Caddyfile.dev                                            | grep -q 'BASIC_AUTH_HASH' README.md && grep -q 'CRONOS_BASIC_AUTH_PASSWORD' README.md && grep -q 'CRONOS_AUTH_DISABLED' README.md && grep -q 'fail-closed' Caddyfile.dev |

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Fail-closed flip breaks the entire pytest suite (async_client sets no auth env → all protected endpoints 503) | critical | I1 adds `CRONOS_AUTH_DISABLED=true` autouse default in conftest.py; test_auth.py clears it per-test |
| Four existing fail-open tests in test_auth.py encode the old contract and will fail | high | I1 rewrites them: unset/partial creds → assert 503; new opt-out test asserts 200 |
| CRONOS_AUTH_DISABLED precedence ambiguity vs credential check | medium | require_auth checks `== "true"` FIRST and returns; strict string match per R2 |
| Webhook script (hyphenated filename, outside app package) is awkward to test | medium | I2 extracts `authorized(header)`; test loads it via importlib.util.spec_from_file_location |

## Assumptions

- The opt-out variable name is `CRONOS_AUTH_DISABLED` and the bypass value is the exact string `"true"` — taken verbatim from the analysis report (R2) and the remediation plan; the architect adopts it as the implementation target without re-deriving.
- The unconfigured-credentials status code is **503** (not 401), per R1's explicit "must return HTTP 503" and the analyst decision note (503 signals misconfiguration, not bad credentials, and avoids a spurious browser login dialog).
- The webhook fix uses **runtime-reject (403)** rather than startup-exit: the webhook is a long-running host service, and an in-process 403 is directly testable and avoids breaking the deploy bootstrap if the secret is briefly absent. An optional startup warning log is added but the process still binds.
- `spaces_router` and `plugins_router` are already registered with `dependencies=_auth` in `main.py` (confirmed lines 577, 586) and neither `api/spaces.py` nor `api/plugins.py` adds a per-route `dependencies=` override — so R4 needs **test coverage only**, no routing code change.
- The conftest autouse fixture runs before test_auth.py's module-level `_clear_auth_env` fixture (conftest-scope autouse precedes module-scope autouse), so the per-test delenv reliably wins inside test_auth.py.

## Open questions

- None.

## Next consumer brief

Read `iterations[]`, `iterations[].scope_files`, `iterations[].validation_command`, and `risks[]` from the YAML — they are the source of truth.

Cross-iteration invariants not derivable from the YAML:
- **Opt-out contract (I1):** `require_auth` must check `os.environ.get("CRONOS_AUTH_DISABLED") == "true"` FIRST (strict string), return on match; THEN fail closed with `HTTPException(status_code=503)` when `CRONOS_BASIC_AUTH_USER` or `CRONOS_BASIC_AUTH_PASSWORD` is missing/empty; THEN the existing 401 Basic-Auth enforcement. The literal var name `CRONOS_AUTH_DISABLED` and value `"true"` must match between auth.py, conftest.py, test_auth.py, and the README/Caddyfile.dev docs (I3).
- **conftest is load-bearing (I1):** the suite-wide `CRONOS_AUTH_DISABLED=true` default MUST land in the same iteration as the auth.py flip, or every other test file regresses — do not split it out.
- **Webhook seam (I2):** extract `authorized(header_value) -> bool` so the new test can importlib-load `deploy/upgrade-webhook.py` (hyphenated, non-package path) without spawning a socket.
- I3 depends on I1 only so the documented opt-out name matches the implemented one; it touches no auth.py code (README + Caddyfile.dev text only) to avoid a same-file collision with I1.
