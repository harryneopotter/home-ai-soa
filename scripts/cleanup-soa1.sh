#!/usr/bin/env bash
set -euo pipefail

# Stop any running SOA1 API processes and clean up temp files and pid
./scripts/stop-soa1.sh

# Remove leftover pid files
rm -f /tmp/soa1.pid

# Optionally clear log files
rm -f /tmp/soa1-api.log /tmp/soa1-api-debug.log || true

echo "Cleanup complete."