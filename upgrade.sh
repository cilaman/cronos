#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

git -c safe.directory="$(pwd)" fetch origin
git -c safe.directory="$(pwd)" reset --hard origin/main

docker compose \
  --env-file .env \
  -f docker-compose.yml -f docker-compose.prod.yml \
  build

sudo systemctl restart cronos.service
