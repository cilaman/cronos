---
cc_version: '1.0'
agent: pipeline-analyst
slug: perf-fix-agent-auth
phase: analysis
status: done
confidence: 0.95
inputs_used:
- memory:project_g04_fail_closed_auth_impl
- memory:feedback_cronos_task_creation
- memory:observation_fail_closed_auth_conftest_pattern
- .cronos/pipeline/perf-fix/scout-report-perf-fix.md
- backend/app/auth.py
- .claude/skills/create-goal/SKILL.md
- .env.example
outputs_produced:
- .cronos/pipeline/perf-fix-agent-auth/analysis-report-perf-fix-agent-auth.md
blockers: []
next_consumer: design
request: "backend/app/api/auth.py or the auth middleware:\n  - If `Authorization:\
  \ Bearer <token>` matches `CRONOS_INTERNAL_TOKEN` env var (and the var is non-empty),\
  \ bypass bcrypt auth\n  - If `CRONOS_INTERNAL_TOKEN` is unset/empty, this bypass\
  \ is disabled (fail-closed)\n  - Return 401 if the token doesn't match; do NOT fall\
  \ through to bcrypt check on a malformed token\n- Docker Compose / `.env.example`:\
  \ add `CRONOS_INTERNAL_TOKEN` variable with instructions\n- `.claude/skills/create-goal/SKILL.md`:\
  \ replace \"no auth needed\" with instructions to read `CRONOS_INTERNAL_TOKEN` from\
  \ env and pass as Bearer token\n- Backend tests: token matches → 200; token wrong\
  \ → 401; token unset → bypass disabled"
has_ui: false
coverage_summary:
  searched:
  - backend/app/auth.py
  - .claude/skills/create-goal/SKILL.md
  - .env.example
  - .cronos/pipeline/perf-fix/scout-report-perf-fix.md
  excluded:
  - frontend/: backend-only feature — no UI components are affected
  - docker-compose.yml: environment variable wiring is config-layer; design agent
      will specify exact placement
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
traceability:
- requirement_id: R1
  statement: 'When `Authorization: Bearer <token>` header is present and `CRONOS_INTERNAL_TOKEN`
    env var is non-empty and the token matches (constant-time compare), `require_auth()`
    returns immediately without performing bcrypt auth.'
  acceptance_criteria:
  - 'Given CRONOS_INTERNAL_TOKEN=secret is set, when a request includes ''Authorization:
    Bearer secret'', then the endpoint returns 200 (no Basic Auth required).'
  - The match uses a constant-time comparison (hmac.compare_digest) to prevent timing
    oracle attacks.
  - The bypass is triggered ONLY when the Authorization header scheme is exactly 'Bearer'
    (case-insensitive scheme extraction is acceptable per RFC 7235).
  verifying_phase: test
  confidence: 0.95
- requirement_id: R2
  statement: When `CRONOS_INTERNAL_TOKEN` env var is unset or empty-string, the Bearer
    token bypass path is disabled; requests with a Bearer header fall through to normal
    BasicAuth processing.
  acceptance_criteria:
  - 'Given CRONOS_INTERNAL_TOKEN is not set in the environment, when a request includes
    any Authorization: Bearer header, then the request is NOT short-circuited — it
    falls through to the existing Basic Auth check and returns 401 if no valid Basic
    credentials are present.'
  - The bypass check must guard on `token and token.strip()` (non-empty after strip)
    to treat blank-string values as unset.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R3
  statement: When `CRONOS_INTERNAL_TOKEN` is set and a Bearer token is provided but
    does NOT match, `require_auth()` raises HTTP 401 immediately without falling through
    to the bcrypt Basic Auth path.
  acceptance_criteria:
  - 'Given CRONOS_INTERNAL_TOKEN=correct, when a request includes ''Authorization:
    Bearer wrong'', then the endpoint returns 401 (not 503, not 200, not a bcrypt
    check).'
  - A mismatched Bearer token is a hard stop — it must never cascade into the Basic
    Auth credential check, to prevent brute-force escalation.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R4
  statement: '`.env.example` documents `CRONOS_INTERNAL_TOKEN` with a placeholder
    value, generation instructions, and a note that it is required for agents running
    inside the container to call the API.'
  acceptance_criteria:
  - '`.env.example` contains a `CRONOS_INTERNAL_TOKEN=` line in the auth section.'
  - A comment above the variable explains its purpose (internal service token for
    agent→API calls) and how to generate it (e.g., `openssl rand -hex 32`).
  - The comment notes that leaving it unset disables the bypass (fail-closed).
  verifying_phase: review
  confidence: 0.9
- requirement_id: R5
  statement: '`.claude/skills/create-goal/SKILL.md` replaces the ''no auth needed
    on the internal port'' claim with instructions to read `CRONOS_INTERNAL_TOKEN`
    from the environment and pass it as an `Authorization: Bearer <token>` header
    on every API request.'
  acceptance_criteria:
  - Line 9 (or equivalent) no longer contains the phrase 'no auth needed on the internal
    port'.
  - 'The `api_post()` helper in the Simple goal procedure section includes an `Authorization:
    Bearer <token>` header constructed from `os.environ[''CRONOS_INTERNAL_TOKEN'']`.'
  - The Feature goal `api_post()` helper is updated identically.
  - A note explains what happens if the env var is absent (agents should raise an
    error rather than silently sending unauthenticated requests).
  verifying_phase: review
  confidence: 0.9
- requirement_id: R6
  statement: 'Backend tests cover the three critical token-path branches: matching
    token → 200, wrong token → 401, unset token → bypass disabled (normal BasicAuth
    required).'
  acceptance_criteria:
  - 'A test with `CRONOS_INTERNAL_TOKEN=test-token` and `Authorization: Bearer test-token`
    header receives HTTP 200 from a protected endpoint.'
  - 'A test with `CRONOS_INTERNAL_TOKEN=test-token` and `Authorization: Bearer wrong-token`
    receives HTTP 401.'
  - 'A test with `CRONOS_INTERNAL_TOKEN` unset and `Authorization: Bearer test-token`
    does NOT bypass auth — receives 401 (or 503 if Basic Auth is also unconfigured,
    consistent with existing fail-closed behaviour).'
  - 'Tests follow the existing conftest pattern: `CRONOS_AUTH_DISABLED` is NOT set
    (so auth is active); `monkeypatch.setenv(''CRONOS_INTERNAL_TOKEN'', ...)` wires
    the token per-test.'
  verifying_phase: test
  confidence: 0.9
metrics:
  tool_calls: 8
  files_read: 4
  memory_hits: 3
---

## Summary

G04 fail-closed auth (commit ba7fff5) secured all routes on port 8000 with bcrypt BasicAuth, which broke the `create-goal` skill's assumption that the backend API is unauthenticated internally. The fix introduces a lightweight internal service token (`CRONOS_INTERNAL_TOKEN`) that agents can use to bypass bcrypt — when the env var is non-empty and a matching Bearer token is supplied, auth passes instantly. The bypass is strictly fail-closed: absent or empty `CRONOS_INTERNAL_TOKEN` → bypass disabled; wrong token → 401 with no fallthrough to bcrypt. Three files change: `backend/app/auth.py` (bypass logic), `.env.example` (documentation), and `.claude/skills/create-goal/SKILL.md` (auth header instructions).

## Scope

### In scope
- `backend/app/auth.py`: add Bearer token bypass branch in `require_auth()` before the BasicAuth credential check
- `.env.example`: document `CRONOS_INTERNAL_TOKEN` in the auth section with generation instructions
- `.claude/skills/create-goal/SKILL.md`: replace "no auth needed" with CRONOS_INTERNAL_TOKEN Bearer header wiring in both `api_post()` examples
- `backend/tests/test_auth.py` (or new file): three new tests for token-match / token-mismatch / token-unset branches

### Out of scope
- `docker-compose.yml`: the task brief mentions Docker Compose but the env var will be populated from `.env` (which the `--env-file` mechanism already threads into the backend container); no compose file change is strictly needed — design agent should confirm
- Changing the Caddy-layer auth or any frontend code
- Rotating or managing the token (secret management is operational, not in scope here)
- Applying the CRONOS_INTERNAL_TOKEN header to skills other than `create-goal` (e.g., `create-task`) — those are separate documents and should be updated as a follow-up

### Deferred
- Updating other skills that call the backend API (e.g., `create-task/SKILL.md`, `pipeline-scaffold/SKILL.md`) to also send the Bearer token — they share the same breakage but are out of this subgoal's scope files
- Adding the token to the Verify section's `curl` example in `create-goal/SKILL.md`

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | Matching Bearer token bypasses bcrypt auth in `require_auth()` |
| R2 | Unset/empty `CRONOS_INTERNAL_TOKEN` disables the bypass path entirely |
| R3 | Wrong Bearer token returns 401 immediately, no fallthrough to bcrypt |
| R4 | `.env.example` documents `CRONOS_INTERNAL_TOKEN` with instructions |
| R5 | `create-goal/SKILL.md` wires CRONOS_INTERNAL_TOKEN into both `api_post()` helpers |
| R6 | Backend tests cover token-match / token-wrong / token-unset branches |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array. Summary:

- R1 — Given the token env var is set and matches the Bearer header, the endpoint returns 200 with no Basic Auth.
- R2 — Given the token env var is absent/empty, a Bearer header does NOT bypass auth; normal BasicAuth processing applies.
- R3 — Given the token env var is set but the header carries a different value, the response is 401 immediately (no bcrypt fallthrough).
- R4 — `.env.example` has `CRONOS_INTERNAL_TOKEN=` with generation instructions and fail-closed note.
- R5 — Both `api_post()` helpers in SKILL.md include the `Authorization: Bearer` header; the stale "no auth needed" claim is removed.
- R6 — Three test cases: match→200, wrong→401, unset→bypass-disabled.

## Traceability

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | Matching Bearer token bypasses bcrypt auth in `require_auth()` |
| R2 | test | Unset/empty `CRONOS_INTERNAL_TOKEN` disables the bypass path entirely |
| R3 | test | Wrong Bearer token returns 401 immediately, no fallthrough to bcrypt |
| R4 | review | `.env.example` documents `CRONOS_INTERNAL_TOKEN` with instructions |
| R5 | review | `create-goal/SKILL.md` wires CRONOS_INTERNAL_TOKEN into both `api_post()` helpers |
| R6 | test | Backend tests cover token-match / token-wrong / token-unset branches |

## Assumptions

- **auth.py path**: The scout report cited `backend/app/auth.py` (not `backend/app/api/auth.py`); confirmed by filesystem search. The task brief says "backend/app/api/auth.py or the auth middleware" — the real path is `backend/app/auth.py`.
- **Bearer token extraction**: FastAPI's `HTTPBasic` security dependency ignores `Authorization: Bearer` headers (it only parses `Basic`). The design agent must add a separate extraction step — either a second `Depends()` or manual header inspection via `Request` — before the BasicAuth check runs. This is an implementation concern for design, not a requirement change.
- **Constant-time comparison**: R1 specifies `hmac.compare_digest` to match the existing timing-safe approach used for Basic Auth credentials. This is a security requirement, not just a style preference.
- **has_ui: false** — all three scope files are backend/config/skill text; no React components, pages, or frontend hooks are touched.
- **docker-compose.yml**: The task brief names it as a scope file, but `.env.example` is the canonical documentation location and the compose file already threads all `.env` variables into the backend container. The design agent should determine if an explicit `environment:` entry in `docker-compose.yml` is also needed (e.g., for the dev setup where `.env` is not used).
- **conftest pattern**: Memory entry `observation_fail_closed_auth_conftest_pattern` confirms that tests enabling auth must use `monkeypatch.delenv("CRONOS_AUTH_DISABLED")` before setting auth env vars. R6 tests must follow this pattern.

## Open questions

- Should docker-compose.yml (dev) also hardcode a default value for `CRONOS_INTERNAL_TOKEN` (e.g., `CRONOS_INTERNAL_TOKEN=dev-internal-token`) so the dev environment works out of the box without `.env` file changes? Design agent should decide.
- Should the `Verify` `curl` example in `create-goal/SKILL.md` also be updated to include `-H "Authorization: Bearer $CRONOS_INTERNAL_TOKEN"`? This is a deferred scope item but may be worth folding in since it's a one-line change.

## Next consumer brief

Design agent: read `traceability[]` for the six requirements and `## Scope` for file boundaries.

Key design decisions to resolve:
1. **Bearer token extraction in FastAPI**: `HTTPBasic(auto_error=False)` only parses `Authorization: Basic`; a Bearer header is silently ignored. The middleware must explicitly inspect the raw `Authorization` header string (via `Request.headers`) or add a second `Depends(HTTPBearer(..., auto_error=False))`. The design must ensure the Bearer check runs BEFORE the BasicAuth credential check so that R3 (wrong token → 401, no fallthrough) is enforced.
2. **docker-compose.yml**: Determine whether a hardcoded dev default for `CRONOS_INTERNAL_TOKEN` belongs in `docker-compose.yml` `environment:` block or left to `.env` only.
3. **SKILL.md update scope**: Both `api_post()` helpers (simple-goal and feature-goal procedures) need the Bearer header. Design should specify the exact diff for each.
4. **R2 guard**: The bypass guard must check `token and token.strip()` to treat `CRONOS_INTERNAL_TOKEN=""` (set but empty) as disabled.
5. The three test cases for R6 should live in `backend/tests/test_auth.py` alongside the existing G04 tests; confirm via grep before writing.
