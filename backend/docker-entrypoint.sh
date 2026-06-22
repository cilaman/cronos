#!/bin/sh
# The Claude CLI keeps auth at /home/cronos/.claude.json; only per-session
# logs live under /home/cronos/.claude/ — which is the named volume we persist.
# Each `docker compose up --build` wipes the login. Restore it from the most
# recent backup the CLI writes into the persisted volume.
#
# gosu pattern: this script runs as root so it can chown the /data bind-mount
# (cap_drop:[ALL] + no-new-privileges blocks setuid AFTER the privilege drop;
# the initial root→cronos drop here is permitted). The last line drops to the
# cronos user before exec'ing uvicorn.
set -e

CLAUDE_JSON="/home/cronos/.claude.json"
BACKUPS_DIR="/home/cronos/.claude/backups"

if [ ! -f "$CLAUDE_JSON" ] && [ -d "$BACKUPS_DIR" ]; then
  latest=$(ls -1t "$BACKUPS_DIR"/.claude.json.backup.* 2>/dev/null | head -n1)
  if [ -n "$latest" ] && [ -f "$latest" ]; then
    echo "[entrypoint] restoring $CLAUDE_JSON from $latest"
    cp "$latest" "$CLAUDE_JSON"
    chown cronos:cronos "$CLAUDE_JSON"
  fi
fi

# Idempotent: only chown files currently owned by root to avoid unnecessary
# writes on repeated restarts. Suppresses errors if /data is already correct.
chown -R --from=0 cronos:cronos /data 2>/dev/null || chown -R cronos:cronos /data

# The claude_config named volume mounts at /home/cronos/.claude as root:root.
# cronos (UID 1001) must own it to write session-env / shell snapshots / run
# logs. Idempotent: only touch root-owned entries on repeat restarts.
chown --from=0 cronos:cronos /home/cronos 2>/dev/null || true
chown -R --from=0 cronos:cronos /home/cronos/.claude 2>/dev/null || chown -R cronos:cronos /home/cronos/.claude

exec gosu cronos "$@"
