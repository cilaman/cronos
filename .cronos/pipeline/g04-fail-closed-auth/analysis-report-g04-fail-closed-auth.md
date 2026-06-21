---
cc_version: '1.0'
agent: pipeline-analyst
slug: g04-fail-closed-auth
phase: analysis
status: done
confidence: 0.95
inputs_used:
- memory:pipeline-analyst-cc-v1-agent
- memory:cc-v1-contract-module
- .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
- .cronos/workspaces/2026-06-20-1427-create-remedy-goals/REMEDIATION-PLAN.md
- backend/app/auth.py
- Caddyfile
- Caddyfile.dev
- deploy/upgrade-webhook.py
- backend/app/main.py
outputs_produced:
- .cronos/pipeline/g04-fail-closed-auth/analysis-report-g04-fail-closed-auth.md
blockers: []
next_consumer: design
request: 'G04: Fail-closed auth + reconcile dual-auth + mandatory webhook secret.
  Fixes three fail-open authentication issues. After: Default (unset) config → unauthenticated
  request returns 401/503, not 200. Disabling auth requires explicit CRONOS_AUTH_DISABLED=true;
  an integration test asserts fail-closed behavior. File Browser and Plugin API routes
  are protected by the same auth dependency. Webhook rejects when WEBHOOK_SECRET is
  unset. The unauthenticated-file-read risk on default deployments is eliminated.'
has_ui: false
coverage_summary:
  searched:
  - backend/app/auth.py (lines 12–23, complete)
  - Caddyfile (lines 1–46, complete)
  - Caddyfile.dev (lines 1–35, complete)
  - deploy/upgrade-webhook.py (lines 1–63, complete)
  - backend/app/main.py (router registration, grep)
  - backend/app/api/spaces.py (import header, grep — confirm no direct auth override)
  - backend/app/api/plugins.py (import header, grep — confirm no direct auth override)
  excluded:
  - frontend/: no UI changes required; auth is backend-only
  - backend/app/api/tasks.py: already wired via _auth; not in G04 scope
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
traceability:
- requirement_id: R1
  statement: 'The `require_auth` dependency in `backend/app/auth.py` must fail closed:
    when `CRONOS_BASIC_AUTH_USER` or `CRONOS_BASIC_AUTH_PASSWORD` env vars are unset
    AND `CRONOS_AUTH_DISABLED` is not `"true"`, the function must return HTTP 503
    (not silently allow the request).'
  acceptance_criteria:
  - Given CRONOS_BASIC_AUTH_USER and CRONOS_BASIC_AUTH_PASSWORD are both unset and
    CRONOS_AUTH_DISABLED is absent, when any protected endpoint receives a request,
    then the response status is 503 (not 200 or 404).
  - 'The current lines 15–16 (`if not user or not password: return`) are replaced;
    the silent-allow path is removed.'
  verifying_phase: test
  confidence: 0.98
- requirement_id: R2
  statement: An explicit opt-out environment variable `CRONOS_AUTH_DISABLED=true`
    bypasses authentication — when set, `require_auth` returns without enforcing credentials.
    This is the only permissible way to disable auth.
  acceptance_criteria:
  - Given CRONOS_AUTH_DISABLED=true, when an unauthenticated request arrives at a
    protected endpoint, then the response is not 401/503.
  - Setting any value other than `"true"` for CRONOS_AUTH_DISABLED does NOT disable
    auth (strict string match).
  - The opt-out is documented in a code comment and in the README/CLAUDE.md dev section.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R3
  statement: 'An integration test verifies the fail-closed default: without any auth-related
    env vars set, an unauthenticated request to a protected endpoint returns 401 or
    503.'
  acceptance_criteria:
  - A test in `backend/tests/` patches the env to clear CRONOS_BASIC_AUTH_USER, CRONOS_BASIC_AUTH_PASSWORD,
    and CRONOS_AUTH_DISABLED, then asserts that GET /api/spaces returns 401 or 503.
  - A complementary test sets CRONOS_AUTH_DISABLED=true and asserts the request succeeds
    (200/other non-4xx).
  - Both tests are green in the existing pytest suite with no --override-ini hacks
    (they hit real auth logic, not mocks).
  verifying_phase: test
  confidence: 0.95
- requirement_id: R4
  statement: The File Browser API routes (`GET /api/spaces/{id}/files` and `GET /api/spaces/{id}/files/{file_path}`)
    and the Plugin Management API routes (`/api/plugins/*`) remain under the existing
    `require_auth` dependency registered in `backend/app/main.py` lines 574 and 586
    — no new routing exception bypasses them.
  acceptance_criteria:
  - After the fix, GET /api/spaces/{id}/files with no credentials and no CRONOS_AUTH_DISABLED
    returns 401/503 (not 200 or file content).
  - After the fix, GET /api/plugins with no credentials and no CRONOS_AUTH_DISABLED
    returns 401/503.
  - No new `dependencies=[]` override or `include_router` without `_auth` is introduced
    for spaces_router or plugins_router.
  verifying_phase: test
  confidence: 0.98
- requirement_id: R5
  statement: 'The upgrade webhook in `deploy/upgrade-webhook.py` must make `WEBHOOK_SECRET`
    mandatory: if the env var is unset or empty at startup, the server either refuses
    to start (exit 1) or rejects every `/upgrade` request with 403.'
  acceptance_criteria:
  - Given WEBHOOK_SECRET is unset or empty, when a POST /upgrade arrives, then the
    response is 403 (forbidden) with no script execution.
  - The current `if SECRET:` guard (line 33) is replaced — the check is unconditional.
  - 'Optionally: if WEBHOOK_SECRET is unset at startup, the process logs an error
    and exits before binding the socket.'
  verifying_phase: test
  confidence: 0.95
- requirement_id: R6
  statement: The dual-auth architecture is documented clearly — code comments or a
    README section explains that Caddy uses `BASIC_AUTH_USER`/`BASIC_AUTH_HASH` (bcrypt,
    edge layer) and the FastAPI app uses `CRONOS_BASIC_AUTH_USER`/`CRONOS_BASIC_AUTH_PASSWORD`
    (plaintext compare, defense-in-depth layer), and how they interact in prod vs
    dev.
  acceptance_criteria:
  - A comment block in `backend/app/auth.py` or an updated README section states both
    env var families, their respective layers, and the CRONOS_AUTH_DISABLED escape
    hatch.
  - Caddyfile.dev comment is updated to reflect that the FastAPI layer is now fail-closed
    (not 'disabled when unset — default for dev').
  verifying_phase: review
  confidence: 0.9
metrics:
  tool_calls: 16
  files_read: 8
  memory_hits: 2
---

## Summary

G04 fixes three concrete fail-open authentication vulnerabilities introduced by the combination of a new File Browser API (arbitrary workspace file reads) and the existing fail-open auth design. The primary change is a 3-line edit to `backend/app/auth.py` (lines 12–23) making the `require_auth` FastAPI dependency fail closed by default, with a mandatory `CRONOS_AUTH_DISABLED=true` opt-out for dev. The secondary change is making the upgrade webhook secret non-optional in `deploy/upgrade-webhook.py` (line 33). The tertiary deliverable is documentation of the dual-auth architecture (Caddy + FastAPI) so operators understand both layers. No new routes require wiring — the File Browser and Plugin API routers are already registered under `_auth` in `main.py` (lines 574, 586); the fail-open bug is the only gap.

## Scope

### In scope
- Change `require_auth` in `backend/app/auth.py` to return HTTP 503 when credentials are unconfigured and `CRONOS_AUTH_DISABLED` is not `"true"`
- Add `CRONOS_AUTH_DISABLED=true` opt-out for local dev (replaces the current implicit fail-open)
- Integration tests for fail-closed default, opt-out, and credential mismatch cases
- Change upgrade webhook to require `WEBHOOK_SECRET` unconditionally (fail 403 or refuse to start)
- Document dual-auth architecture (Caddy layer vs FastAPI layer) in auth.py and/or README

### Out of scope
- Changing the Caddy basicauth config (already correct; Caddyfile is not broken)
- Changing the HTTP Basic Auth comparison algorithm (plaintext compare in auth.py is acceptable for defense-in-depth; Caddy handles bcrypt at the edge)
- Adding new UI components or frontend routes
- Rotating or changing credential values (operator concern, not code)

### Deferred
- Merging the two credential families into one (e.g. backing the FastAPI layer with bcrypt too) — this would require a new password-hashing dependency and a migration story; not required for fail-closed
- Rate-limiting or brute-force protection on the FastAPI Basic Auth endpoint — future P3 hardening
- HTTPS enforcement at the FastAPI layer (currently Caddy's responsibility)

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | `require_auth` returns 503 when env vars are unset (no more silent allow) |
| R2 | `CRONOS_AUTH_DISABLED=true` is the only permissible way to disable auth |
| R3 | Integration test asserts fail-closed default and opt-out behavior |
| R4 | File Browser and Plugin API routes remain under the existing `require_auth` dependency |
| R5 | Upgrade webhook requires `WEBHOOK_SECRET`; rejects with 403 if unset |
| R6 | Dual-auth architecture (Caddy + FastAPI) is documented clearly |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (machine-readable source of truth). Summary:

- R1 — `if not user or not password: return` replaced; HTTP 503 returned when credentials unconfigured
- R2 — `CRONOS_AUTH_DISABLED=true` (strict string) is the escape hatch; any other value still enforces auth
- R3 — Test clears all auth env vars → asserts 401/503; complementary test sets opt-out → asserts success
- R4 — File Browser (`/api/spaces/{id}/files`) and Plugin (`/api/plugins/*`) return 401/503 without credentials
- R5 — Webhook 403 when `WEBHOOK_SECRET` empty; `if SECRET:` guard replaced with unconditional check
- R6 — Comment or README section documents `BASIC_AUTH_USER`/`BASIC_AUTH_HASH` (Caddy) vs `CRONOS_BASIC_AUTH_*` (FastAPI)

## Traceability

The full requirement → acceptance criteria → verifying_phase map is the YAML `traceability[]` array.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | `require_auth` returns 503 when env vars are unset (no silent allow) |
| R2 | test | `CRONOS_AUTH_DISABLED=true` is the only permissible way to disable auth |
| R3 | test | Integration test asserts fail-closed default and opt-out behavior |
| R4 | test | File Browser and Plugin API remain under `require_auth`; no bypass introduced |
| R5 | test | Upgrade webhook requires `WEBHOOK_SECRET`; rejects 403 when unset |
| R6 | review | Dual-auth architecture documented (Caddy + FastAPI layers, env var families) |

## Assumptions

- `has_ui: false` rationale: G04 is backend auth plumbing only; File Browser and Plugin UI already exist; no new screens, forms, or visual state are required.
- The FastAPI app's plaintext `hmac.compare_digest` (auth.py line 19) is intentional for defense-in-depth behind Caddy's bcrypt; this is a conscious design choice documented in Review 1. No change to the comparison algorithm is in scope.
- `CRONOS_AUTH_DISABLED` is the agreed opt-out name — the remediation plan text specifies "explicit, loud opt-out (`CRONOS_AUTH_DISABLED=true`)" verbatim. The analyst adopts this name as the implementation target.
- Both `spaces_router` (line 574) and `plugins_router` (line 586) are confirmed registered under `_auth` in `main.py`; no wiring change is needed for R4 — only the fail-open bug in `require_auth` itself must be fixed.
- The upgrade webhook fix (R5) targets `deploy/upgrade-webhook.py` only; the host systemd service is out of scope for this goal.
- Scout confidence 0.92 (done); no upper-bound constraint on analyst confidence.

## Open questions

- None.

## Next consumer brief

**Design agent should read:** `traceability[]` (6 requirements), `has_ui: false` (no frontend work), `## Scope` (dual-auth doc is in scope; bcrypt change is out of scope).

**Decision points for the design agent:**
1. **R5 webhook — startup-exit vs runtime-reject?** Two valid options: (a) log error + `sys.exit(1)` before `server.serve_forever()` if `SECRET` is empty; (b) keep the server running but always 403 if `SECRET` is empty. Option (a) is safer (fails loudly at deploy time); option (b) is more lenient (lets the service start but protects the endpoint). The design should pick one and defend it.
2. **R1 status code — 503 vs 401?** The remediation plan says "401/503"; 503 ("Service Unavailable — auth not configured") better communicates misconfiguration rather than bad credentials; 401 would prompt a browser login dialog. The design should standardize on one.
3. **Test scope:** R3 tests need to patch environment variables at the FastAPI dependency level (using `monkeypatch` or `unittest.mock.patch.dict`); the design should confirm this is compatible with the existing `AsyncClient`-based test harness in `backend/tests/conftest.py`.
4. **Scope boundary:** Only `backend/app/auth.py` and `deploy/upgrade-webhook.py` require code changes. The design DAG can be minimal: (I1) auth.py fix + tests, (I2) webhook fix + test, (I3) docs.
