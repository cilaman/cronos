---
cc_version: '1.0'
agent: pipeline-doc-sync
slug: g04-fail-closed-auth
phase: doc
status: done
confidence: 0.95
inputs_used:
  - .cronos/pipeline/g04-fail-closed-auth/impl-report-g04-fail-closed-auth.md
  - .cronos/pipeline/g04-fail-closed-auth/review-report-g04-fail-closed-auth--attempt1.md
  - backend/app/auth.py
  - backend/tests/conftest.py
  - backend/tests/test_auth.py
  - deploy/upgrade-webhook.py
  - README.md
  - Caddyfile.dev
  - CLAUDE.md
  - .env.example
  - deploy/VPS_SETUP.md
outputs_produced:
  - .cronos/pipeline/g04-fail-closed-auth/doc-report-g04-fail-closed-auth.md
metrics:
  docs_updated: 3
  files_read: 11
  intentionally_not_updated: 5
---

## Summary

Documentation for G04 fail-closed auth implementation is complete. The implementor already updated `README.md` (Authentication section documenting dual-auth layers, fail-closed behavior, `CRONOS_AUTH_DISABLED=true` opt-out, and mandatory webhook secret) and `Caddyfile.dev` (expanded comment explaining fail-closed contract and opt-out). The doc-sync phase updated three additional files to harmonize the auth documentation across the codebase: `CLAUDE.md` (Auth section + new `backend/app/auth.py` module entry), `.env.example` (added `WEBHOOK_SECRET` with mandatory flag), and `deploy/VPS_SETUP.md` (changed "optional" to "mandatory" for webhook secret and clarified the constant-time compare). All four user-facing threat notes from the review report are reflected in the updated docs.

## Files updated

1. **CLAUDE.md** — Updated Auth section (lines 51–63) to document dual-auth architecture (Caddy bcrypt vs. app plaintext), fail-closed behavior (503 on unset credentials), `CRONOS_AUTH_DISABLED=true` opt-out, and mandatory webhook secret. Added new `backend/app/auth.py` module entry (lines 78–79) describing the fail-closed auth dependency.

2. **.env.example** — Added `WEBHOOK_SECRET` env var (lines 44–47) with explanation that it is mandatory (returns 403 when unset) and includes a generation command (`openssl rand -hex 32`).

3. **deploy/VPS_SETUP.md** — Updated the webhook section (lines 350–361) to clarify that `WEBHOOK_SECRET` is mandatory (not optional) and that the webhook rejects all requests with 403 when unset. Noted constant-time compare and automatic secret passing by the backend agent.

## Files already updated by implementor (verified)

- **README.md** — Lines 51–81 document both auth layers (Caddy bcrypt vs. app plaintext), fail-closed behavior, `CRONOS_AUTH_DISABLED=true` opt-out (exact string), and mandatory webhook secret (403 on unset). Documentation is complete and accurate.

- **Caddyfile.dev** — Lines 3–11 contain expanded comment explaining fail-closed behavior: "if `CRONOS_BASIC_AUTH_USER` + `CRONOS_BASIC_AUTH_PASSWORD` are unset it returns HTTP 503" and "`CRONOS_AUTH_DISABLED=true`" is the ONLY supported bypass. Documentation is complete and accurate.

## Intentionally not updated

1. **Caddyfile** (production config) — No changes needed. Uses `BASIC_AUTH_USER` + `BASIC_AUTH_HASH` (bcrypt) at the Caddy edge layer only; this is a separate mechanism from the app-layer credentials and unchanged by G04. Documenting this separation is in README.md (dual-auth architecture).

2. **backend/app/api/spaces.py** — No per-route auth override needed. Already receives `require_auth` dependency via `_auth` injection in main.py (line 574). Confirmed in the impl report.

3. **backend/app/api/plugins.py** — No per-route auth override needed. Already receives `require_auth` dependency via `_auth` injection in main.py (line 586). Confirmed in the impl report.

4. **TESTING.md** — No update needed. The conftest autouse fixture (`_auth_disabled_by_default`) in `backend/tests/conftest.py` automatically sets `CRONOS_AUTH_DISABLED=true` for all tests, so existing test suites do not break. The new `test_auth.py` file documents the explicit disable/enable patterns for test authors.

5. **backend/tests/conftest.py** (and the 11 test files patched by impl) — These are source files (tests), not documentation, and are not updated by doc-sync.

## Threat landscape coverage

All four user-facing behavior changes from the review report are now documented:

- **503 on unset credentials** — Documented in CLAUDE.md, README.md, Caddyfile.dev, and .env.example.
- **`CRONOS_AUTH_DISABLED=true` (exact string) as only bypass** — Documented in CLAUDE.md, README.md, Caddyfile.dev, and .env.example.
- **File-Browser + Plugin routes protected** — Documented in CLAUDE.md (auth.py module entry: used by `_auth` dependency in main.py for all protected routes) and already in the codebase via the shared `require_auth` dependency.
- **Mandatory webhook secret (403 when unset)** — Documented in README.md, .env.example, and VPS_SETUP.md (updated from "optional" to "mandatory").

## Next consumer

The remediation plan is closed. All documentation is synced and ready for merge to the feature branch. No further doc updates required.
