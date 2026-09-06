#!/bin/bash
set -Eeuo pipefail

# Keep the API private to this machine; Next.js is the only public listener.
/opt/venv/bin/python -m uvicorn app.server:app \
  --app-dir /app/backend --host 127.0.0.1 --port 8000 --no-access-log &
backend_pid=$!
node /app/frontend/server.js &
frontend_pid=$!

shutdown() {
  kill -TERM "$backend_pid" "$frontend_pid" 2>/dev/null || true
  wait "$backend_pid" "$frontend_pid" 2>/dev/null || true
}
trap 'shutdown; exit 0' SIGTERM SIGINT

# A failed child must not leave a half-working machine serving traffic.
status=0
wait -n "$backend_pid" "$frontend_pid" || status=$?
shutdown
if [ "$status" -eq 0 ]; then status=1; fi
exit "$status"
