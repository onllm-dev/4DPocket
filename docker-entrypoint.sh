#!/bin/sh
set -e

# Ensure data directory exists
mkdir -p /data

case "${1}" in
  server)
    echo "Running database migrations..."
    uv run alembic upgrade head 2>&1 || { echo "migration failed"; exit 1; }
    echo "Starting 4DPocket server on port ${FDP_SERVER__PORT:-4040}..."
    exec uvicorn fourdpocket.main:app \
      --host "${FDP_SERVER__HOST:-0.0.0.0}" \
      --port "${FDP_SERVER__PORT:-4040}" \
      --workers "${FDP_SERVER__WORKERS:-1}"
    ;;
  worker)
    echo "Starting Huey background worker..."
    exec python -m fourdpocket.workers.huey_worker \
      --workers "${HUEY_WORKERS:-2}" \
      --worker-type thread
    ;;
  *)
    # Pass through any other command
    exec "$@"
    ;;
esac
