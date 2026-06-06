---
cc_version: "1.0"
agent: pipeline-scout
slug: showing-commit
phase: scout
status: done
confidence: 0.92
inputs_used:
  - memory:project_branding
  - memory:feedback_commit_and_upgrade
  - frontend/src/App.tsx
  - frontend/src/components/Sidebar.tsx
  - backend/app/main.py
  - frontend/src/api.ts
  - frontend/vite.config.ts
  - backend/Dockerfile
  - frontend/Dockerfile
  - docker-compose.yml
  - docker-compose.prod.yml
  - deploy/upgrade-webhook.py
  - deploy/VPS_SETUP.md
  - backend/pyproject.toml
  - frontend/package.json
  - .env.example
  - Caddyfile
  - Caddyfile.dev
outputs_produced:
  - .cronos/pipeline/showing-commit/scout-report-showing-commit.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - frontend/src
    - backend/app
    - deploy/
    - docker configuration
  excluded:
    - backend/tests
    - frontend/node_modules
  strategies:
    - memory_retrieval
    - glob_structural
    - grep_symbol
    - read_targeted
metrics:
  tool_calls: 18
  files_read: 17
  memory_hits: 2
---

## Summary

The Cronos GUI currently shows a hardcoded "v0.0.1" in the sidebar footer (Sidebar.tsx:207) with no deployment metadata. The upgrade.sh script fetches origin/main and rebuilds Docker images, but does not bake build timestamps or git commit SHAs into the resulting containers. The frontend and backend have no current mechanism to expose build-time constants to the GUI. To implement the feature, build metadata must be: (1) captured during the docker build phase, (2) wired through environment variables into containers, (3) exposed via a new API endpoint (or added to /api/health), and (4) rendered in the sidebar alongside the version.

## Coverage

### Searched

- frontend/src (App.tsx, Sidebar.tsx, components/, api.ts, vite.config.ts)
- backend/app (main.py, Dockerfile)
- deploy/ (upgrade-webhook.py, VPS_SETUP.md)
- docker configuration (docker-compose.yml, .prod overlay, Dockerfiles)
- pyproject.toml, package.json (version sources)

### Excluded

- backend/tests: not relevant to deployment infra
- frontend/node_modules: not relevant
- .git history: not examined (live commit retrieval needed)

### Strategies

- **memory_retrieval**: 2 relevant entries (project_branding confirms cilaman.com domain; feedback_commit_and_upgrade documents upgrade workflow)
- **glob_structural**: targeted frontend/backend/deploy patterns yielded 18 relevant files
- **grep_symbol**: searched for BUILD, VERSION, COMMIT, VITE_, REACT_APP patterns; none found (no current build-time constant wiring)
- **read_targeted**: full reads of sidebar, API layer, upgrade infrastructure, docker configs, VPS setup docs

## Findings

### 1. Current sidebar branding location

**frontend/src/components/Sidebar.tsx, lines 103–112** — Header div with live circle icon and "CRONOS" text:
```
<span className="font-display text-sm font-semibold uppercase tracking-[0.22em] text-ink">
  Cronos
</span>
```

**frontend/src/components/Sidebar.tsx, lines 204–209** — Footer with hardcoded version:
```
<span className="font-mono text-[10px] tracking-[0.14em] text-ink-faint">
  v0.0.1
</span>
```

**frontend/src/App.tsx, lines 30–32** — Mobile header also shows "CRONOS" text (static).

**Relevance**: The sidebar footer is the natural candidate location for deployed commit SHA and build timestamps. Currently only a static hardcoded version exists.

### 2. Upgrade and docker build flow

**deploy/upgrade-webhook.py, lines 18–45** — Webhook listens on 172.18.0.1:9137; POST /upgrade runs `/opt/cronos/upgrade.sh` as daemon thread.

**upgrade.sh workflow**:
1. `git fetch origin` and `git reset --hard origin/main` (pulls latest from remote)
2. `docker compose build` (rebuilds both backend and frontend images)
3. `sudo systemctl restart cronos.service` (restarts the app)

**docker-compose.prod.yml, lines 35–39** — Backend loads CLAUDE_CODE_OAUTH_TOKEN from env_file.

**Relevance**: Docker build command runs at upgrade time with repo at origin/main. Build metadata (git commit, timestamp) can be captured here as docker ARG or embedded in build context. No current mechanism exists to pass build args to either frontend or backend builders.

### 3. Frontend build and serving

**frontend/Dockerfile** — Multi-stage build:
- Node 22 builder image runs `npm install` + `npm run build`, outputs `/app/dist`
- Caddy serves from `/srv`
- No ARG for build-time secrets

**frontend/vite.config.ts** — Minimal config; `base="/app/"`, no env interpolation currently.

**frontend/src/api.ts** — HTTP client has no version/metadata endpoints.

**Relevance**: Vite supports `import.meta.env.VITE_*` pattern for build-time constants. Dockerfile must pass commit/timestamp as docker build args to the node builder stage.

### 4. Backend build and health endpoint

**backend/Dockerfile** — Python 3.12 base, installs Claude CLI, no ARG for metadata.

**backend/app/main.py:225–268** — Health endpoint returns:
```python
{
  "ok": ok,
  "data_dir": str(DATA_DIR),
  "spaces_dir_exists": spaces_dir_ok,
  "claude_on_path": claude_on_path,
  "index_loaded": index_loaded,
  "tasks_indexed": tasks_indexed,
  "spaces_indexed": spaces_indexed,
  "workers_running": workers_running,
  "workers": workers_info,
}
```

**Relevance**: Health endpoint is a natural place to add `commit_sha` and `backend_build_time` fields. No version or commit info currently in response.

### 5. Version and build metadata sources

- **backend/pyproject.toml:3** — Version = "0.0.1" (hardcoded)
- **frontend/package.json:3** — Version = "0.0.1" (hardcoded)
- **frontend/src/components/Sidebar.tsx:207** — Version = "v0.0.1" (hardcoded in JSX)

**Relevance**: Versions are static. Build commit and timestamp must be injected at docker build time, not read from container's working tree (which would give stale state, not deployed state per the requirement).

### 6. Deployment environment and arguments

**docker-compose.yml** — No build args passed to frontend or backend builders.

**docker-compose.prod.yml** — Backend env_file loads OAuth token; no build-metadata env vars.

**.env.example** — Documents DOMAIN, BASIC_AUTH_USER, BASIC_AUTH_HASH, CRONOS_GIT_TOKEN; no BUILD_COMMIT, BUILD_TIMESTAMP.

**Relevance**: New env vars must be added to compose files and .env schema. These can be: (1) captured in upgrade.sh and passed as docker ARGs, or (2) written to a file at build time and mounted.

### 7. Caddy reverse proxy and static file serving

**Caddyfile:21–23** and **Caddyfile.dev:13–15** — `/api/*` reverse-proxied to backend:8000.

**frontend/src/api.ts** — HTTP client targets `/api/` exclusively.

**Relevance**: API is the recommended path for deployment metadata. A GET /api/info or extension to /api/health keeps the pattern consistent.

### 8. GitHub integration capability

**backend/app/git_ops.py** (inferred from CLAUDEMD) — Project supports repo-linked spaces with CRONOS_GIT_TOKEN for HTTPS clones.

**docker-compose.prod.yml:40–50** — Token loaded via env_file.

**Relevance**: App already has GitHub integration. Commit SHA can optionally include a GitHub link (short SHA with link to commit) if repo URL is known at build time.

## Assumptions

- The running commit must reflect deployed state (baked at build time), not the working tree state inside the container. Docker ARG or build-time file is required.
- Build timestamp should be ISO 8601 (e.g., 2026-05-31T15:30:00Z) captured at docker build time.
- Frontend and backend build times may differ slightly; a single "last upgraded" timestamp is sufficient (use the later time or the overall upgrade.sh timestamp).
- Short commit SHA (7–8 chars) is preferred for display; full SHA can be in a title tooltip.
- Operator has API access to query /api/health or /api/info.

## Open questions

- None.

## Next consumer brief

**Analysis phase should validate:**

1. Should deployment metadata live in a new /api/info endpoint or extend /api/health?
2. Should the commit SHA display always, or only when different from origin/main (with sync indicator)?
3. Should there be a clickable GitHub link, or just plain SHA?
4. Should frontend and backend timestamps be shown separately or merged to single "last upgraded" time?

**Key implementation touchpoints for downstream design phase:**

- **Sidebar.tsx** (render location): Fetch metadata from API on mount; display commit SHA and timestamp(s) in footer
- **backend/app/main.py** (health or new /api/info endpoint): Add `commit_sha`, `backend_build_time` fields to response
- **frontend/Dockerfile** (ARG injection): Pass `VITE_BUILD_COMMIT` and `VITE_BUILD_TIME` as docker build args to node builder
- **backend/Dockerfile** (ENV setup): Set `BUILD_COMMIT` and `BUILD_TIME` via ENV (or read from mounted file)
- **deploy/upgrade.sh** (metadata capture): Capture commit with `git rev-parse --short HEAD`, timestamp with `date -u +%Y-%m-%dT%H:%M:%SZ`; pass as `--build-arg` to docker compose build
- **docker-compose.yml / .prod.yml** (env var definitions): Add BUILD_COMMIT and BUILD_TIME to backend service environment
- **Caddy** (reverse proxy): No changes needed; API request passes through transparently

**File paths for next phase:**
- frontend/src/components/Sidebar.tsx (render)
- frontend/src/api.ts (optional: add info() or extend health())
- backend/app/main.py (health endpoint extension or new /api/info)
- backend/Dockerfile (ENV for build metadata)
- frontend/Dockerfile (ARG passing to builder)
- deploy/upgrade.sh (metadata capture and docker build args)
- docker-compose.yml and docker-compose.prod.yml (env definitions)
