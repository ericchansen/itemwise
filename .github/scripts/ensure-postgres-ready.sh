#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${AZURE_RESOURCE_GROUP:-}" ]]; then
  echo "AZURE_RESOURCE_GROUP is required"
  exit 1
fi

if [[ -z "${PG_SERVER:-}" ]]; then
  echo "PG_SERVER is required"
  exit 1
fi

MAX_POLLS="${MAX_POLLS:-30}"
POLL_INTERVAL_SECONDS="${POLL_INTERVAL_SECONDS:-10}"

state="$(az postgres flexible-server show \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --name "$PG_SERVER" \
  --query "state" -o tsv)"

if [[ "$state" == "Stopped" ]]; then
  echo "PostgreSQL server $PG_SERVER is stopped. Starting..."
  az postgres flexible-server start \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --name "$PG_SERVER" \
    --only-show-errors
fi

for _ in $(seq 1 "$MAX_POLLS"); do
  state="$(az postgres flexible-server show \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --name "$PG_SERVER" \
    --query "state" -o tsv)"
  if [[ "$state" == "Ready" ]]; then
    echo "PostgreSQL server $PG_SERVER is Ready"
    exit 0
  fi
  sleep "$POLL_INTERVAL_SECONDS"
done

echo "PostgreSQL server $PG_SERVER did not reach Ready state"
exit 1
