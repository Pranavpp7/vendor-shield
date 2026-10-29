#!/usr/bin/env bash
# Run on a fresh Oracle Always Free Ampere VM after cloning this repo.
# See docs/DEPLOY.md — this does not create the tenancy for you.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Missing .env in repo root. Copy deploy.env.example to .env and fill keys."
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Installing Docker..."
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER" || true
fi

# Compose v2 plugin
if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose not found. Install Docker Engine with the compose plugin."
  exit 1
fi

echo "Building images (first time on Ampere: 15–40 min, BGE bake)..."
docker compose --profile full up -d --build

echo "Waiting for /api/health..."
for i in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
    echo "App is healthy on :8000"
    curl -fsS http://127.0.0.1:8000/api/health
    echo
    echo "Open port 80 (and 443 if SITE_ADDRESS is a hostname) in the VCN security list."
    echo "Caddy is on :80. Do not open 6333/8000 to the internet."
    exit 0
  fi
  sleep 5
done

echo "Timed out waiting for health. docker compose --profile full logs app"
docker compose --profile full logs --tail 80 app
exit 1
