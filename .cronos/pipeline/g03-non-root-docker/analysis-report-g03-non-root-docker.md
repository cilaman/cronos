---
cc_version: '1.0'
agent: pipeline-analyst
slug: g03-non-root-docker
phase: analysis
status: done
confidence: 0.92
inputs_used:
- memory:project-remediation-board-setup
- memory:project-pipeline-analyst-agent
- .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
- .cronos/workspaces/2026-06-20-1427-create-remedy-goals/REMEDIATION-PLAN.md
- backend/Dockerfile
- frontend/Dockerfile
- docker-compose.yml
- backend/docker-entrypoint.sh
- backend/app/git_ops.py
- backend/app/agent.py
outputs_produced:
- .cronos/pipeline/g03-non-root-docker/analysis-report-g03-non-root-docker.md
blockers: []
next_consumer: design
request: 'G03: Non-root agent execution + capability drop + egress allowlist. Closes
  the highest-severity security finding: agents running as root. After: Both containers
  run as UID ≠ 0 (visible via `id` in a task); a full task still completes end-to-end
  as non-root (clone → edit → commit → push → finalize); cap_drop: [ALL] and no-new-privileges:
  true applied in docker-compose; agent container egress constrained to allowlist;
  deliberate exfiltration attempt to unlisted host is blocked.'
has_ui: false
coverage_summary:
  searched:
  - backend/Dockerfile (lines 1-43)
  - frontend/Dockerfile (lines 1-24)
  - docker-compose.yml (lines 1-60)
  - backend/docker-entrypoint.sh (lines 1-19)
  - backend/app/git_ops.py (lines 1-130, especially _auth_env lines 96-115)
  - backend/app/agent.py (lines 1-100)
  - .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
    (G03 findings)
  - .cronos/workspaces/2026-06-20-1427-create-remedy-goals/REMEDIATION-PLAN.md (§G03)
  excluded:
  - frontend/src/: no UI changes required
  - backend/app/ beyond agent.py and git_ops.py: no application-layer changes required
  - backend/tests/: test scope belongs to design/impl phases
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
traceability:
- requirement_id: R1
  statement: backend/Dockerfile creates a non-root system user (e.g. cronos, UID 1001),
    chowns /app and /data to that user, and terminates with a USER directive so the
    process runs as non-root.
  acceptance_criteria:
  - Given the backend image is built and run, `id` inside the container shows UID
    ≠ 0.
  - The cronos user owns /app and /data (verify with `ls -la`).
  - '`whoami` inside the container returns the non-root username.'
  verifying_phase: test
  confidence: 0.95
- requirement_id: R2
  statement: The Claude Code CLI (`claude` binary) installed via `npm install -g @anthropic-ai/claude-code`
    is exec-accessible by the non-root user without additional permission changes.
  acceptance_criteria:
  - Running `claude --version` as the non-root user succeeds (exit code 0).
  - The symlink /usr/local/bin/claude exists and has world-execute permissions (o+x)
    — confirmed or fixed by Dockerfile.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R3
  statement: The Claude auth file location is migrated from /root/.claude.json to
    the non-root user's home directory; docker-entrypoint.sh and the docker-compose.yml
    volume mount are updated accordingly.
  acceptance_criteria:
  - docker-entrypoint.sh references the non-root user's home (e.g., /home/cronos/.claude.json
    and /home/cronos/.claude/backups/).
  - docker-compose.yml volume mount changes from `claude_config:/root/.claude` to
    `claude_config:/home/cronos/.claude` (or equivalent for the chosen user).
  - Container starts and the auth restore logic runs without errors in the entrypoint
    log.
  verifying_phase: test
  confidence: 0.93
- requirement_id: R4
  statement: 'docker-compose.yml backend service includes `cap_drop: [ALL]` and `security_opt:
    [no-new-privileges:true]`.'
  acceptance_criteria:
  - '`docker inspect <backend_container>` shows CapDrop includes ALL.'
  - '`docker inspect <backend_container>` shows SecurityOpt includes no-new-privileges:true.'
  - Container starts and serves /api/health successfully after applying these constraints.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R5
  statement: The /data volume (CRONOS_DATA_DIR) is writable by the non-root user at
    runtime, either via Dockerfile chown or entrypoint permission fix.
  acceptance_criteria:
  - The non-root user can create files under /data/spaces/ at runtime.
  - Existing data mounted from ./data on the host is accessible (no EACCES on startup).
  verifying_phase: test
  confidence: 0.88
- requirement_id: R6
  statement: Git operations using GIT_CONFIG_* env-var PAT injection (backend/app/git_ops.py
    `_auth_env()`) continue to function correctly as the non-root user.
  acceptance_criteria:
  - Given CRONOS_GIT_TOKEN is set, `_auth_env()` returns an env dict with GIT_CONFIG_*
    keys and git clone succeeds.
  - The non-root user has execute access to `/usr/bin/git` (world-executable; no change
    expected).
  - Worktree writes into /data succeed (covered by R5).
  verifying_phase: review
  confidence: 0.92
- requirement_id: R7
  statement: The frontend/Caddy Dockerfile and docker-compose configuration run Caddy
    as a non-root user; if Caddy must bind port 80 inside the container, CAP_NET_BIND_SERVICE
    is added back selectively rather than keeping root.
  acceptance_criteria:
  - Caddy process UID ≠ 0 inside the frontend container.
  - Caddy serves static assets and reverse-proxies /api/* successfully as non-root.
  - If port 80 is required and requires a capability, only CAP_NET_BIND_SERVICE is
    added (not ALL capabilities restored).
  verifying_phase: test
  confidence: 0.85
- requirement_id: R8
  statement: Egress from the backend container is constrained to an allowlist (at
    minimum github.com and api.anthropic.com); an outbound connection to a host not
    on the allowlist is blocked.
  acceptance_criteria:
  - A deliberate HTTP/HTTPS request to an unlisted host (e.g., example.com) from within
    the backend container fails with a network error.
  - A request to github.com (git clone) and api.anthropic.com (Claude API) succeeds.
  - The egress policy mechanism is documented (docker network rule, iptables, or forward
    proxy).
  verifying_phase: manual
  confidence: 0.8
metrics:
  tool_calls: 10
  files_read: 8
  memory_hits: 2
---

## Summary

G03 closes Cronos's highest-severity security gap: agents run as root with bare `Bash` and execute arbitrary shell commands against cloned, potentially untrusted repositories. A prompt-injection in a linked repo or retrieved memory currently yields root code execution inside the container. This goal adds three layered controls: (1) switch both containers to a non-root user, (2) drop all Linux capabilities and prevent privilege escalation in docker-compose, and (3) constrain outbound network egress to an allowlist so even a successful injection cannot exfiltrate to arbitrary hosts. No application-layer (Python) code changes are required; all changes are confined to `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`, and `backend/docker-entrypoint.sh`.

## Scope

### In scope
- Create non-root user in `backend/Dockerfile` with correct ownership of `/app` and `/data`
- Verify Claude CLI exec-accessibility for non-root user after `npm install -g`
- Migrate Claude auth file path (`/root/.claude.json`) to non-root user's home in `docker-entrypoint.sh` and `docker-compose.yml`
- Apply `cap_drop: [ALL]` and `security_opt: [no-new-privileges:true]` to backend service in `docker-compose.yml`
- Fix `/data` volume permissions so non-root user can read/write at runtime
- Verify `GIT_CONFIG_*` env-var PAT injection continues to work as non-root (no code change expected; test/review gate)
- Make frontend/Caddy container run as non-root (with selective capability restoration if port 80 is required)
- Add network-level egress allowlist for backend container

### Out of scope
- Changes to Python application code (`agent.py`, `git_ops.py`, `worker.py`, etc.)
- Changes to stored auth data formats or the `claude` CLI's internal auth protocol
- Agent behaviour changes or prompt modifications
- PAT rotation or GitHub App credential changes (those belong to G11)
- Plugin install guard (G06 — a dependent goal that relies on G03 landing first)

### Deferred
- gVisor / Firecracker microVM per-task sandboxing (mentioned in G03 "rejected alternatives" as a future P3 hardening)
- Per-task network namespace isolation (network policy is container-level here, not per-agent-run)
- A standalone egress proxy service (simple iptables/docker network rule is the right first cut)

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | backend/Dockerfile non-root user creation + chown + USER directive |
| R2 | Claude CLI exec-accessible to non-root user |
| R3 | Auth file path migrated in entrypoint + docker-compose volume mount |
| R4 | cap_drop + no-new-privileges in docker-compose backend service |
| R5 | /data volume writable by non-root user at runtime |
| R6 | GIT_CONFIG_* PAT injection works as non-root (no code change; review gate) |
| R7 | frontend/Caddy runs as non-root with selective capability restoration |
| R8 | Egress allowlist blocks unauthorized outbound connections from backend |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array. Summary:

- R1 — `id` in a running backend container shows UID ≠ 0; /app and /data owned by cronos user
- R2 — `claude --version` succeeds as non-root; symlink at /usr/local/bin/claude has o+x
- R3 — entrypoint.sh uses non-root home paths; docker-compose volume mount updated; entrypoint log shows no errors
- R4 — `docker inspect` confirms CapDrop ALL and SecurityOpt no-new-privileges; /api/health still responds
- R5 — Non-root user can create files under /data/spaces/ at runtime with mounted host volume
- R6 — git clone with GIT_CONFIG_* env succeeds as non-root; git binary world-executable (no change expected)
- R7 — Caddy UID ≠ 0; static assets + /api/* proxy work; only CAP_NET_BIND_SERVICE if port 80 required
- R8 — Request to unlisted host fails; github.com and api.anthropic.com succeed; policy documented

## Traceability

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | backend/Dockerfile non-root user creation + chown + USER directive |
| R2 | test | Claude CLI exec-accessible to non-root user |
| R3 | test | Auth file path migrated in entrypoint + docker-compose volume mount |
| R4 | test | cap_drop + no-new-privileges in docker-compose backend service |
| R5 | test | /data volume writable by non-root user at runtime |
| R6 | review | GIT_CONFIG_* PAT injection works as non-root (no code change; review gate) |
| R7 | test | frontend/Caddy runs as non-root with selective capability restoration |
| R8 | manual | Egress allowlist blocks unauthorized outbound connections from backend |

## Assumptions

- The non-root user name `cronos` and UID `1001` are used as the convention; design agent may choose a different name/UID — the requirement is UID ≠ 0, not a specific name.
- `npm install -g @anthropic-ai/claude-code` places the `claude` symlink at `/usr/local/bin/claude` with world-execute permissions (standard npm behaviour). If this is not true, a `chmod o+x` step is needed in the Dockerfile. Confidence 0.88 — world-exec on global npm packages is standard but not guaranteed for all base images.
- `git` is at `/usr/bin/git` (installed via apt) and has world-execute permissions — standard for `git` on Debian/Ubuntu; no change needed (R6 is a review gate, not a code change).
- The `/data` volume is mounted from `./data` on the host; the host directory may be owned by root. A `chown` in the Dockerfile or entrypoint is required. The design agent should decide between Dockerfile `chown` (build-time, requires UID match) vs. entrypoint `chown` (runtime, more robust for arbitrary host UIDs).
- Egress policy implementation is left to the design agent to choose (iptables rules on the host, docker network with outbound rules, or a forward-proxy sidecar). The requirement is the observable behaviour (unlisted hosts blocked), not the mechanism.
- `has_ui: false` — all changes are infrastructure (Dockerfiles, docker-compose.yml, shell script); no React/TypeScript/frontend UI changes required.
- R8 `verifying_phase: manual` — automated egress tests require either a CI environment with network control or a Docker socket; the test agent cannot reliably simulate network blocking in a unit test context. Design agent should include a manual verification checklist for this requirement.

## Open questions

- None.

## Next consumer brief

**Design agent:** read `traceability[]` for the 8 requirements and `## Scope` for boundaries.

Key design decisions to resolve:

1. **Non-root user strategy (R1, R5):** Choose between (a) creating user at build time + Dockerfile `COPY --chown=cronos:cronos` for /app + an entrypoint step to `chown /data` at runtime, or (b) a dedicated startup script that does both. Option (b) is more robust for arbitrary host-owned `./data` mounts.

2. **Claude auth volume (R3):** Volume mount path must change from `claude_config:/root/.claude` → `claude_config:/home/cronos/.claude`; `docker-entrypoint.sh` CLAUDE_JSON and BACKUPS_DIR variables must be updated to match.

3. **Claude CLI permission (R2):** Insert a `chmod o+rx /usr/local/lib/node_modules/@anthropic-ai/claude-code` or verify via `ls -la /usr/local/bin/claude` in the Dockerfile to be explicit. Don't assume npm defaults.

4. **cap_drop + capability restoration (R4, R7):** Backend: `cap_drop: [ALL]` + `security_opt: [no-new-privileges:true]` — confirm which capabilities (if any) the backend container needs (likely none). Frontend/Caddy (R7): if keeping port 80 inside the container, add `cap_add: [NET_BIND_SERVICE]` selectively; otherwise switch Caddy to an internal port > 1024 and update compose `ports`.

5. **Egress mechanism (R8):** For a single VPS, the most practical approach is host-level iptables `OUTPUT` rules scoped to the container's IP range (docker network). Alternatively, a squid/tinyproxy sidecar with `http_proxy` set in the backend container env. Design agent should assess and choose; R8 is verified manually.

6. **Scope discipline:** Only `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`, and `backend/docker-entrypoint.sh` need editing. Do not touch Python or TypeScript source files.
