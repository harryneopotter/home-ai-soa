#!/usr/bin/env bash
set -euo pipefail

# Export FINANCE_DATA_DIR so WebUI and finance-agent share data
export FINANCE_DATA_DIR="/home/ryzen/projects/home-ai/finance-agent/data"
export PYTHONPATH="/home/ryzen/projects:${PYTHONPATH:-}"
cd /home/ryzen/projects/soa-webui
/usr/bin/env uvicorn main:app --host 0.0.0.0 --port 8080 --reload &
PID=$!
echo $PID > /tmp/soa-webui.pid
sleep 1
echo "Started WebUI (PID: $PID) with FINANCE_DATA_DIR=${FINANCE_DATA_DIR}"