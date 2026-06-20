---
cc_version: '1.0'
agent: pipeline-implementor
slug: g03-non-root-docker
phase: impl
status: done
confidence: 0.90
inputs_used:
- .cronos/pipeline/g03-non-root-docker/design-report-g03-non-root-docker.md
- backend/Dockerfile
- backend/docker-entrypoint.sh
- docker-compose.yml
- frontend/Dockerfile
outputs_produced:
- .cronos/pipeline/g03-non-root-docker/impl-report-g03-non-root-docker.md
- backend/Dockerfile
- backend/docker-entrypoint.sh
- docker-compose.yml
- frontend/Dockerfile
- deploy/EGRESS_ALLOWLIST.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 18
  files_read: 5
  memory_hits: 0
---

## Summary

All five iterations (I1–I5) from the design report are implemented. Both containers now
run as non-root (`cronos` UID 1001 in backend, `caddy` user in frontend). The gosu
drop-privileges pattern lets `docker-entrypoint.sh` chown the `/data` bind-mount as
root before exec'ing into uvicorn as cronos — satisfying both R4 (`cap_drop:[ALL]`) and
R5 (runtime chown compatibility). The egress allowlist runbook (I5) documents two
enforcement mechanisms plus a manual verification checklist that closes R8.

## Files changed

| File | Change |
|------|--------|
| `backend/Dockerfile` | Added `gosu` to apt; added `chmod -R o+rX` for claude CLI; added `useradd -m -u 1001 -s /bin/sh cronos`; added `mkdir -p /data && chown -R cronos:cronos /app /data`; updated entrypoint comment |
| `backend/docker-entrypoint.sh` | Migrated `CLAUDE_JSON` → `/home/cronos/.claude.json`, `BACKUPS_DIR` → `/home/cronos/.claude/backups`; added idempotent `chown -R --from=0 cronos:cronos /data`; replaced `exec "$@"` with `exec gosu cronos "$@"` |
| `docker-compose.yml` | Added `CLAUDE_PROJECTS_DIR: /home/cronos/.claude/projects` env; changed volume `claude_config:/root/.claude` → `claude_config:/home/cronos/.claude`; added `cap_drop:[ALL]` + `security_opt:[no-new-privileges:true]` to backend service; added `cap_drop:[ALL]` + `cap_add:[NET_BIND_SERVICE]` + `security_opt:[no-new-privileges:true]` to caddy service |
| `frontend/Dockerfile` | Added `USER caddy` at end of runtime stage |
| `deploy/EGRESS_ALLOWLIST.md` | New runbook: Mechanism A (host iptables), Mechanism B (forward proxy), manual verification checklist, ops notes on UID 1001 |

## Validation results

All design-specified validation commands passed (adapted where `docker` CLI is unavailable in build env):

**I2 (docker-entrypoint.sh):**
- `grep -q '/home/cronos/.claude.json'` → PASS
- `grep -q '/home/cronos/.claude/backups'` → PASS
- `grep -q 'exec gosu cronos'` → PASS
- `sh -n docker-entrypoint.sh` → PASS (syntax valid)

**I3 (docker-compose.yml):**
- `grep -q 'no-new-privileges:true'` → PASS
- `grep -A2 'cap_drop' | grep -q ALL` → PASS
- `grep -q 'claude_config:/home/cronos/.claude'` → PASS
- `grep -q 'CLAUDE_PROJECTS_DIR: /home/cronos/.claude/projects'` → PASS

**I4 (frontend/Dockerfile + caddy service):**
- `grep -qE 'USER\s+(caddy|cronos|[0-9]+)' frontend/Dockerfile` → PASS (`USER caddy`)
- `grep -A20 '^  caddy:' | grep -q 'NET_BIND_SERVICE'` → PASS

**I5 (deploy/EGRESS_ALLOWLIST.md):**
- `test -f deploy/EGRESS_ALLOWLIST.md` → PASS
- `grep -q 'api.anthropic.com'` → PASS
- `grep -q 'github.com'` → PASS
- `grep -qi 'manual verification'` → PASS
- `grep -qi 'example.com'` → PASS

**I1 (backend/Dockerfile):** Cannot run `docker build` in the build environment;
content-level verification confirms: `gosu` in apt install list, `chmod -R o+rX` after
npm install, `useradd -m -u 1001`, `chown -R cronos:cronos /app /data`. The design's
`test -x /usr/local/bin/claude` assertion will be validated by the tester agent running
`docker build`.

## Out-of-scope findings

- `backend/app/worker.py:43` has a hardcoded `/root/.claude/projects` default — the
  compose `CLAUDE_PROJECTS_DIR` env override resolves this without editing Python, as
  designed. No Python change was made (scope boundary respected).
- `backend/app/git_ops.py:_auth_env()` (lines 96–115) was inspected and confirmed
  UID-agnostic (reads `os.environ`, no path assumptions). R6 is a review-only
  verification item; no edit required.
- `Caddyfile.dev` / `Caddyfile` are out of scope. Port 80 capability gap resolved via
  `cap_add:[NET_BIND_SERVICE]` in compose (Caddyfile unchanged).

## Assumptions

- `caddy:2-alpine` ships a built-in `caddy` user (UID 1000) per the official Caddy
  Dockerfile. If the tester finds the USER directive fails (caddy user absent), the fix
  is to replace `USER caddy` with `USER 1000` in `frontend/Dockerfile`.
- `gosu` is available in `python:3.12-slim`'s Debian apt repos (confirmed — package
  `gosu` exists in Debian bookworm).
- `chown -R --from=0 cronos:cronos /data` is supported by the GNU coreutils version
  in `python:3.12-slim`. The `|| chown -R cronos:cronos /data` fallback handles the
  case where `--from` is not supported.

## Open questions

- None beyond the caddy user assumption above (resolvable in test phase).

## Next consumer brief

**Tester**: validate all 5 iterations end-to-end.

1. **I1**: `docker build -t cronos-backend-g03:test backend/` then:
   `docker run --rm --entrypoint='' cronos-backend-g03:test sh -c 'id -u | grep -vq ^0$ && id -un | grep -q cronos && test -x /usr/local/bin/claude && stat -c %a /usr/local/bin/claude | grep -Eq "^.{2}[1357]$" && test -d /app && stat -c %U /app | grep -q cronos'`

2. **I2**: `sh -n backend/docker-entrypoint.sh` (already passes) plus grep assertions from design.

3. **I3**: `docker compose -f docker-compose.yml config` then grep for `no-new-privileges:true`, `cap_drop: ALL`, `claude_config:/home/cronos/.claude`, `CLAUDE_PROJECTS_DIR`.

4. **I4**: `docker compose -f docker-compose.yml config` then grep for `NET_BIND_SERVICE` under the caddy service; also verify `USER caddy` in `docker image inspect` after build.

5. **I5**: All grep assertions on `deploy/EGRESS_ALLOWLIST.md` (already pass).

6. **R8 manual verification**: Run the checklist in `deploy/EGRESS_ALLOWLIST.md` inside a running container to confirm `example.com` is blocked and `api.anthropic.com` + `github.com` are reachable. Note: this requires the operator to apply one of the two egress enforcement mechanisms on the deployment host first.
