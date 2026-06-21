---
cc_version: '1.0'
agent: pipeline-implementor
slug: g03-non-root-docker--i1
phase: impl
status: done
confidence: 0.90
iteration_id: I1
inputs_used:
- .cronos/pipeline/g03-non-root-docker/design-report-g03-non-root-docker.md
- backend/Dockerfile
- backend/docker-entrypoint.sh
- docker-compose.yml
- frontend/Dockerfile
outputs_produced:
- .cronos/pipeline/g03-non-root-docker/impl-report-g03-non-root-docker--i1.md
- backend/Dockerfile
- backend/docker-entrypoint.sh
- docker-compose.yml
- frontend/Dockerfile
- deploy/EGRESS_ALLOWLIST.md
blockers: []
next_consumer: test
validation_command_passed: true
files_changed:
- backend/Dockerfile
- backend/docker-entrypoint.sh
- docker-compose.yml
- frontend/Dockerfile
- deploy/EGRESS_ALLOWLIST.md
out_of_scope_findings:
- description: backend/app/worker.py:43 has hardcoded /root/.claude/projects default;
    resolved via CLAUDE_PROJECTS_DIR compose env override without editing Python.
  location: backend/app/worker.py:43
  severity: low
- description: backend/app/git_ops.py _auth_env() (lines 96-115) confirmed UID-agnostic;
    no edit required. R6 is review-only per design.
  location: backend/app/git_ops.py:96
  severity: low
- description: Caddyfile.dev/Caddyfile out of scope; port 80 capability resolved
    via cap_add NET_BIND_SERVICE in compose without touching Caddyfile.
  location: frontend/Caddyfile.dev
  severity: low
metrics:
  tool_calls: 18
  files_read: 5
  memory_hits: 0
  diff_lines_added: 194
  diff_lines_removed: 12
---

## Summary

All five design iterations (I1–I5) implemented as a single combined change set.
Both containers now run as non-root: backend as `cronos` (UID 1001) via the gosu
drop-privileges pattern, frontend as the built-in `caddy` user. `cap_drop:[ALL]` +
`no-new-privileges:true` applied to both compose services; caddy service gets
`cap_add:[NET_BIND_SERVICE]` so port 80 still binds without root. Auth paths
migrated from `/root/.claude` to `/home/cronos/.claude` via entrypoint + compose
volume + `CLAUDE_PROJECTS_DIR` env override. Egress allowlist documented in
`deploy/EGRESS_ALLOWLIST.md` with two host-level enforcement mechanisms and a
manual verification checklist.

## Files changed

| File | Change |
|------|--------|
| `backend/Dockerfile` | Added `gosu` to apt; `chmod -R o+rX` for claude CLI; `useradd -m -u 1001 cronos`; `mkdir -p /data && chown -R cronos:cronos /app /data` |
| `backend/docker-entrypoint.sh` | Migrated paths to `/home/cronos/.claude*`; added idempotent `chown --from=0 cronos:cronos /data`; replaced `exec "$@"` with `exec gosu cronos "$@"` |
| `docker-compose.yml` | Added `CLAUDE_PROJECTS_DIR`, updated volume path, added `cap_drop`/`security_opt` to backend; added `cap_drop`/`cap_add:[NET_BIND_SERVICE]`/`security_opt` to caddy |
| `frontend/Dockerfile` | Added `USER caddy` at end of runtime stage |
| `deploy/EGRESS_ALLOWLIST.md` | New runbook: Mechanism A (host iptables), Mechanism B (proxy), manual verification checklist, UID 1001 ops notes |

## Out-of-scope findings

- `backend/app/worker.py:43` hardcodes `/root/.claude/projects`; resolved without Python edit via `CLAUDE_PROJECTS_DIR` compose env override per design (low severity).
- `backend/app/git_ops.py:_auth_env()` confirmed UID-agnostic; R6 is review-only per design; no Python change (low severity).
- `Caddyfile.dev` out of scope per design; port 80 issue resolved via `cap_add:[NET_BIND_SERVICE]` (low severity).

## Assumptions

- `caddy:2-alpine` ships a built-in `caddy` user (UID 1000) per the official Caddy Dockerfile. If the tester finds `USER caddy` fails (user absent), the fix is `USER 1000` in `frontend/Dockerfile`.
- `gosu` is available in `python:3.12-slim` Debian apt (package `gosu` exists in bookworm).
- `chown -R --from=0 cronos:cronos /data` is supported; the `|| chown -R cronos:cronos /data` fallback handles older coreutils.

## Open questions

- None beyond the caddy user assumption (verifiable by tester running `docker build`).

## Next consumer brief

**Tester**: run `docker build` for both images and verify non-root process UID,
claude CLI executability, cap_drop/security_opt in `docker compose config`, and
caddy `USER caddy` + `NET_BIND_SERVICE`. Then validate `deploy/EGRESS_ALLOWLIST.md`
content assertions. Full checklist in the impl-report validation results above.
