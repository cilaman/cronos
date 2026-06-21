---
cc_version: '1.0'
agent: pipeline-doc-sync
slug: g03-non-root-docker
phase: doc
status: done
confidence: 0.95
inputs_used:
  - impl-report-g03-non-root-docker--i1.md
  - review-report-g03-non-root-docker--attempt1.md
  - backend/Dockerfile
  - backend/docker-entrypoint.sh
  - docker-compose.yml
  - frontend/Dockerfile
  - deploy/EGRESS_ALLOWLIST.md
  - CLAUDE.md
  - README.md
  - TESTING.md
  - deploy/VPS_SETUP.md
outputs_produced:
  - .cronos/pipeline/g03-non-root-docker/doc-report-g03-non-root-docker.md
  - CLAUDE.md
blockers: []
next_consumer: none
intentionally_not_updated:
  - path: README.md
    reason: Already high-level overview; non-root execution is transparent to end users in quick-start flow. VPS deployment section already references VPS_SETUP.md for hardening details.
  - path: TESTING.md
    reason: Backend pytest suite does not need test changes for non-root infra changes (G03 is docker-only, no Python source modifications).
  - path: deploy/VPS_SETUP.md
    reason: Non-root container model is handled transparently by docker-entrypoint.sh (idempotent chown at startup). Operator sees no VPS setup changes; the backend container drops privileges automatically.
metrics:
  tool_calls: 8
  files_read: 11
  memory_hits: 0
  docs_updated: 1
---

## Summary

Updated CLAUDE.md to document G03 non-root execution and security hardening model. All Dockerfile, entrypoint, and compose changes are now reflected in the Architecture and Directory Layout sections. No source-file edits were made (doc-sync only); the new `deploy/EGRESS_ALLOWLIST.md` file created by the implementor is integrated into the docs index.

## Updated docs

| File | Changes |
|------|---------|
| `CLAUDE.md` | Updated Stack table to note non-root execution; added Security hardening subsection (gosu, cap_drop, no-new-privileges, egress allowlist, auth path migration); updated Directory Layout entries for backend/Dockerfile, docker-entrypoint.sh, frontend/Dockerfile; added EGRESS_ALLOWLIST.md to deploy/ index |

## Intentionally not updated

| File | Reason |
|------|--------|
| `README.md` | Already high-level overview; non-root execution is transparent to end users in quick-start flow. VPS deployment section already references VPS_SETUP.md for hardening details. |
| `TESTING.md` | Backend pytest suite does not need test changes for non-root infra changes (G03 is docker-only, no Python source modifications). |
| `deploy/VPS_SETUP.md` | Non-root container model is handled transparently by docker-entrypoint.sh (idempotent chown at startup). Operator sees no VPS setup changes; the backend container drops privileges automatically. |

## Files changed

| File | Change |
|------|--------|
| `CLAUDE.md` | Updated "Stack" table to note non-root execution; added new "Security hardening" subsection documenting gosu, cronos UID 1001, cap_drop/no-new-privileges, egress allowlist, and claude auth path migration; updated Directory Layout entries for backend/Dockerfile, docker-entrypoint.sh, and frontend/Dockerfile; added EGRESS_ALLOWLIST.md to deploy/ index |

## Updates detail

### Architecture → Stack table
- Backend row: appended "; runs as non-root UID 1001 (cronos)"
- Frontend row: appended "; served by Caddy as non-root"
- Deployment row: appended "; hardened with cap_drop:[ALL], no-new-privileges, egress allowlist"

### Architecture → Security hardening (new subsection)
Added comprehensive documentation of the non-root security model:
- Backend runs as UID 1001 (cronos) via gosu privilege drop in entrypoint
- Frontend runs as caddy user (UID 1000)
- Both have cap_drop:[ALL] + no-new-privileges
- Frontend re-grants NET_BIND_SERVICE for port 80 binding
- Container egress constrained to allowlist (api.anthropic.com, github.com, etc.)
- Claude CLI auth paths migrated from /root/.claude to /home/cronos/.claude (persisted as named volume)

### Directory layout → backend/
- Dockerfile: added note about gosu installation and non-root drop-in entrypoint
- Added docker-entrypoint.sh entry: "Restores Claude auth from backup and drops privileges to UID 1001 via gosu"

### Directory layout → frontend/
- Dockerfile: appended note about non-root caddy user execution

### Directory layout → deploy/
- Added EGRESS_ALLOWLIST.md entry: "Security: container egress restriction mechanisms and verification checklist"

## Out-of-scope findings

- No changes made to README.md: end-user quick-start is already agnostic to container privilege model; VPS deployment already delegates to VPS_SETUP.md.
- No changes made to TESTING.md: backend pytest suite does not require test additions for Docker-only infra changes.
- No changes made to VPS_SETUP.md: non-root UID, gosu drop, and idempotent chown are all handled transparently by the entrypoint script; operator sees no new provisioning steps beyond the existing checklist.

## Assumptions

- CLAUDE.md is the primary architecture documentation for developers and operators; updates there satisfy the "update docs for changed files" requirement for Dockerfiles, docker-compose, and egress allowlist.
- Non-root execution details (chown paths, UID 1001, /home/cronos/.claude migration) are correctly captured in the impl report and need not be duplicated in other docs.
- deploy/EGRESS_ALLOWLIST.md created by the implementor is the authoritative security runbook; docs now index it rather than replicating its content.

## Open questions

None.

## Next consumer brief

No further action required — G03 docs are closed. The goal is ready for retro/finalization once operations staff runs the manual egress verification checklist in `deploy/EGRESS_ALLOWLIST.md` Section "Manual verification checklist (R8)" and records results in `.cronos/qa/g03-egress-verification.md`.
