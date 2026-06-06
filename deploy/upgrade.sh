#!/usr/bin/env bash
# deploy/upgrade.sh — repo-tracked upgrade script for Cronos on VPS.
# Fetches latest main, rebuilds both images with baked-in build metadata,
# and restarts the systemd service.
#
# Run as the cronos user (requires sudoers rule for systemctl restart).
# Install to host path after every pull:
#   sudo install -m 755 /opt/cronos/deploy/upgrade.sh /opt/cronos/upgrade.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

# This repo checkout doubles as the live cronos-development space, so the worker
# writes task/goal state (and traces, stats, harness runs) into git-TRACKED files
# under .cronos/. `git reset --hard` reverts tracked files to the committed
# revision, which would roll completed work back to active/waiting and make it
# "respawn" after the restart. Snapshot these runtime dirs, then restore them
# after the reset so persisted state survives the upgrade. Workspaces are
# excluded on purpose — they contain git worktrees that must not be copied.
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

echo "==> Fetching latest main..."
git fetch origin
git reset --hard origin/main

echo "==> Restoring live runtime state preserved across the reset..."
for d in "${RUNTIME_STATE_DIRS[@]}"; do
  [ -d "$STATE_BACKUP/$d" ] || continue
  rm -rf "$d"
  mkdir -p "$(dirname "$d")"
  cp -a "$STATE_BACKUP/$d" "$d"
done
rm -rf "$STATE_BACKUP"

echo "==> Resolving build metadata..."
COMMIT_SHA=$(git rev-parse --short HEAD)
BUILD_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
REPO_URL=$(git remote get-url origin | sed -E 's/^git@github\.com:/https:\/\/github.com\//; s/\.git$//')

echo "    commit : $COMMIT_SHA"
echo "    time   : $BUILD_TIME"
echo "    repo   : $REPO_URL"

echo "==> Building images..."
docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  build \
  --build-arg BUILD_COMMIT="$COMMIT_SHA" \
  --build-arg BUILD_TIME="$BUILD_TIME" \
  --build-arg BUILD_REPO_URL="$REPO_URL" \
  --build-arg VITE_BUILD_COMMIT="$COMMIT_SHA" \
  --build-arg VITE_BUILD_TIME="$BUILD_TIME" \
  --build-arg VITE_BUILD_REPO_URL="$REPO_URL"

echo "==> Restarting service..."
sudo systemctl restart cronos.service

echo "==> Upgrade complete (commit $COMMIT_SHA)."
