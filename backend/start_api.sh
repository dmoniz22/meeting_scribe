#!/bin/sh
# Start uvicorn with auto-restart on failure
while true; do
    echo "[$(date)] Starting uvicorn..."
    python3.12 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
    echo "[$(date)] Uvicorn exited with code $?, restarting in 2 seconds..."
    sleep 2
done
