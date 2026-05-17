#!/usr/bin/env bash
set -euo pipefail

# Allow root (webhook service) to run git in a cronos-owned directory.
git config --global --add safe.directory "$(pwd)"
git pull
docker compose \
  --env-file .env \
  -f docker-compose.yml -f docker-compose.prod.yml \
  up -d --build
sudo systemctl restart cronos.service
