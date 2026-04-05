#!/bin/sh
set -e

# Ensure data directory exists
mkdir -p /data

case "${1}" in
  server)
    echo "Starting 4DPocket server on port ${FDP_SERVER__PORT:-4040}..."
    exec uvicorn fourdpocket.main:app \
      --host "${FDP_SERVER__HOST:-0.0.0.0}" \
      --port "${FDP_SERVER__PORT:-4040}" \
      --workers "${FDP_SERVER__WORKERS:-1}"
    ;;
  worker)
    echo "Starting Huey background worker..."
    exec python -m huey.bin.huey_consumer \
      fourdpocket.workers.huey \
      --workers "${HUEY_WORKERS:-2}" \
      --worker-type thread
    ;;
  *)
    # Pass through any other command
    exec "$@"
    ;;
esac
