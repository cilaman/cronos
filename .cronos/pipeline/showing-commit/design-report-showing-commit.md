---
cc_version: '1.0'
agent: pipeline-architect
slug: showing-commit
phase: design
status: done
confidence: 0.85
inputs_used:
- memory:project_branding
- memory:feedback_commit_and_upgrade
- .cronos/pipeline/showing-commit/analysis-report-showing-commit.md
- .cronos/pipeline/showing-commit/scout-report-showing-commit.md
- deploy/VPS_SETUP.md
- deploy/upgrade-webhook.py
- frontend/src/components/Sidebar.tsx
- frontend/src/api.ts
outputs_produced:
- .cronos/pipeline/showing-commit/design-report-showing-commit.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - deploy/
  - frontend/src/components/Sidebar.tsx
  - frontend/src/api.ts
  - .cronos/pipeline/showing-commit/
  excluded:
  - backend/tests/: implementor scopes its own tests per iteration
  - frontend/node_modules/: not relevant
  strategies:
  - memory_retrieval
  - read_targeted
iterations:
- id: I1
  type: infra
  scope_files:
  - deploy/upgrade.sh
  - deploy/VPS_SETUP.md
  validation_command: bash -n /data/spaces/cronos-development/deploy/upgrade.sh &&
    grep -E 'git rev-parse --short HEAD|date -u' /data/spaces/cronos-development/deploy/upgrade.sh
  max_diff_lines: 200
  depends_on: []
- id: I2
  type: infra
  scope_files:
  - backend/Dockerfile
  - frontend/Dockerfile
  - docker-compose.yml
  - docker-compose.prod.yml
  validation_command: docker compose -f /data/spaces/cronos-development/docker-compose.yml
    config --quiet && docker compose -f /data/spaces/cronos-development/docker-compose.yml
    -f /data/spaces/cronos-development/docker-compose.prod.yml config --quiet
  max_diff_lines: 200
  depends_on:
  - I1
- id: I3
  type: backend
  scope_files:
  - backend/app/main.py
  - backend/tests/test_info_endpoint.py
  validation_command: cd /data/spaces/cronos-development/backend && pytest tests/test_info_endpoint.py
    -v
  max_diff_lines: 250
  depends_on:
  - I2
- id: I4
  type: frontend
  scope_files:
  - frontend/src/api.ts
  - frontend/src/types.ts
  - frontend/src/hooks/useBuildInfo.ts
  - frontend/src/components/BuildInfo.tsx
  - frontend/src/components/Sidebar.tsx
  - frontend/src/components/__tests__/BuildInfo.test.tsx
  validation_command: cd /data/spaces/cronos-development/frontend && npm test -- src/components/__tests__/BuildInfo.test.tsx
    --run
  max_diff_lines: 400
  depends_on:
  - I3
risks:
- description: deploy/upgrade.sh does not currently exist in the repository (only
    referenced as /opt/cronos/upgrade.sh from VPS_SETUP.md and upgrade-webhook.py).
    Committing a new repo-tracked version risks divergence from any hand-rolled host
    script operators may have installed previously.
  severity: high
  mitigation: I1 adds upgrade.sh as a NEW repo-tracked file AND updates VPS_SETUP.md
    §10.1 with an explicit step to `sudo install -m 755 /opt/cronos/deploy/upgrade.sh
    /opt/cronos/upgrade.sh` after every git pull, making the repo version the canonical
    source and providing a clean migration path.
- description: Vite embeds VITE_* env vars at build time only; rebuilding the backend
    without rebuilding the frontend (e.g. a docker compose build backend on its own)
    would leave a stale VITE_BUILD_COMMIT in the served bundle while /api/info reports
    the new value.
  severity: medium
  mitigation: I1 ensures upgrade.sh always invokes `docker compose build` (no service
    argument), rebuilding both images in lockstep with the same COMMIT_SHA/BUILD_TIME
    args. I4's BuildInfo component computes drift with a 5-minute threshold and displays
    both timestamps when they diverge — surfacing any future partial-rebuild mistake
    to the operator instead of silently masking it.
- description: /api/info is a new public-under-Basic-Auth endpoint that returns build
    metadata; an attacker who gets past Basic Auth could correlate commit SHA against
    public GitHub to identify vulnerable deployed versions.
  severity: low
  mitigation: The endpoint returns only what is already implicit in the running bundle
    (commit SHA is embedded in VITE_BUILD_COMMIT and visible in any HTML view-source).
    No additional information disclosure beyond the existing attack surface. Document
    this in a docstring on the endpoint so future reviewers do not relax auth in front
    of it.
- description: Local dev (docker compose up without upgrade.sh) and pytest CI both
    run with BUILD_COMMIT and BUILD_TIME unset, which could break tests that assert
    on the fields if not handled.
  severity: medium
  mitigation: 'I3 explicitly writes test_info_endpoint.py with two cases: (1) env
    vars present -> non-null fields; (2) env vars absent (monkeypatch.delenv) -> both
    fields equal null and HTTP 200 (no exception). Backend implementation reads via
    os.environ.get(...) with default None, never os.environ[...].'
- description: Sidebar layout shift while /api/info is in-flight could cause a visible
    jitter on first render.
  severity: low
  mitigation: I4's BuildInfo component reserves a fixed two-line min-height slot (or
    one line when collapsed) so the layout is stable regardless of fetch state. The
    slot renders empty whitespace until React Query resolves, then fades in via existing
    Tailwind transition utilities. Validated via the BuildInfo.test.tsx loading-state
    assertion.
metrics:
  tool_calls: 8
  files_read: 6
  memory_hits: 2
  iterations_planned: 4
---

## Summary

The feature bakes commit SHA, build timestamp, and repo URL into both containers via a versioned `deploy/upgrade.sh` that passes `--build-arg` values to `docker compose build`. The backend exposes `GET /api/info` returning `{commit_sha, build_time, repo_url, frontend_build_commit_via_vite}` (the frontend value is duplicated from `import.meta.env` on the client; the API returns only backend values). A new `BuildInfo` component renders a compact two-line metadata block in the Sidebar footer, replacing the hardcoded `v0.0.1`. The four-iteration DAG is strictly serial (infra to infra to backend to frontend) because every layer depends on the env vars produced by the previous one; parallelism is not achievable without violating that chain. Frontend vs backend timestamp divergence is surfaced with a 5-minute threshold (within: show single backend time; beyond: show both with role labels).

## Components

### Data
- No persistent data model changes. Build metadata flows env vars to API JSON response to React state; nothing is persisted to SQLite.

### Backend
- `backend/Dockerfile`: declare `ARG BUILD_COMMIT` / `ARG BUILD_TIME`; set `ENV BUILD_COMMIT=$BUILD_COMMIT` / `ENV BUILD_TIME=$BUILD_TIME` near the end of the file so values persist to the running layer.
- `backend/app/main.py`: register a new `GET /api/info` route returning `{"commit_sha": os.environ.get("BUILD_COMMIT"), "build_time": os.environ.get("BUILD_TIME"), "repo_url": os.environ.get("BUILD_REPO_URL")}`. Same Basic Auth as the rest of `/api/*` (Caddy handles it). No new dependency injection.
- `backend/tests/test_info_endpoint.py`: pytest cases for present and absent env vars, response shape, and null handling.

### Frontend
- `frontend/Dockerfile`: declare `ARG VITE_BUILD_COMMIT` / `ARG VITE_BUILD_TIME` / `ARG VITE_BUILD_REPO_URL` in the node builder stage before `npm run build`, so Vite can inline them as `import.meta.env.VITE_*` constants.
- `frontend/src/types.ts`: add `BuildInfo` type (`commit_sha`, `build_time`, `repo_url` — all `string | null`).
- `frontend/src/api.ts`: add `getInfo(): Promise<BuildInfo>` that GETs `/api/info`.
- `frontend/src/hooks/useBuildInfo.ts`: React Query hook with 5-minute `staleTime`, gracefully falls back to `null` fields on network error so the sidebar never breaks.
- `frontend/src/components/BuildInfo.tsx`: presentational component. Renders short SHA (clickable link to `${repo_url}/commit/${sha}` when both non-null; plain monospace otherwise; empty when SHA null). Renders build timestamp: compares backend `build_time` with `import.meta.env.VITE_BUILD_TIME`; if within 5 minutes shows single "Built 2026-05-31 15:30 UTC" line; if beyond 5 minutes shows two labeled lines ("API: ...", "UI: ..."). Fixed min-height to prevent layout shift.
- `frontend/src/components/Sidebar.tsx`: footer row replaces the `v0.0.1` span with `<BuildInfo />`; ThemePicker remains on the left, BuildInfo on the right. Mobile close button in the header (lines 113-122) is untouched.

### Infra
- `deploy/upgrade.sh`: new repo-tracked script (currently only host-resident at `/opt/cronos/upgrade.sh`). Sequence: `git fetch origin && git reset --hard origin/main`; `COMMIT_SHA=$(git rev-parse --short HEAD)`; `BUILD_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)`; `REPO_URL=$(git remote get-url origin | sed -E 's/^git@github.com:/https:\/\/github.com\//; s/\.git$//')`; `docker compose -f docker-compose.yml -f docker-compose.prod.yml build --build-arg BUILD_COMMIT=$COMMIT_SHA --build-arg BUILD_TIME=$BUILD_TIME --build-arg BUILD_REPO_URL=$REPO_URL --build-arg VITE_BUILD_COMMIT=$COMMIT_SHA --build-arg VITE_BUILD_TIME=$BUILD_TIME --build-arg VITE_BUILD_REPO_URL=$REPO_URL`; `sudo systemctl restart cronos.service`.
- `deploy/VPS_SETUP.md`: §10 update adds one-line `sudo install -m 755 /opt/cronos/deploy/upgrade.sh /opt/cronos/upgrade.sh` step to the install path and documents that the canonical source is now the repo file.
- `docker-compose.yml`: add `build.args` (`BUILD_COMMIT`, `BUILD_TIME`, `BUILD_REPO_URL`) on backend service and `VITE_BUILD_COMMIT` / `VITE_BUILD_TIME` / `VITE_BUILD_REPO_URL` on frontend service; expose `BUILD_COMMIT`, `BUILD_TIME`, `BUILD_REPO_URL` in backend `environment` block so the Dockerfile-baked values reach the running process.
- `docker-compose.prod.yml`: mirror the same `build.args` and `environment` additions on top of the base file overlay.

## Implementation plan

| ID  | Type     | Depends on | Scope files (abridged)                                                                                                                    | Validation                                                                                                       |
|-----|----------|------------|-------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------|
| I1  | infra    | -          | deploy/upgrade.sh, deploy/VPS_SETUP.md                                                                                                    | bash -n deploy/upgrade.sh && grep -E 'git rev-parse --short HEAD\|date -u' deploy/upgrade.sh                     |
| I2  | infra    | I1         | backend/Dockerfile, frontend/Dockerfile, docker-compose.yml, docker-compose.prod.yml                                                      | docker compose config --quiet (both base and prod overlay)                                                       |
| I3  | backend  | I2         | backend/app/main.py, backend/tests/test_info_endpoint.py                                                                                  | cd backend && pytest tests/test_info_endpoint.py -v                                                              |
| I4  | frontend | I3         | frontend/src/api.ts, frontend/src/types.ts, frontend/src/hooks/useBuildInfo.ts, frontend/src/components/BuildInfo.tsx, Sidebar.tsx, test  | cd frontend && npm test -- src/components/__tests__/BuildInfo.test.tsx --run                                     |

## Risks

| Risk                                                                                       | Severity | Mitigation                                                                                                                                                                                  |
|--------------------------------------------------------------------------------------------|----------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| deploy/upgrade.sh is net-new in the repo; host installation may diverge                    | high     | I1 commits canonical version AND updates VPS_SETUP.md with `sudo install` step to refresh /opt/cronos/upgrade.sh from /opt/cronos/deploy/upgrade.sh after every pull.                        |
| Partial rebuild (backend only) leaves stale VITE_BUILD_COMMIT in served bundle             | medium   | upgrade.sh rebuilds both images together; BuildInfo shows both timestamps when they diverge >5min, surfacing the mistake to the operator.                                                   |
| /api/info exposes deployed commit, aiding attacker fingerprinting                          | low      | Same SHA is already embedded in served JS bundle; no new disclosure. Docstring on endpoint warns reviewers not to relax auth.                                                                |
| Local dev / CI runs without BUILD_COMMIT or BUILD_TIME env vars                            | medium   | Backend reads via `os.environ.get(..., None)`; test_info_endpoint.py has explicit absent-env case asserting HTTP 200 with null fields.                                                       |
| Sidebar layout shift while /api/info is in flight                                          | low      | BuildInfo reserves fixed min-height slot; renders empty whitespace during fetch; loading-state test in BuildInfo.test.tsx asserts no DOM size change.                                       |

## Assumptions

- The repo's `git remote get-url origin` returns a GitHub URL (HTTPS or SSH form); the sed normalization in `upgrade.sh` handles both. If the remote points to a non-GitHub host the link will be malformed — that is an acceptable degradation since the operator can still read the SHA as plain text.
- The 5-minute threshold for "frontend and backend timestamps are close enough to show one" is a design decision per R7. Operators running on a single VPS where upgrade.sh rebuilds both images in one invocation will always see a single timestamp; the divergence path exists only to defend against partial-rebuild operator errors.
- `BUILD_REPO_URL` is treated as the third build arg (not in the analysis YAML's explicit list, but the analysis "deferred" the GitHub link only because no upstream mechanism for REPO_URL was proposed; we propose one here, so the link becomes in-scope under R5's "clickable link when repo URL is available" clause).
- Tests own their own scope inside each iteration: I3 includes `test_info_endpoint.py`, I4 includes `BuildInfo.test.tsx`. The phase-6 tester will additionally run the broader pytest/vitest suites; per-iteration validation commands are scoped to the new files to keep implementor diffs auditable.

## Open questions

- None.

## Next consumer brief

Implementors: read `iterations[]` (YAML), pick your assigned `id`, and treat `scope_files` as a HARD diff boundary — no edits outside it. Cross-iteration invariants the YAML does NOT express:

1. **Env var name constancy**: `BUILD_COMMIT`, `BUILD_TIME`, `BUILD_REPO_URL` (backend) and `VITE_BUILD_COMMIT`, `VITE_BUILD_TIME`, `VITE_BUILD_REPO_URL` (frontend) MUST be spelled identically across upgrade.sh (I1), both Dockerfiles + both compose files (I2), main.py (I3), and the Vite-embedded references in BuildInfo.tsx (I4). One typo breaks the entire chain silently. The phase-6 tester will only catch this if both I3 and I4 tests run after a real build.
2. **API response shape**: `/api/info` returns exactly three keys: `commit_sha`, `build_time`, `repo_url` (all `string | null`). The `types.ts` `BuildInfo` interface in I4 must match exactly. No other keys are added in this iteration; future fields require a new design.
3. **R7 threshold constant**: `BUILD_TIME_DIVERGENCE_MS = 5 * 60 * 1000` lives in `BuildInfo.tsx`. Do not duplicate it elsewhere.
4. **VPS_SETUP.md edit (I1)**: insert ONE `sudo install -m 755 /opt/cronos/deploy/upgrade.sh /opt/cronos/upgrade.sh` line in §10.1 or §5.2 (post-clone setup), and add a note that the script is now repo-tracked. Do not rewrite other sections.

No unresolved open questions for the implementor — analysis closed all four design decision points (new /api/info chosen, 5-minute threshold chosen, GitHub link in-scope via REPO_URL arg, sidebar footer-replace chosen).
