---
cc_version: "1.0"
agent: pipeline-doc-sync
slug: showing-commit
phase: doc
status: done
confidence: 0.85
inputs_used:
  - .cronos/pipeline/showing-commit/review-report-showing-commit--attempt1.md
  - .cronos/pipeline/showing-commit/impl-report-showing-commit--i1.md
  - .cronos/pipeline/showing-commit/impl-report-showing-commit--i2.md
  - .cronos/pipeline/showing-commit/impl-report-showing-commit--i3.md
  - .cronos/pipeline/showing-commit/impl-report-showing-commit--i4.md
  - README.md
  - CLAUDE.md
  - deploy/VPS_SETUP.md
outputs_produced:
  - .cronos/pipeline/showing-commit/doc-report-showing-commit.md
  - README.md
  - CLAUDE.md
  - deploy/VPS_SETUP.md
blockers: []
next_consumer: user
intentionally_not_updated:
  - path: backend/app/main.py
    reason: "Source file; documentation covers the new /api/info endpoint; no doc changes needed in the source code itself."
  - path: backend/tests/test_info_endpoint.py
    reason: "Test file; out of scope for documentation updates per CONTRACT.md."
  - path: backend/Dockerfile
    reason: "Infrastructure code; changes are documented in VPS_SETUP.md and CLAUDE.md sections on deployment."
  - path: frontend/Dockerfile
    reason: "Infrastructure code; changes are documented in VPS_SETUP.md upgrade section."
  - path: docker-compose.yml
    reason: "Infrastructure code; build.args and environment changes are documented in VPS_SETUP.md upgrade section."
  - path: docker-compose.prod.yml
    reason: "Infrastructure code; overlay changes are documented in VPS_SETUP.md upgrade section."
  - path: deploy/upgrade.sh
    reason: "Operational script; functionality documented in VPS_SETUP.md §10.1 (Manual upgrade) section."
  - path: frontend/src/api.ts
    reason: "Source file; getInfo() function is documented via useBuildInfo hook and BuildInfo component descriptions in CLAUDE.md."
  - path: frontend/src/types.ts
    reason: "Source file; BuildInfo interface documented in CLAUDE.md module table."
  - path: frontend/src/hooks/useBuildInfo.ts
    reason: "Source file; React Query hook functionality documented in CLAUDE.md key modules and README.md quick start."
  - path: frontend/src/components/BuildInfo.tsx
    reason: "Source file; component purpose and placement documented in CLAUDE.md and README.md."
  - path: frontend/src/components/Sidebar.tsx
    reason: "Source file; BuildInfo integration documented in CLAUDE.md as part of sidebar footer UI."
  - path: frontend/src/components/__tests__/BuildInfo.test.tsx
    reason: "Test file; out of scope per CONTRACT.md. Non-blocking finding F3 (sixth test case for SHA-only branch) noted in review report for future follow-up."
metrics:
  tool_calls: 15
  files_read: 8
  memory_hits: 0
  docs_updated: 3
  docs_considered: 13
---

## Summary

The "showing-commit" goal implements a four-iteration feature to surface build metadata (commit SHA, build timestamp, repository URL) throughout the deployment pipeline and UI. Iteration I1 adds `deploy/upgrade.sh` (repo-tracked infrastructure script); I2 wires build arguments into both Dockerfiles and compose overlays; I3 exposes metadata via a new `GET /api/info` backend endpoint; I4 implements a React Query hook and `BuildInfo` component in the sidebar footer. The implementation passes review with verdict `pass` (operator override for F1 footer placement accepted on 2026-06-01). Documentation has been updated in three key files: README.md now describes the build info UI feature and the `/api/info` endpoint; CLAUDE.md modules table documents the new endpoint, hook, and component; VPS_SETUP.md §10.1 fully details the `upgrade.sh` script's build metadata extraction and Docker build integration, plus verification checklist item for `/api/info`. No documentation changes are required to source files themselves (test files and infrastructure code are covered by operational docs). Non-blocking findings F2-F4 from the review are listed in `intentionally_not_updated[]` for future follow-up (always-show-both timestamps wording, sixth test case for SHA-only branch, per-iteration coverage gate workarounds).

## Updated docs

| File | Change summary |
|------|----------------|
| README.md | Added paragraph describing build info UI display and `/api/info` endpoint availability in the Quick start section. |
| CLAUDE.md | Updated Key modules table to document `/api/info` endpoint in main.py entry; added useBuildInfo hook and BuildInfo component entries to modules table; added deploy/upgrade.sh to Directory layout section. |
| deploy/VPS_SETUP.md | Expanded §10.1 (Manual upgrade) with full description of `upgrade.sh` script functionality including build metadata extraction, Docker build wiring, and commit SHA/timestamp baking; added verification checklist item for `/api/info` endpoint; updated §10.2 webhook section to reference the repo-tracked upgrade script. |

## Intentionally not updated

- **backend/app/main.py** — Source file; documentation covers the new /api/info endpoint; no doc changes needed in the source code itself.
- **backend/tests/test_info_endpoint.py** — Test file; out of scope for documentation updates per CONTRACT.md.
- **backend/Dockerfile** — Infrastructure code; changes are documented in VPS_SETUP.md and CLAUDE.md sections on deployment.
- **frontend/Dockerfile** — Infrastructure code; changes are documented in VPS_SETUP.md upgrade section.
- **docker-compose.yml** — Infrastructure code; build.args and environment changes are documented in VPS_SETUP.md upgrade section.
- **docker-compose.prod.yml** — Infrastructure code; overlay changes are documented in VPS_SETUP.md upgrade section.
- **deploy/upgrade.sh** — Operational script; functionality documented in VPS_SETUP.md §10.1 (Manual upgrade) section.
- **frontend/src/api.ts** — Source file; getInfo() function is documented via useBuildInfo hook and BuildInfo component descriptions in CLAUDE.md.
- **frontend/src/types.ts** — Source file; BuildInfo interface documented in CLAUDE.md module table.
- **frontend/src/hooks/useBuildInfo.ts** — Source file; React Query hook functionality documented in CLAUDE.md key modules and README.md quick start.
- **frontend/src/components/BuildInfo.tsx** — Source file; component purpose and placement documented in CLAUDE.md and README.md.
- **frontend/src/components/Sidebar.tsx** — Source file; BuildInfo integration documented in CLAUDE.md as part of sidebar footer UI.
- **frontend/src/components/__tests__/BuildInfo.test.tsx** — Test file; out of scope per CONTRACT.md. Non-blocking finding F3 (sixth test case for SHA-only branch) noted in review report for future follow-up.

## Assumptions

- Changelog hook: review report states "The UI displays the current commit SHA and build timestamps in the sidebar footer" and "the backend exposes metadata via /api/info endpoint." This user-visible behavior change anchors all documentation updates.
- Build metadata is optional in local dev (upgrade.sh is VPS/deployment-focused); CLAUDE.md and README.md reflect this as "when available."
- Operator accepted F1 (footer placement) on 2026-06-01; no doc disclaimer required per review report.
- Non-blocking findings F2-F4 are recorded in `intentionally_not_updated[]` with pointers for future resolution (timestamp folding wording, test coverage gap, coverage gate workarounds).

## Open questions

- F2 (non-blocking): Review finding flags "single Built ... line when timestamps within 5 min" vs. user request wording "for both." This is a defensible design choice (confirmed by implementation) but not literal to the acceptance wording. No doc action required; design can be clarified in a follow-up if desired.
- F3 (non-blocking): BuildInfo.tsx line 56 (SHA-set / repo-url-null branch) is not covered by tests. A sixth test case could be added to exercise the `<span>{shortSha}</span>` path.
- F4 (non-blocking): Per-iteration validation commands in the design fail against project-wide coverage floors. Backend pyproject.toml and frontend vitest.config.ts both have thresholds that cause single-file test runs to exit 1 even when all tests pass. Future designs should include `--no-cov` workarounds or per-file exclusions.

## Next consumer brief

Documentation has been successfully synced for the "showing-commit" goal. Three files were updated:

1. **README.md** — Added description of the build info UI feature (sidebar footer display of commit SHA and build timestamp) and the new `/api/info` endpoint in the Quick start section.

2. **CLAUDE.md** — Key modules table now documents the `/api/info` endpoint (in backend/app/main.py), the `useBuildInfo` React Query hook, and the `BuildInfo` component. Directory layout section now lists `deploy/upgrade.sh` as the repo-tracked upgrade script.

3. **deploy/VPS_SETUP.md** — §10.1 expanded to fully document the `upgrade.sh` script: it fetches the latest main, extracts commit metadata (SHA, build time, repo URL), and passes these via `--build-arg` to both Dockerfiles. Build metadata is baked into container images and exposed via the `/api/info` endpoint. Verification checklist now includes a check for `/api/info` returning correct metadata.

All implementation files (source code, tests, Dockerfiles, compose files, infrastructure scripts) are covered by these documentation updates. The feature is ready for deployment. Non-blocking follow-ups (F2-F4 from review) are noted above for future work; they do not block this goal's completion.
