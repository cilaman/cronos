# Cronos

Personal Kanban-style task manager for orchestrating Claude Code agents.
Runs in Docker on a single VPS, authenticated against a Claude Pro/Max
subscription via OAuth.

> **Status:** Iteration 5 — deploy + ops polish. Task CRUD, drag-and-drop,
> agent execution, and waiting-state replies all work end-to-end. The stack
> is ready to deploy to a VPS. See [the plan](../.claude/plans/goal-of-this-workspace-cosmic-minsky.md).

## Quick start (local)

```bash
docker compose up --build
# Open http://localhost:8080
```

You should see the Cronos board. Without a Claude OAuth token, agent runs
will fail (the binary reports "no credentials"); CRUD and the file watcher
work regardless. To run agents locally, export the token before starting:

```bash
export CLAUDE_CODE_OAUTH_TOKEN=$(claude setup-token)
docker compose up --build
```

`/api/health` reports `claude_on_path: true` (the CLI is baked into the
backend image), `worker_running: true`, and `tasks_indexed: <N>`.

## Deploying to a VPS

See [deploy/VPS_SETUP.md](deploy/VPS_SETUP.md) for the full checklist:
hardening, Docker install, OAuth token provisioning, TLS, basic auth,
systemd autostart, and nightly `/data` backups.

## Ops at a glance

- **Health:** `GET /api/health` — returns 200 only when dirs exist, the
  task index loaded, and the worker loop is alive. The backend container
  has a Docker `healthcheck` that hits the same endpoint every 30 s.
- **Logs:** `docker compose logs -f backend caddy`. The prod overlay caps
  each service at `10m × 5` rotated `json-file` logs.
- **Backups:** `cronos-backup.timer` tars `/opt/cronos/data` to
  `/var/backups/cronos/` daily at ~03:17 UTC, keeping the last 14.
  Trigger manually with `sudo systemctl start cronos-backup.service`.
- **Token rotation:** rerun `claude setup-token` on your Mac, replace
  `~/.config/claude/env` on the VPS (`chmod 600`), then
  `docker compose ... restart backend`. Revoke the old token in your
  Claude account settings.

## Layout

```
backend/   FastAPI app (Python 3.12) + bundled Claude Code CLI (Node 22)
frontend/  Vite + React + TS + Tailwind; built into a Caddy image
deploy/    VPS setup docs, systemd units, backup script
data/      Per-deployment state (tasks/, workspaces/, cronos.db). Gitignored.
Caddyfile        Production Caddy config (TLS, basic auth)
Caddyfile.dev    Local dev Caddy config (HTTP, no auth)
docker-compose.yml      Local stack
docker-compose.prod.yml Production overlay (env_file, healthcheck, log rotation)
```
