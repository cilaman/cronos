---
cc_version: '1.0'
agent: pipeline-architect
slug: g03-non-root-docker
phase: design
status: done
confidence: 0.85
inputs_used:
- memory:project-remediation-board-setup
- memory:project-pipeline-architect-agent
- .cronos/pipeline/g03-non-root-docker/analysis-report-g03-non-root-docker.md
- .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
- backend/Dockerfile
- frontend/Dockerfile
- docker-compose.yml
- backend/docker-entrypoint.sh
outputs_produced:
- .cronos/pipeline/g03-non-root-docker/design-report-g03-non-root-docker.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - backend/Dockerfile (full file, 43 lines)
  - frontend/Dockerfile (full file, 24 lines)
  - docker-compose.yml (full file, 60 lines)
  - backend/docker-entrypoint.sh (full file, 19 lines)
  - backend/app/pipeline/schemas/design.schema.yaml (design-class constraints)
  - backend/app/pipeline/verify.py (placeholder list, agent registry)
  excluded:
  - 'backend/app/git_ops.py: R6 is a review gate — no code change required (analyst
    confirmed env-var PAT injection is UID-agnostic)'
  - 'backend/app/worker.py: R3 home-path migration handled via CLAUDE_PROJECTS_DIR
    compose env override; no Python edit'
  - 'Caddyfile / Caddyfile.dev: out of allowed scope_files; R7 solved via cap_add[NET_BIND_SERVICE]
    instead of port change'
  - 'frontend/src/**, backend/tests/**: infra-only goal, has_ui=false'
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
iterations:
- id: I1
  type: infra
  scope_files:
  - backend/Dockerfile
  validation_command: docker build -t cronos-backend-g03:test backend/ && docker run
    --rm --entrypoint='' cronos-backend-g03:test sh -c 'id -u | grep -vq ^0$ && id
    -un | grep -q cronos && test -x /usr/local/bin/claude && stat -c %a /usr/local/bin/claude
    | grep -Eq ^.{2}[1357]$ && test -d /app && test -d /data && stat -c %U /app |
    grep -q cronos && stat -c %U /data | grep -q cronos'
  max_diff_lines: 120
  depends_on: []
- id: I2
  type: infra
  scope_files:
  - backend/docker-entrypoint.sh
  validation_command: grep -q '/home/cronos/.claude.json' backend/docker-entrypoint.sh
    && grep -q '/home/cronos/.claude/backups' backend/docker-entrypoint.sh && grep
    -q 'exec gosu cronos' backend/docker-entrypoint.sh && sh -n backend/docker-entrypoint.sh
  max_diff_lines: 80
  depends_on:
  - I1
- id: I3
  type: infra
  scope_files:
  - docker-compose.yml
  validation_command: 'docker compose -f docker-compose.yml config | tee /tmp/g03-compose.yml
    && grep -q ''no-new-privileges:true'' /tmp/g03-compose.yml && grep -A2 ''cap_drop''
    /tmp/g03-compose.yml | grep -q ALL && grep -q ''claude_config:/home/cronos/.claude''
    /tmp/g03-compose.yml && grep -q ''CLAUDE_PROJECTS_DIR: /home/cronos/.claude/projects''
    /tmp/g03-compose.yml'
  max_diff_lines: 80
  depends_on:
  - I1
  - I2
- id: I4
  type: infra
  scope_files:
  - frontend/Dockerfile
  - docker-compose.yml
  validation_command: docker compose -f docker-compose.yml config | tee /tmp/g03-compose-fe.yml
    && grep -qE 'USER\s+(caddy|cronos|[0-9]+)' frontend/Dockerfile && grep -A4 'caddy:'
    /tmp/g03-compose-fe.yml | grep -q 'NET_BIND_SERVICE'
  max_diff_lines: 60
  depends_on:
  - I3
- id: I5
  type: infra
  scope_files:
  - deploy/EGRESS_ALLOWLIST.md
  validation_command: test -f deploy/EGRESS_ALLOWLIST.md && grep -q 'api.anthropic.com'
    deploy/EGRESS_ALLOWLIST.md && grep -q 'github.com' deploy/EGRESS_ALLOWLIST.md
    && grep -qi 'manual verification' deploy/EGRESS_ALLOWLIST.md && grep -qi 'example.com'
    deploy/EGRESS_ALLOWLIST.md
  max_diff_lines: 200
  depends_on:
  - I3
risks:
- description: Runtime chown of host-mounted /data is incompatible with cap_drop:[ALL]
    + no-new-privileges if attempted after the user switch — a non-root process cannot
    chown files it does not own. If we drop privileges in the Dockerfile via USER
    cronos and then run the entrypoint, the chown step in the entrypoint will fail
    with EPERM and the container will refuse to boot when the host's ./data is root-owned.
  severity: high
  mitigation: 'Use the gosu drop-privileges-in-entrypoint pattern: keep the Dockerfile''s
    final USER as root (or omit USER and rely on the entrypoint), install gosu via
    apt in I1, have docker-entrypoint.sh chown -R cronos:cronos /data (idempotent,
    only if not already owned) and then exec gosu cronos "$@" as its final line. no-new-privileges:true
    blocks setuid escalation AFTER the privilege boundary; it does not block an initial
    root→cronos drop performed before the application process starts.'
- description: Caddy binds privileged port 80 inside the frontend container. After
    dropping to a non-root USER, an unprivileged process cannot bind <1024 without
    CAP_NET_BIND_SERVICE. Changing the listen port to 8080 would require editing Caddyfile
    / Caddyfile.dev, which are NOT in the allowed scope_files for this goal.
  severity: medium
  mitigation: 'Keep Caddy listening on :80 internally (Caddyfile unchanged) and add
    `cap_add: [NET_BIND_SERVICE]` to the caddy service in docker-compose.yml in I4.
    This is the minimal-capability path; it does NOT restore the dropped ALL capabilities,
    only re-grants the single bind capability. The caddy: image''s default USER may
    already be set — verify with `docker inspect caddy:2-alpine` and add an explicit
    `USER` line in frontend/Dockerfile only if the upstream default is root.'
- description: Egress allowlist (R8) verification phase is 'manual' and docker-compose
    alone cannot express a host-level L3/L7 default-deny egress policy. If the implementor
    stops at a compose-only solution they will not satisfy R8's acceptance criteria
    (deliberate request to example.com must fail; github.com + api.anthropic.com must
    succeed).
  severity: medium
  mitigation: I5 produces deploy/EGRESS_ALLOWLIST.md documenting two practical mechanisms
    (host iptables OUTPUT rules scoped to the docker bridge subnet, OR a forward-proxy
    sidecar with HTTP_PROXY env injection) and a step-by-step manual verification
    checklist (curl example.com → fail; curl https://api.anthropic.com → 200/401;
    git ls-remote https://github.com/octocat/Hello-World → success). R8 closes when
    an operator executes the checklist on the deployment host and records the result.
- description: 'Host bind-mount UID mismatch: the host''s ./data directory may be
    owned by an arbitrary UID (often 0 or 1000); after entrypoint chowns it to UID
    1001 (cronos), subsequent `docker compose down && up` cycles work, but other host
    tooling that touches ./data (e.g. backup.sh in deploy/) may now fail with EACCES,
    OR the host''s developer user can no longer edit files there.'
  severity: medium
  mitigation: Document the UID 1001 choice and the host-side consequence in deploy/EGRESS_ALLOWLIST.md's
    adjacent ops notes (or call it out in the I2 entrypoint comment). Ensure entrypoint
    chown is idempotent (`chown -R --from=0 cronos:cronos /data 2>/dev/null || chown
    -R cronos:cronos /data`) so it only acts when ownership is wrong. Cronos's nightly
    backup runs as root via systemd (per CLAUDE.md deploy/), so backup.sh is unaffected
    — confirm during manual smoke.
- description: 'Claude CLI executable permissions: `npm install -g @anthropic-ai/claude-code`
    typically lays down world-executable bits on the /usr/local/bin/claude symlink
    and the underlying /usr/local/lib/node_modules/@anthropic-ai/claude-code/cli.js,
    but this is not guaranteed across npm/Node versions. If the symlink target is
    mode 0700 (owner-only), the cronos user gets EACCES when invoking `claude`.'
  severity: medium
  mitigation: In I1 add an explicit `chmod -R o+rX /usr/local/lib/node_modules/@anthropic-ai/claude-code
    && chmod o+rx /usr/local/bin/claude` step immediately after `npm install -g`.
    The I1 validation_command runs `test -x /usr/local/bin/claude` to fail the build
    if perms are wrong.
- description: 'R6 (git PAT injection works as non-root) is verifying_phase: review
    and has no scope_files in this design — the analyst certified that backend/app/git_ops.py''s
    _auth_env() is UID-agnostic. If the reviewer fails this gate at attempt N, there
    is no architect-owned iteration to fix it; the fix would belong in a Python source
    file outside this goal''s allowed scope.'
  severity: low
  mitigation: Coverage_summary.excluded explicitly records the rationale for not scoping
    git_ops.py. The reviewer should validate R6 by inspecting _auth_env() (lines 96-115)
    against the running container's `id` output — no edit expected. If the review
    unexpectedly fails, escalate to a follow-up goal rather than expanding G03's scope;
    do not have implementors edit Python in this goal.
metrics:
  tool_calls: 9
  files_read: 8
  memory_hits: 2
  iterations_planned: 5
---

## Summary

G03 closes Cronos's highest-severity finding (agents executing as root) with five strictly infrastructure-only iterations: rebuild backend image as non-root `cronos` (UID 1001) with verified Claude-CLI executability (I1), migrate auth paths and add the gosu drop-privileges entrypoint so runtime `/data` chown survives `cap_drop:[ALL]` (I2), apply `cap_drop`/`no-new-privileges`/volume-path/env-override changes to the backend service in docker-compose (I3), make Caddy non-root with selective `NET_BIND_SERVICE` capability so port 80 still binds (I4), and document the egress allowlist mechanism plus a manual verification checklist for R8 (I5). No Python or TypeScript source is touched; R6 is covered by a review-only inspection of `git_ops.py` and is explicitly excluded from `scope_files` to keep this goal hygienic.

## Components

### Data
- No data-model changes. Goal is pure container/infra hardening.

### Backend
- `backend/Dockerfile`: add `cronos` user (UID 1001), install `gosu` via apt, ensure `/app` + `/data` exist and are owned by cronos, normalize Claude CLI permissions, keep final USER as root so the entrypoint can chown then drop (gosu pattern).
- `backend/docker-entrypoint.sh`: migrate `CLAUDE_JSON` and `BACKUPS_DIR` from `/root/.claude*` to `/home/cronos/.claude*`; add idempotent `chown -R cronos:cronos /data`; replace `exec "$@"` with `exec gosu cronos "$@"`.
- `docker-compose.yml` (backend service): change volume `claude_config:/root/.claude` → `claude_config:/home/cronos/.claude`; add `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`, and `environment.CLAUDE_PROJECTS_DIR: /home/cronos/.claude/projects` (overrides the hardcoded `/root/.claude/projects` in `backend/app/worker.py:43` without editing Python).

### Frontend
- `frontend/Dockerfile`: add `USER caddy` (or numeric UID if `caddy` user is absent in `caddy:2-alpine`) at the bottom of the runtime stage, after COPY steps.
- `docker-compose.yml` (caddy service): add `cap_drop: [ALL]` + `security_opt: [no-new-privileges:true]` + `cap_add: [NET_BIND_SERVICE]` so port 80 binds without restoring full root capabilities. Caddyfiles unchanged.

### Infra / Docs
- `deploy/EGRESS_ALLOWLIST.md`: new runbook documenting two egress-restriction mechanisms (host iptables OUTPUT rules scoped to the docker bridge subnet, or a forward-proxy sidecar) and a manual verification checklist for R8 (curl example.com → fail; curl https://api.anthropic.com → success; git ls-remote https://github.com/<sample-public-repo> → success).

## Implementation plan

| ID | Type  | Depends on | Scope files (abridged)                          | Validation                                                                 |
|----|-------|------------|-------------------------------------------------|----------------------------------------------------------------------------|
| I1 | infra | -          | backend/Dockerfile                              | docker build + run; assert UID!=0, claude exec-able, /app+/data owned by cronos |
| I2 | infra | I1         | backend/docker-entrypoint.sh                    | grep for /home/cronos paths + gosu exec; sh -n syntax check                |
| I3 | infra | I1, I2     | docker-compose.yml                              | `docker compose config` then grep for cap_drop ALL, no-new-privileges, volume path, CLAUDE_PROJECTS_DIR env |
| I4 | infra | I3         | frontend/Dockerfile, docker-compose.yml         | `docker compose config` + grep USER directive in frontend/Dockerfile + NET_BIND_SERVICE under caddy service |
| I5 | infra | I3         | deploy/EGRESS_ALLOWLIST.md                      | File exists + contains api.anthropic.com + github.com + manual checklist with example.com test |

Requirement coverage (R1–R8):

| R# | Covered by                  | Notes                                                                       |
|----|-----------------------------|-----------------------------------------------------------------------------|
| R1 | I1                          | Non-root user creation + chown + USER (the USER is overridden at runtime via gosu but the cronos user owns /app, /data and is the process UID after entrypoint) |
| R2 | I1                          | Explicit chmod o+rx in Dockerfile + validation runs `test -x`              |
| R3 | I2, I3                      | Entrypoint paths migrated; compose volume + env override                   |
| R4 | I3                          | cap_drop[ALL] + no-new-privileges in docker-compose                        |
| R5 | I1, I2                      | Build-time chown of /data placeholder; runtime idempotent chown via gosu entrypoint |
| R6 | (review-only; see risks)    | No edit needed — analyst certified _auth_env() is UID-agnostic; covered in risks[6] |
| R7 | I4                          | Caddy non-root + selective NET_BIND_SERVICE                                |
| R8 | I5                          | Egress allowlist runbook + manual verification checklist                   |

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| gosu/cap_drop interaction: runtime chown after USER switch fails with EPERM | high | Use gosu drop-privileges pattern in entrypoint; keep Dockerfile USER root; chown then `exec gosu cronos "$@"`. no-new-privileges blocks setuid escalation post-boundary, not the initial drop. |
| Caddy port 80 vs scope tension (Caddyfile out of scope) | medium | `cap_add: [NET_BIND_SERVICE]` in compose for caddy service; do NOT change Caddy listen port. |
| R8 egress allowlist mechanism is manual and not expressible in compose alone | medium | I5 documents host-iptables + forward-proxy options plus an explicit manual verification checklist (curl example.com must fail; api.anthropic.com + github.com must succeed). |
| Host bind-mount UID mismatch breaks dev tooling that edits ./data | medium | Idempotent chown in entrypoint (`chown --from=0` style); document UID 1001 + host-side implications in EGRESS_ALLOWLIST.md ops notes section. |
| Claude CLI not world-executable on certain npm/Node combos | medium | Explicit `chmod -R o+rX` after `npm install -g` in I1; I1 validation_command runs `test -x /usr/local/bin/claude`. |
| R6 (git PAT injection as non-root) is review-only with no architect-owned iteration | low | Excluded with rationale in coverage_summary; analyst certified _auth_env() UID-agnostic. If review fails unexpectedly, escalate to a follow-up goal rather than scope-creep G03. |

## Assumptions

- Convention UID 1001 / username `cronos` is acceptable (matches `docker-compose.prod.yml:59`'s existing `/home/cronos/.config/claude/env` reference; R1 requires UID≠0 not a specific value).
- `gosu` is available via Debian apt (it is — Debian package `gosu` exists in bookworm/trixie). Using `gosu` keeps the entrypoint POSIX-sh compatible (no su-exec swap needed).
- The host `./data` directory may be root-owned at runtime; the idempotent entrypoint chown handles arbitrary host UIDs without rebuilds.
- `caddy:2-alpine`'s upstream image may or may not ship a `caddy` user; the implementor must inspect at I4 time and either reuse the upstream user (`USER caddy`) or create a numeric `USER 1001` line. Either satisfies R7.
- The `backend/app/worker.py:43` hardcoded `/root/.claude/projects` default is overridable via the `CLAUDE_PROJECTS_DIR` env var (confirmed by reading the line: `os.environ.get("CLAUDE_PROJECTS_DIR", "/root/.claude/projects")`). This keeps R3 satisfied without editing Python.
- R8 verifying_phase=manual means the test agent cannot assert the egress block in CI; the runbook + checklist is the contractual deliverable for this goal cycle. A future goal can add automated network-policy testing.
- `backend/app/git_ops.py:_auth_env()` (lines 96–115) is UID-agnostic per analyst certification; non-root cronos can read `os.environ` and `/usr/bin/git` is world-executable on Debian. No R6 edit required.

## Open questions

- None. All design facts that affected scoping (gosu pattern, port-80 capability vs. Caddyfile scope, CLAUDE_PROJECTS_DIR env override) were resolved during recon and folded into the iterations or risks. The egress allowlist mechanism choice (iptables vs. forward proxy) is left to the implementor's runbook in I5 since R8 is verified by behaviour not mechanism.

## Next consumer brief

Implementor: consume `iterations[]` one entry at a time, in topological order (I1 → I2 → I3 → I4 ‖ I5). The full iteration is your unit of work; `scope_files` is a hard diff boundary — do NOT edit any Python, TypeScript, Caddyfile, or test file even if it would simplify the change.

Cross-iteration invariants the YAML alone does not capture:

1. **Username/UID:** Use `cronos` / UID `1001` consistently across I1 (Dockerfile `useradd`), I2 (entrypoint `chown cronos:cronos` and `gosu cronos`), and I3 (volume path `/home/cronos/.claude`). If you change the username, change it in all three iterations atomically.
2. **gosu pattern (I1 + I2 are coupled):** I1 must `apt-get install -y gosu` and must NOT add a final `USER cronos` directive. I2 must end with `exec gosu cronos "$@"`. The Dockerfile USER stays root so the entrypoint can chown `/data` at runtime; gosu drops to cronos before the uvicorn process starts.
3. **CLAUDE_PROJECTS_DIR env (I3):** This compose-env override is the substitute for editing `backend/app/worker.py:43`'s hardcoded `/root/.claude/projects` default. Without it, agent run logs will try to write under `/root/` (unwritable for cronos) and fail.
4. **R6 has no iteration:** Do NOT add an iteration that touches `backend/app/git_ops.py`. The reviewer validates R6 by inspecting `_auth_env()` lines 96–115 against the running non-root container.

Open question for implementor I4: confirm whether `caddy:2-alpine` ships a `caddy` user before choosing `USER caddy` vs `USER 1001`. Either is valid for R7.
