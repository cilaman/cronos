#!/usr/bin/env bash
set -euo pipefail

git -c safe.directory="$(pwd)" pull
docker compose \
  --env-file .env \
  -f docker-compose.yml -f docker-compose.prod.yml \
  up -d --build
sudo systemctl restart cronos.service
