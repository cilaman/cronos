---
cc_version: '1.0'
agent: pipeline-implementor
slug: g04-fail-closed-auth--i3
phase: impl
status: done
confidence: 0.95
iteration_id: I3
inputs_used:
- .cronos/pipeline/g04-fail-closed-auth/design-report-g04-fail-closed-auth.md
- .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
- backend/app/auth.py
- backend/tests/conftest.py
- backend/tests/test_auth.py
- deploy/upgrade-webhook.py
- Caddyfile.dev
- README.md
outputs_produced:
- .cronos/pipeline/g04-fail-closed-auth/impl-report-g04-fail-closed-auth--i3.md
iterations_executed:
- id: I1
  validation_command: cd backend && pytest tests/test_auth.py -v
  validation_command_passed: true
  notes: 22 tests pass; narrow -k invocation fails --cov-fail-under=60 (expected,
    per project feedback)
- id: I2
  validation_command: cd backend && pytest tests/test_upgrade_webhook.py -v
  validation_command_passed: true
  notes: 5 tests pass; path fixed from parents[3] to parents[2]
- id: I3
  validation_command: grep -q 'BASIC_AUTH_HASH' README.md && grep -q 'CRONOS_BASIC_AUTH_PASSWORD'
    README.md && grep -q 'CRONOS_AUTH_DISABLED' README.md && grep -q 'fail-closed'
    Caddyfile.dev
  validation_command_passed: true
  notes: All four grep checks pass; README auth section added; Caddyfile.dev comment expanded
blockers: []
next_consumer: test
validation_command_passed: true
files_changed:
- backend/app/auth.py
- backend/tests/conftest.py
- backend/tests/test_auth.py
- deploy/upgrade-webhook.py
- backend/tests/test_upgrade_webhook.py
- Caddyfile.dev
- README.md
- backend/tests/api/test_features_board.py
- backend/tests/api/test_features_create.py
- backend/tests/api/test_features_delete.py
- backend/tests/api/test_features_edit.py
- backend/tests/api/test_features_process.py
- backend/tests/api/test_features_read.py
- backend/tests/api/test_features_realize.py
- backend/tests/api/test_features_router_registration.py
- backend/tests/api/test_features_state_transition.py
- backend/tests/test_api_harnesses.py
- backend/tests/test_harness_wiring.py
out_of_scope_findings:
- description: 12 existing test files outside scope_files needed monkeypatch.delenv("CRONOS_AUTH_DISABLED")
    to restore 401 behavior — unforeseen interaction with new conftest autouse fixture.
  location: backend/tests/api/test_features_*.py + test_api_harnesses.py + test_harness_wiring.py
  severity: low
- description: spaces_router and plugins_router confirmed protected via _auth in main.py
    (lines 574, 586); no per-route override present; no code change required.
  location: backend/app/main.py:574,586
  severity: low
metrics:
  tool_calls: 35
  files_read: 22
  memory_hits: 0
  diff_lines_added: 341
  diff_lines_removed: 31
---

## Summary

All three design iterations executed and validated. The fail-closed auth flip is live: `require_auth` now returns HTTP 503 when credentials are unconfigured and `CRONOS_AUTH_DISABLED != "true"`. The webhook secret is mandatory (403 on all requests when unset). Documentation in `README.md` and `Caddyfile.dev` describes the dual-auth architecture and the opt-out contract.

One unforeseen interaction required fixing 12 additional test files (outside the declared scope_files): existing tests that explicitly configure credentials to enable auth were being bypassed by the new conftest `_auth_disabled_by_default` autouse fixture. Each affected fixture was patched with `monkeypatch.delenv("CRONOS_AUTH_DISABLED", raising=False)` before its credential setenv calls.

Full suite result: **2707 passed, 85.18% coverage** (no failures).

## Files changed

### I1 — fail-closed auth.py + conftest/test_auth rewrite

- `backend/app/auth.py` — reordered checks: `CRONOS_AUTH_DISABLED == "true"` first (opt-out), then 503 on unset credentials, then 401 Basic enforcement
- `backend/tests/conftest.py` — added `_auth_disabled_by_default` function-scoped autouse fixture that sets `CRONOS_AUTH_DISABLED=true` so existing tests remain unaffected
- `backend/tests/test_auth.py` — `_clear_auth_env` now also clears `CRONOS_AUTH_DISABLED`; four fail-open tests rewritten to assert 503; added 7 new tests (fail-closed-default, opt-out flag, precedence, false≠disabled, File-Browser route, Plugin route)

### I2 — mandatory webhook secret

- `deploy/upgrade-webhook.py` — extracted `authorized(header_value) -> bool` function; `SECRET=""` / unset → `authorized()` always returns False → 403; startup warning printed when unset
- `backend/tests/test_upgrade_webhook.py` (new) — 5 tests covering: unset secret → not authorized, empty string → not authorized, match → authorized, mismatch → not authorized, case-sensitivity

### I3 — documentation

- `Caddyfile.dev` — comment block expanded to explain fail-closed behavior and `CRONOS_AUTH_DISABLED=true` as the ONLY supported local-dev opt-out
- `README.md` — added **Authentication** section documenting both layers (Caddy bcrypt vs. app plaintext), fail-closed behavior, `CRONOS_AUTH_DISABLED=true` opt-out, and mandatory webhook secret

### Out-of-scope test fixes (unintended regression repairs)

The following files were modified to add `monkeypatch.delenv("CRONOS_AUTH_DISABLED", raising=False)` to fixtures/tests that explicitly enable auth by setting user+password env vars — required because the new conftest autouse otherwise bypasses auth enforcement in those tests:

- `backend/tests/api/test_features_board.py`
- `backend/tests/api/test_features_create.py`
- `backend/tests/api/test_features_delete.py`
- `backend/tests/api/test_features_edit.py`
- `backend/tests/api/test_features_process.py`
- `backend/tests/api/test_features_read.py`
- `backend/tests/api/test_features_realize.py`
- `backend/tests/api/test_features_router_registration.py`
- `backend/tests/api/test_features_state_transition.py`
- `backend/tests/test_api_harnesses.py`
- `backend/tests/test_harness_wiring.py` — also updated `test_harnesses_endpoint_reachable_without_auth_when_auth_disabled` to use `CRONOS_AUTH_DISABLED=true` (it tested the now-removed "no-env-vars = disabled" contract)

## Out-of-scope findings

- The `Caddyfile` (production) uses `BASIC_AUTH_USER`/`BASIC_AUTH_HASH` (bcrypt); these are unrelated to the app-layer credentials and no changes were needed there — confirmed out-of-scope per the design report
- `backend/app/api/spaces.py` and `backend/app/api/plugins.py` confirmed to receive `require_auth` via `_auth` dependency in `main.py` (lines 574, 586) — no per-route override found — no code change required (R4 covered by the new parametrized test in `test_auth.py`)

## Assumptions

- All assumptions from the design report hold; no deviations
- The 12 extra test files touched are a direct consequence of the conftest autouse approach; the design's risk section anticipated the inverse issue (fail-closed breaking protected-endpoint tests) but did not enumerate auth-enabling tests that need the inverse clearing

## Open questions

- None.

## Next consumer brief

Read `iterations_executed[].validation_command_passed` (all true) and `files_changed` list. The test consumer should run `cd backend && pytest tests/ --cov=app --cov-report=term-missing` to confirm 2707 pass / 85%+ coverage. The review consumer should check: (1) that `require_auth` precedence order matches R1–R2; (2) that `authorized()` in the webhook is the sole gate with no SECRET bypass path; (3) that the new conftest autouse and the per-file `delenv` pattern are consistent across all modified test files.
