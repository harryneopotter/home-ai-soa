#!/usr/bin/env bash
set -euo pipefail

if [ -f /tmp/soa1.pid ]; then
  PID=$(cat /tmp/soa1.pid)
  if ps -p $PID > /dev/null 2>&1; then
    echo "Stopping SOA1 API (PID: $PID)"
    kill $PID || true
    rm -f /tmp/soa1.pid
  else
    echo "PID file found but process not running. Cleaning up."
    rm -f /tmp/soa1.pid
  fi
else
  # Attempt to find any running processes as a fallback
  PIDS=$(pgrep -f "uvicorn .*home-ai.soa1.api:create_app" || true)
  if [ -n "$PIDS" ]; then
    echo "Stopping SOA1 API (PIDs: $PIDS)"
    kill $PIDS || true
  else
    echo "No running SOA1 API processes found."
  fi
fi