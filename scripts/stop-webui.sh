#!/usr/bin/env bash
set -euo pipefail

if [ -f /tmp/soa-webui.pid ]; then
  PID=$(cat /tmp/soa-webui.pid)
  if ps -p $PID > /dev/null 2>&1; then
    echo "Stopping WebUI (PID: $PID)"
    kill $PID || true
    rm -f /tmp/soa-webui.pid
  else
    echo "PID file found but process not running. Cleaning up."
    rm -f /tmp/soa-webui.pid
  fi
else
  PIDS=$(pgrep -f "uvicorn .*main:app" || true)
  if [ -n "$PIDS" ]; then
    echo "Stopping WebUI (PIDs: $PIDS)"
    kill $PIDS || true
  else
    echo "No running WebUI processes found."
  fi
fi