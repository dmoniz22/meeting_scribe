#!/bin/sh
# Start uvicorn with auto-restart on failure
PORT=${API_PORT:-8000}
while true; do
    echo "[$(date)] Starting uvicorn on port $PORT..."
    python3.12 -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
    echo "[$(date)] Uvicorn exited with code $?, restarting in 2 seconds..."
    sleep 2
done
