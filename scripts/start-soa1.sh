#!/usr/bin/env bash
set -euo pipefail

# Start SOA1 API using uvicorn (recommended)
cd /home/ryzen/projects/home-ai/soa1
# Run within the module path to avoid ambiguous module imports
/usr/bin/env uvicorn api:create_app --workers 1 --host 0.0.0.0 --port 8001 --factory --log-level info &
PID=$!
echo $PID > /tmp/soa1.pid
sleep 1
echo "Started SOA1 API (PID: $PID)"