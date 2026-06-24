---
cc_version: '1.0'
agent: pipeline-architect
slug: perf-fix-agent-auth
phase: design
status: done
confidence: 0.9
inputs_used:
- memory:project_g04_fail_closed_auth_impl
- memory:observation_fail_closed_auth_conftest_pattern
- memory:feedback_cronos_task_creation
- .cronos/pipeline/perf-fix-agent-auth/analysis-report-perf-fix-agent-auth.md
- .cronos/pipeline/perf-fix/scout-report-perf-fix.md
- backend/app/auth.py
- backend/tests/test_auth.py
- .claude/skills/create-goal/SKILL.md
- .env.example
- docker-compose.yml
outputs_produced:
- .cronos/pipeline/perf-fix-agent-auth/design-report-perf-fix-agent-auth.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - backend/app/auth.py
  - backend/tests/test_auth.py
  - .claude/skills/create-goal/SKILL.md
  - .env.example
  - docker-compose.yml
  excluded:
  - 'frontend/: backend-only feature — no UI; has_ui=false in analysis'
  - 'backend/app/api/auth.py: does not exist — real path is backend/app/auth.py (analysis
    assumption confirmed)'
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
iterations:
- id: I1
  type: backend
  scope_files:
  - backend/app/auth.py
  - backend/tests/test_auth.py
  validation_command: cd backend && pytest tests/test_auth.py -v
  max_diff_lines: 250
  depends_on: []
- id: I2
  type: infra
  scope_files:
  - .env.example
  - docker-compose.yml
  validation_command: grep -q CRONOS_INTERNAL_TOKEN .env.example && grep -q CRONOS_INTERNAL_TOKEN
    docker-compose.yml
  max_diff_lines: 60
  depends_on: []
- id: I3
  type: infra
  scope_files:
  - .claude/skills/create-goal/SKILL.md
  validation_command: grep -q CRONOS_INTERNAL_TOKEN .claude/skills/create-goal/SKILL.md
    && ! grep -q 'no auth needed on the internal port' .claude/skills/create-goal/SKILL.md
  max_diff_lines: 90
  depends_on: []
risks:
- description: 'FastAPI''s HTTPBasic(auto_error=False) security dependency only parses
    `Authorization: Basic` — a `Bearer` header is silently ignored, so the existing
    `credentials` parameter cannot see the internal token. If the implementor tries
    to read the Bearer token from `credentials` it will always be None and the bypass
    will never fire.'
  severity: high
  mitigation: 'I1 must inject `request: Request` into `require_auth()` and read the
    raw header via `request.headers.get(''authorization'')`, splitting on whitespace
    to extract scheme+token (do NOT rely on the HTTPBasic `credentials` object for
    the Bearer path). The R6 token-match test (Bearer → 200) directly exercises this
    extraction and fails if it is wired through `credentials`.'
- description: 'Check-ordering bug: if the Bearer bypass is placed AFTER the `if not
    user or not (pw_hash or password): raise 503` guard (auth.py:26-28), a deployment
    that configures ONLY CRONOS_INTERNAL_TOKEN (no Basic Auth) returns 503 instead
    of bypassing — defeating the agent use case where containers carry no Basic Auth
    creds.'
  severity: high
  mitigation: I1 must place the Bearer bypass branch immediately after the `CRONOS_AUTH_DISABLED
    == 'true'` early-return (auth.py:15) and BEFORE the 503 credentials-unconfigured
    guard. Add an R6 test where only CRONOS_INTERNAL_TOKEN is set (Basic Auth env
    unset) and a matching Bearer returns 200, proving the bypass precedes the 503
    path.
- description: Empty-string token (`CRONOS_INTERNAL_TOKEN=""`, set but blank) must
    be treated as disabled per R2. A naive `if token == header_token` compare would
    let an attacker pass an empty Bearer token to bypass auth when the var is set-but-blank.
  severity: medium
  mitigation: Guard the bypass with `if token and token.strip():` before any comparison
    so blank/whitespace values are treated as unset; use `hmac.compare_digest` for
    the match. The R2 unset/empty test asserts a Bearer header does NOT short-circuit
    when the var is empty.
- description: 'Env propagation mismatch: `require_auth()` and the agent subprocess
    both read `os.environ`, but if CRONOS_INTERNAL_TOKEN is added only to `.env` (not
    the compose `environment:` block) the dev/out-of-box container may not export
    it to the backend process or its spawned agent children, so the token the agent
    sends will not match the one the server validates.'
  severity: medium
  mitigation: 'I2 adds `CRONOS_INTERNAL_TOKEN: ${CRONOS_INTERNAL_TOKEN:-}` to the
    docker-compose.yml backend `environment:` block (alongside the existing CRONOS_BASIC_AUTH_*
    entries) so the backend process and the agents it spawns as subprocesses share
    one value; `.env.example` documents the var as the single source.'
metrics:
  tool_calls: 14
  files_read: 7
  memory_hits: 3
  iterations_planned: 3
---

## Summary

This design adds an internal service-token bypass to the existing fail-closed Basic Auth in `backend/app/auth.py`: when `CRONOS_INTERNAL_TOKEN` is non-empty and a request carries a matching `Authorization: Bearer <token>` header, `require_auth()` returns immediately; a mismatched token is a hard 401 (no fallthrough to bcrypt), and an unset/empty var disables the bypass entirely. The work splits into three fully-independent iterations (all DAG layer 0): I1 (backend) implements the bypass plus its three branch tests, I2 (infra) documents the var in `.env.example` and threads it through the compose backend `environment:` block, and I3 (infra) rewrites the `create-goal` skill's two `api_post()` helpers to send the Bearer header. The load-bearing tradeoff captured in the risk register is check-ordering: the Bearer branch must run after the `CRONOS_AUTH_DISABLED` early-return but BEFORE the 503 credentials-unconfigured guard, or token-only deployments break.

## Components

### Data
- None — no schema, model, or persistence changes; the token is an environment variable, not stored state.

### Backend
- `backend/app/auth.py` → `require_auth()`: add a `request: Request` parameter and an internal-token bypass branch (constant-time `hmac.compare_digest`) positioned between the `CRONOS_AUTH_DISABLED` early-return and the 503 credentials guard; mismatch raises 401 immediately, no bcrypt fallthrough.
- `backend/tests/test_auth.py`: three new tests following the existing `_clear_auth_env` + `monkeypatch.setenv` pattern — match→200, wrong→401, unset/empty→bypass-disabled (plus a token-only-no-BasicAuth→200 ordering test).
- `docker-compose.yml` backend `environment:` block: `CRONOS_INTERNAL_TOKEN: ${CRONOS_INTERNAL_TOKEN:-}` so the backend process and its spawned agent subprocesses share one value.
- `.env.example`: documented `CRONOS_INTERNAL_TOKEN=` line in the auth section with generation instructions and the fail-closed note.
- `.claude/skills/create-goal/SKILL.md`: remove the stale "no auth needed on the internal port" claim; both `api_post()` helpers send `Authorization: Bearer ${CRONOS_INTERNAL_TOKEN}` and raise if the var is absent.

## Implementation plan

| ID  | Type  | Depends on | Scope files (abridged)                                   | Validation                                                                 |
|-----|-------|------------|----------------------------------------------------------|----------------------------------------------------------------------------|
| I1  | backend | -        | backend/app/auth.py, backend/tests/test_auth.py          | cd backend && pytest tests/test_auth.py -v                                 |
| I2  | infra   | -        | .env.example, docker-compose.yml                         | grep -q CRONOS_INTERNAL_TOKEN .env.example && grep -q … docker-compose.yml  |
| I3  | infra   | -        | .claude/skills/create-goal/SKILL.md                      | grep -q CRONOS_INTERNAL_TOKEN … && ! grep -q 'no auth needed on the internal port' … |

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| HTTPBasic(auto_error=False) ignores `Bearer` — the bypass never fires if read via `credentials` | high | I1 injects `request: Request` and reads the raw `authorization` header; R6 match-test exercises it |
| Bearer branch placed after the 503 guard breaks token-only (no Basic Auth) deployments | high | Place bypass after `CRONOS_AUTH_DISABLED` return, before the 503 guard; add token-only→200 test |
| `CRONOS_INTERNAL_TOKEN=""` (set but blank) could be used to bypass | medium | Guard with `if token and token.strip():` + `hmac.compare_digest`; R2 test asserts fallthrough |
| Token not exported to backend/agent subprocess if only in `.env` | medium | I2 adds it to compose `environment:` block; `.env.example` is the documented source |

## Assumptions

- **Real path is `backend/app/auth.py`** (not `backend/app/api/auth.py` from the brief) — confirmed by Read; the analysis assumption holds.
- **Agents inherit the backend container env** — agents run as subprocesses of the backend (per `agent.py`), so a single `CRONOS_INTERNAL_TOKEN` in the compose backend `environment:` block reaches both `require_auth()` and the agent's `os.environ`; no per-workspace env mounting is needed.
- **Tests live in the existing `backend/tests/test_auth.py`** alongside the G04 tests, reusing the autouse `_clear_auth_env` fixture (it `delenv`s `CRONOS_AUTH_DISABLED`, so auth is active); new tests add `monkeypatch.setenv("CRONOS_INTERNAL_TOKEN", …)`.
- **Bundling source + tests in I1 is intentional** — the bypass logic (R1/R2/R3) and its branch tests (R6) are tightly coupled and share one `validation_command`; splitting them would force a serial dependency for no benefit.
- **docker-compose.yml IS in scope** — though the analysis flagged it as possibly unnecessary, the env-propagation risk makes the compose `environment:` entry the load-bearing wiring for the dev/out-of-box path; I2 includes it.

## Open questions

- None. (The two analysis open questions are resolved: docker-compose.yml gets the `${CRONOS_INTERNAL_TOKEN:-}` pass-through entry — no hardcoded dev default, keeping fail-closed; the Verify-section `curl` example update is left as the analyst's deferred follow-up, out of these scope files.)

## Next consumer brief

Read `iterations[]`, each `scope_files`, and `validation_command` first; the DAG is flat — I1/I2/I3 are all layer 0 and parallelizable.

Cross-iteration invariants NOT derivable from the YAML:
- The env var name is **exactly** `CRONOS_INTERNAL_TOKEN` and the header is **exactly** `Authorization: Bearer <token>` — I1 (validation), I2 (docs/compose), and I3 (skill helpers) must all use these literal strings or the round-trip breaks.
- **Check order in `require_auth()` is load-bearing** (risk #2): Bearer bypass goes after the `CRONOS_AUTH_DISABLED == "true"` early-return and BEFORE the `raise 503` credentials-unconfigured guard.
- I1 must read the token from `request.headers` (inject `Request`), NOT from the `HTTPBasic` `credentials` object (risk #1), and compare with `hmac.compare_digest` after an `if token and token.strip():` guard (risk #3).
