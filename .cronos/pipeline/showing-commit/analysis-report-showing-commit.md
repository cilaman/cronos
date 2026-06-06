---
cc_version: '1.0'
agent: pipeline-analyst
slug: showing-commit
phase: analysis
status: done
confidence: 0.88
inputs_used:
- memory:project_branding
- memory:feedback_commit_and_upgrade
- .cronos/pipeline/showing-commit/scout-report-showing-commit.md
- frontend/src/components/Sidebar.tsx
- backend/app/pipeline/verify.py
- backend/app/pipeline/schemas/analysis.schema.yaml
- backend/app/pipeline/CONTRACT.md
outputs_produced:
- .cronos/pipeline/showing-commit/analysis-report-showing-commit.md
blockers: []
next_consumer: design
request: 'Show, in the GUI sidebar next to the CRONOS text in the top-left corner,
  the git commit that is currently running, so the operator can see at a glance whether
  the deployed app is in sync with current main.


  It would also be valuable to show a timestamp of when the GUI and the backend were
  last upgraded.


  Notes / acceptance:

  - The running commit must reflect what is actually deployed (baked at build/upgrade
  time), not a value read from a working tree.

  - Ideally the commit is comparable against origin/main (e.g. a short SHA, optionally
  linking to the commit on GitHub).

  - Surface upgrade/build timestamps for both the frontend (GUI) and backend.

  - The deployed app is rebuilt from origin/main by upgrade.sh, so any build-stamp
  wiring must flow through the upgrade + docker build path.'
has_ui: true
coverage_summary:
  searched:
  - frontend/src/components/Sidebar.tsx
  - backend/app/main.py
  - backend/Dockerfile
  - frontend/Dockerfile
  - deploy/upgrade.sh
  - docker-compose.yml
  - docker-compose.prod.yml
  - backend/app/pipeline/schemas/analysis.schema.yaml
  excluded:
  - backend/tests/: not relevant to build-stamp wiring
  - frontend/node_modules/: not relevant
  strategies:
  - memory_retrieval
  - read_targeted
traceability:
- requirement_id: R1
  statement: The deployed git commit SHA is baked into both containers at docker build
    time, not read from the working tree at runtime.
  acceptance_criteria:
  - Given a docker build triggered by upgrade.sh, when the backend container starts,
    then an environment variable BUILD_COMMIT holds the short SHA of the commit at
    origin/main that was checked out before the build.
  - Given a docker build triggered by upgrade.sh, when the frontend bundle is produced,
    then import.meta.env.VITE_BUILD_COMMIT holds the same short SHA.
  - Restarting or exec-ing into a running container does not change the baked-in SHA
    value.
  verifying_phase: test
  confidence: 0.92
- requirement_id: R2
  statement: A build timestamp is baked into both containers at docker build time.
  acceptance_criteria:
  - Given a docker build triggered by upgrade.sh, when the backend container starts,
    then an environment variable BUILD_TIME holds an ISO 8601 UTC timestamp string
    representing when the build ran.
  - Given a docker build triggered by upgrade.sh, when the frontend bundle is produced,
    then import.meta.env.VITE_BUILD_TIME holds the same ISO 8601 UTC timestamp.
  - The timestamp reflects the upgrade run time, not the git commit author date.
  verifying_phase: test
  confidence: 0.92
- requirement_id: R3
  statement: upgrade.sh captures the commit SHA and build timestamp before invoking
    docker compose build and injects them as build args.
  acceptance_criteria:
  - upgrade.sh runs git rev-parse --short HEAD (or equivalent) after git reset --hard
    origin/main and stores the result.
  - upgrade.sh captures a UTC timestamp (date -u +%Y-%m-%dT%H:%M:%SZ or equivalent)
    at upgrade time.
  - upgrade.sh passes both values as --build-arg COMMIT_SHA=<sha> and --build-arg
    BUILD_TIME=<ts> to docker compose build.
  verifying_phase: review
  confidence: 0.9
- requirement_id: R4
  statement: The backend exposes a /api/info endpoint that returns commit_sha and
    build_time fields, with graceful null handling when env vars are absent.
  acceptance_criteria:
  - GET /api/info returns JSON with at least commit_sha (string, 7-8 chars or null)
    and build_time (ISO 8601 string or null).
  - The endpoint is accessible under the existing HTTP Basic Auth with no additional
    authentication.
  - When BUILD_COMMIT or BUILD_TIME env vars are absent (e.g. local dev without upgrade.sh),
    the endpoint returns null for those fields rather than raising an error.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R5
  statement: The frontend sidebar displays the deployed commit SHA near the CRONOS
    header, fetched from /api/info on mount.
  acceptance_criteria:
  - Given the sidebar is rendered, when the /api/info response arrives, then the short
    SHA is visible in the sidebar area adjacent to or below the CRONOS text.
  - The SHA renders as a clickable link to the corresponding GitHub commit when a
    repo URL is available; otherwise as plain monospace text.
  - When commit_sha is null (local dev or env var not set), nothing is rendered in
    the SHA slot.
  - While loading, the SHA slot is empty and does not shift the sidebar layout.
  verifying_phase: test
  confidence: 0.85
- requirement_id: R6
  statement: The sidebar displays a last-upgraded timestamp for the backend, sourced
    from the /api/info build_time field.
  acceptance_criteria:
  - Given build_time is non-null in the API response, when the sidebar renders, then
    a human-readable timestamp (e.g. '2026-05-31 15:30 UTC') appears near the commit
    SHA.
  - When build_time is null, no timestamp element is rendered.
  - The label or tooltip identifies this as the backend build/upgrade time.
  verifying_phase: test
  confidence: 0.82
- requirement_id: R7
  statement: The frontend build timestamp (VITE_BUILD_TIME) is surfaced in the sidebar,
    and the design distinguishes frontend vs backend timestamps when they diverge.
  acceptance_criteria:
  - The sidebar can display frontend_build_time sourced from import.meta.env.VITE_BUILD_TIME
    independently of the API call.
  - The design specifies a threshold (e.g. 5 minutes) beyond which both timestamps
    are shown separately; within the threshold a single timestamp is shown.
  verifying_phase: design
  confidence: 0.7
- requirement_id: R8
  statement: docker-compose.yml and docker-compose.prod.yml are updated to declare
    BUILD_COMMIT and BUILD_TIME ARG/ENV plumbing for both services.
  acceptance_criteria:
  - Both compose files define build.args for BUILD_COMMIT and BUILD_TIME on the backend
    service.
  - The backend service environment block exposes BUILD_COMMIT and BUILD_TIME as runtime
    ENV vars.
  - The frontend service build.args block passes VITE_BUILD_COMMIT and VITE_BUILD_TIME
    to the node builder stage.
  verifying_phase: review
  confidence: 0.92
- requirement_id: R9
  statement: Both Dockerfiles are updated to receive and propagate the build-time
    metadata.
  acceptance_criteria:
  - backend/Dockerfile declares ARG BUILD_COMMIT and ARG BUILD_TIME then sets ENV
    BUILD_COMMIT=$BUILD_COMMIT and ENV BUILD_TIME=$BUILD_TIME so the vars persist
    to the running layer.
  - frontend/Dockerfile declares ARG VITE_BUILD_COMMIT and ARG VITE_BUILD_TIME in
    the node builder stage so Vite can embed them.
  verifying_phase: review
  confidence: 0.92
metrics:
  tool_calls: 10
  files_read: 7
  memory_hits: 2
---

## Summary

The operator needs to see at a glance whether the running Cronos instance matches the current main branch. This requires baking the git commit SHA and a build timestamp into both the frontend bundle and the backend container at upgrade/build time, exposing those values via a new /api/info endpoint, and rendering them in the sidebar. No working-tree reads are permitted; all metadata must flow through the upgrade.sh to docker build to container ENV chain. The feature spans both frontend (UI display) and backend (API endpoint, Dockerfile, upgrade script, compose files).

## Scope

### In scope
- Capturing git commit SHA (short form) and ISO 8601 UTC build timestamp in upgrade.sh before docker compose build
- Passing those values as docker build args to both the frontend and backend builders
- backend/Dockerfile: ARG + ENV wiring so values survive to the running container
- frontend/Dockerfile: ARG wiring so Vite embeds them as VITE_* build-time constants
- New GET /api/info endpoint returning commit_sha and build_time; graceful null for missing vars
- Sidebar footer area: display commit SHA (optionally linked to GitHub) and backend build time, fetched from /api/info
- docker-compose.yml and docker-compose.prod.yml: updated build args and environment declarations

### Out of scope
- Continuous polling of origin/main to detect drift — display is static, baked at build time
- CI/CD or GitHub Actions integration — upgrade.sh is the sole build path
- Changes to HTTP Basic Auth or Caddy configuration
- Replacing the hardcoded "v0.0.1" version string (separate versioning concern)

### Deferred
- Clickable GitHub SHA link when repo URL is not statically known at build time (requires passing REPO_URL as an additional build arg)
- "Upgrade now" button in the sidebar triggering the upgrade webhook from the UI
- Automated sync-status indicator comparing deployed SHA against origin/main HEAD via live GitHub API

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | Commit SHA baked into both containers at docker build time, not from working tree |
| R2 | Build timestamp baked into both containers at docker build time |
| R3 | upgrade.sh captures SHA and timestamp and passes them as docker build args |
| R4 | Backend /api/info endpoint returns commit_sha and build_time (null-safe) |
| R5 | Sidebar displays commit SHA near CRONOS header, from API, null-safe |
| R6 | Sidebar displays backend build timestamp near commit SHA, null-safe |
| R7 | Frontend VITE_BUILD_TIME surfaced in sidebar; design distinguishes frontend vs backend when they diverge |
| R8 | docker-compose files declare ARG/ENV plumbing for BUILD_COMMIT and BUILD_TIME on both services |
| R9 | Both Dockerfiles receive and propagate build-time metadata |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). The body summary below mirrors them in compact form for the human reader.

- R1 — BUILD_COMMIT present in running backend container and VITE_BUILD_COMMIT embedded in frontend bundle; value equals short SHA of origin/main at upgrade time
- R2 — BUILD_TIME in backend container and VITE_BUILD_TIME in frontend bundle hold ISO 8601 UTC timestamp of the build run
- R3 — upgrade.sh uses git rev-parse --short HEAD and date -u to capture metadata and passes both as --build-arg to docker compose build
- R4 — GET /api/info returns JSON with commit_sha and build_time; returns null for both when env vars absent; no auth change needed
- R5 — Short SHA visible in sidebar near CRONOS text; GitHub link when repo URL available; absent when null; no layout shift
- R6 — Human-readable build timestamp shown near SHA; absent when null; label identifies it as backend build time
- R7 — Frontend bundle timestamp (VITE_BUILD_TIME) displayable independently; design specifies threshold for showing both vs one
- R8 — Both compose files have build.args for BUILD_COMMIT/BUILD_TIME (backend) and VITE_BUILD_COMMIT/VITE_BUILD_TIME (frontend)
- R9 — backend/Dockerfile: ARG + ENV for BUILD_COMMIT and BUILD_TIME; frontend/Dockerfile: ARG for VITE_BUILD_COMMIT and VITE_BUILD_TIME in builder stage

## Traceability

The full requirement to acceptance criteria to verifying_phase map is the YAML `traceability[]` array. Downstream agents read the YAML directly; this section exists so a human reader sees the same routing table without parsing YAML.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | Commit SHA baked into both containers at build time, not from working tree |
| R2 | test | Build timestamp baked into both containers at build time |
| R3 | review | upgrade.sh captures SHA and timestamp and passes as docker build args |
| R4 | test | Backend /api/info endpoint returns commit_sha and build_time (null-safe) |
| R5 | test | Sidebar displays commit SHA near CRONOS header, from API, null-safe |
| R6 | test | Sidebar displays backend build timestamp near commit SHA, null-safe |
| R7 | design | Frontend build timestamp (VITE_BUILD_TIME) surfaced; design decides display threshold |
| R8 | review | docker-compose files declare full ARG/ENV plumbing |
| R9 | review | Both Dockerfiles receive and propagate build-time metadata |

## Assumptions

- has_ui=true rationale: the request explicitly asks for display in the GUI sidebar; frontend/src/components/Sidebar.tsx is the affected render component.
- Short SHA is 7-8 characters from git rev-parse --short HEAD; full SHA can be the href target of any GitHub link. This matches the scout assumption and request preference.
- The GitHub repo URL for linking is not necessarily known at build time in the current setup; R5 treats the link as optional with plain text fallback. A follow-on task can add REPO_URL as a build arg.
- A single "last upgraded" timestamp represents when upgrade.sh ran and docker build executed, not the git commit author/committer date. This satisfies the operator intent of knowing when the app was rebuilt and restarted.
- Frontend and backend are rebuilt in the same upgrade.sh invocation; their BUILD_TIME values will differ by at most a few seconds. R7 is marked design-phase because the threshold and display logic require a design decision.
- /api/info is preferred over extending /api/health to keep the health endpoint focused on liveness/readiness semantics; if the design agent prefers extending /api/health that is an acceptable low-risk alternative.
- Local development environments running docker compose up without upgrade.sh will not have BUILD_COMMIT or BUILD_TIME set; the sidebar must render cleanly with nulls.
- The scout confirmed no existing BUILD/VERSION/COMMIT env var wiring exists; all implementation in this spec is net-new.

## Open questions

- None.

## Next consumer brief

Read `traceability[]` for the full requirement list and note `has_ui=true` to confirm the UI sub-track is required.

**Design decision points not resolved in analysis:**

1. New /api/info vs extending /api/health: analysis prefers /api/info for separation of concerns. Design may extend /api/health if minimizing surface area is preferred. Either is acceptable; document the choice.

2. R7 display threshold: when frontend and backend BUILD_TIME values are close (within a few minutes), a single timestamp avoids clutter. Design should specify the threshold and whether to prefer the backend time, frontend time, or the later of the two.

3. GitHub SHA link: R5 allows plain SHA when no REPO_URL is available. Design should decide whether to add a REPO_URL build arg captured from git remote get-url origin in upgrade.sh, or defer the link to a follow-on task.

4. Sidebar render location: Sidebar.tsx lines 204-209 (footer ThemePicker row) currently shows "v0.0.1". Design should choose whether the commit/timestamp replaces that string, appears beside it, or occupies a new row. Mobile close-button layout (lines 113-122) must not be disrupted.

**Risk area**: upgrade.sh was referenced in VPS_SETUP.md but not directly listed as a file in the deploy/ directory by the scout. Design agent should confirm the exact path and content of upgrade.sh before specifying changes.

**Implementation hotpath**: upgrade.sh to docker-compose build args to Dockerfiles to backend ENV to /api/info to frontend/src/api.ts to frontend/src/components/Sidebar.tsx.
