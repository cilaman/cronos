#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

git -c safe.directory="$(pwd)" fetch origin
git -c safe.directory="$(pwd)" reset --hard origin/main

ENV_FILE=".env"
[ -f "$ENV_FILE" ] || ENV_FILE="/opt/cronos/.env"
[ -f "$ENV_FILE" ] || { echo "ERROR: .env not found at $(pwd)/.env or /opt/cronos/.env"; exit 1; }

docker compose \
  --env-file "$ENV_FILE" \
  -f docker-compose.yml -f docker-compose.prod.yml \
  build

sudo systemctl restart cronos.service
