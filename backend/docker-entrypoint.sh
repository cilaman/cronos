#!/bin/sh
# The Claude CLI keeps auth at /root/.claude.json but only its sessions live
# under /root/.claude/ — which is the only path our compose file persists.
# Each `docker compose up --build` therefore wipes the login. Restore it from
# the most recent backup the CLI itself writes into the persisted volume.
set -e

CLAUDE_JSON="/root/.claude.json"
BACKUPS_DIR="/root/.claude/backups"

if [ ! -f "$CLAUDE_JSON" ] && [ -d "$BACKUPS_DIR" ]; then
  latest=$(ls -1t "$BACKUPS_DIR"/.claude.json.backup.* 2>/dev/null | head -n1)
  if [ -n "$latest" ] && [ -f "$latest" ]; then
    echo "[entrypoint] restoring $CLAUDE_JSON from $latest"
    cp "$latest" "$CLAUDE_JSON"
  fi
fi

exec "$@"
