#!/usr/bin/env bash
# Deploys the Flink job. If a job is already RUNNING, stops it with a savepoint
# and resumes the new job from that savepoint (stateful redeploy). Otherwise
# just submits it fresh.
#
# Usage: deploy_flink.sh [--fresh]
#   --fresh   Always do a stateless cancel + run, even if a job is running.
set -euo pipefail

FLINK_JM="${FLINK_JM:-flink-jobmanager}"
DOCKER_JAR_PATH="${DOCKER_JAR_PATH:-/opt/flink/crypto-analyzer-flink-1.0.0.jar}"
FRESH="${1:-}"

JOB_ID=$(docker exec "$FLINK_JM" flink list | grep 'RUNNING' | awk '{print $4}' || true)

if [[ -n "$JOB_ID" && "$FRESH" != "--fresh" ]]; then
  echo "Stopping running job $JOB_ID with a savepoint..."
  STOP_OUTPUT=$(docker exec "$FLINK_JM" flink stop --savepointPath file:///opt/flink/data/savepoints "$JOB_ID")
  echo "$STOP_OUTPUT"
  SAVEPOINT_PATH=$(echo "$STOP_OUTPUT" | grep -o 'file:[^[:space:]]*' | head -1)
  if [[ -z "$SAVEPOINT_PATH" ]]; then
    echo "ERROR: could not find savepoint path in flink stop output." >&2
    exit 1
  fi
  echo "Savepoint completed: $SAVEPOINT_PATH"
  echo "Resuming new job from savepoint..."
  docker exec "$FLINK_JM" flink run -d -s "$SAVEPOINT_PATH" "$DOCKER_JAR_PATH"
elif [[ -n "$JOB_ID" && "$FRESH" == "--fresh" ]]; then
  echo "Cancelling running job $JOB_ID (stateless restart)..."
  docker exec "$FLINK_JM" flink cancel "$JOB_ID"
  sleep 5
  echo "Submitting new job..."
  docker exec "$FLINK_JM" flink run -d "$DOCKER_JAR_PATH"
else
  echo "No running job found. Submitting new job..."
  docker exec "$FLINK_JM" flink run -d "$DOCKER_JAR_PATH"
fi
