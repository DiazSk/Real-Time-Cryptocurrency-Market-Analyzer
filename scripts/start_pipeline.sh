#!/usr/bin/env bash
# Starts all Docker services and the Kafka producer.
# Performs sequential health checks before proceeding so the producer
# never publishes to a Kafka broker that isn't ready.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$REPO_ROOT"

# ── Dependency check ──────────────────────────────────────────────────────────
for cmd in docker docker-compose curl python3; do
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "ERROR: '$cmd' is required but not found in PATH." >&2
    exit 1
  }
done

# ── Environment ───────────────────────────────────────────────────────────────
if [[ ! -f .env ]]; then
  echo "ERROR: .env file not found. Copy .env.example and fill in values:" >&2
  echo "  cp .env.example .env" >&2
  exit 1
fi
# Export variables for use in health-check commands run on the host.
set -a
# shellcheck disable=SC1091
source .env
set +a

# ── Start infrastructure ──────────────────────────────────────────────────────
echo "Starting Docker services..."
docker-compose up -d

# ── Kafka readiness ───────────────────────────────────────────────────────────
echo "Waiting for Kafka..."
until docker-compose exec -T kafka \
    kafka-topics --bootstrap-server localhost:9092 --list &>/dev/null; do
  sleep 3
done
echo "  Kafka ready."

# ── PostgreSQL readiness ──────────────────────────────────────────────────────
echo "Waiting for PostgreSQL..."
until docker-compose exec -T postgres \
    pg_isready -U "${POSTGRES_USER:-crypto_user}" &>/dev/null; do
  sleep 3
done
echo "  PostgreSQL ready."

# ── Redis readiness ───────────────────────────────────────────────────────────
echo "Waiting for Redis..."
until docker-compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; do
  sleep 2
done
echo "  Redis ready."

# ── Start producer ────────────────────────────────────────────────────────────
echo "Starting crypto price producer..."
python3 -m src.producers.crypto_price_producer &
PRODUCER_PID=$!
echo "  Producer started (PID $PRODUCER_PID)."

echo ""
echo "Pipeline is running."
echo "  Flink UI:    http://localhost:8082"
echo "  Kafka UI:    http://localhost:8081"
echo "  API docs:    http://localhost:8000/docs"
echo "  pgAdmin:     http://localhost:5050"
echo ""
echo "Stop with: bash scripts/stop_pipeline.sh"
