#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# This repo checkout doubles as the live cronos-development space, so the worker
# writes task/goal state (and traces, stats, harness runs) into git-TRACKED files
# under .cronos/. `git reset --hard` reverts tracked files to the committed
# revision, which would roll completed work back to active/waiting and make it
# "respawn" after the restart. Snapshot these runtime dirs, then restore them
# after the reset so persisted state survives the upgrade. Workspaces are
# excluded on purpose — they contain git worktrees that must not be copied.
preserve_runtime_state() {
  RUNTIME_STATE_DIRS=(
    .cronos/tasks
    .cronos/traces
    .cronos/stats
    .cronos/harness-runs
    .cronos/test-reports
  )
  STATE_BACKUP="$(mktemp -d)"
  for d in "${RUNTIME_STATE_DIRS[@]}"; do
    [ -d "$d" ] || continue
    mkdir -p "$STATE_BACKUP/$(dirname "$d")"
    cp -a "$d" "$STATE_BACKUP/$d"
  done
}

restore_runtime_state() {
  for d in "${RUNTIME_STATE_DIRS[@]}"; do
    [ -d "$STATE_BACKUP/$d" ] || continue
    rm -rf "$d"
    mkdir -p "$(dirname "$d")"
    cp -a "$STATE_BACKUP/$d" "$d"
  done
  rm -rf "$STATE_BACKUP"
}

preserve_runtime_state
git -c safe.directory="$(pwd)" fetch origin
git -c safe.directory="$(pwd)" reset --hard origin/main
restore_runtime_state

ENV_FILE=".env"
[ -f "$ENV_FILE" ] || ENV_FILE="/opt/cronos/.env"
[ -f "$ENV_FILE" ] || { echo "ERROR: .env not found at $(pwd)/.env or /opt/cronos/.env"; exit 1; }

docker compose \
  --env-file "$ENV_FILE" \
  -f docker-compose.yml -f docker-compose.prod.yml \
  build

sudo systemctl restart cronos.service
