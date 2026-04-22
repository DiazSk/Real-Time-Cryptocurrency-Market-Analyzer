#!/usr/bin/env bash
# Gracefully stops the producer, cancels any running Flink job, then stops Docker services.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$REPO_ROOT"

# ── Stop producer ─────────────────────────────────────────────────────────────
echo "Stopping producer..."
pkill -f "src.producers.crypto_price_producer" 2>/dev/null && echo "  Producer stopped." || echo "  Producer not running."

# ── Cancel Flink job (if JobManager is up) ────────────────────────────────────
echo "Checking for running Flink jobs..."
if curl -sf http://localhost:8082/jobs >/dev/null 2>&1; then
  JOB_ID=$(curl -s http://localhost:8082/jobs \
    | python3 -c "
import sys, json
jobs = json.load(sys.stdin).get('jobs', [])
running = [j['id'] for j in jobs if j.get('status') == 'RUNNING']
print(running[0] if running else '')
" 2>/dev/null || true)

  if [[ -n "$JOB_ID" ]]; then
    echo "  Cancelling Flink job $JOB_ID..."
    curl -s -X PATCH "http://localhost:8082/jobs/${JOB_ID}?mode=cancel" >/dev/null
    echo "  Flink job cancelled."
  else
    echo "  No running Flink jobs found."
  fi
else
  echo "  Flink JobManager not reachable — skipping job cancellation."
fi

# ── Stop Docker services ──────────────────────────────────────────────────────
echo "Stopping Docker services..."
docker-compose stop
echo "Done. Data volumes are preserved. Run 'bash scripts/teardown.sh' to remove them."
