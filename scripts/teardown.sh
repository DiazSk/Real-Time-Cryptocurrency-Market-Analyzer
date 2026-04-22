#!/usr/bin/env bash
# Removes all containers, networks, and volumes for a clean slate.
# This is destructive — all persisted data will be lost.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$REPO_ROOT"

echo "WARNING: This will permanently delete all containers and data volumes."
read -rp "Are you sure? [y/N] " confirm

if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 0
fi

echo "Stopping producer (if running)..."
pkill -f "src.producers.crypto_price_producer" 2>/dev/null || true

echo "Removing containers, networks, and volumes..."
docker-compose down -v --remove-orphans

echo "Teardown complete."
