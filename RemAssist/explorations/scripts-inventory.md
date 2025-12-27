# Scripts Directory Inventory

## Overview
The `scripts/` directory contains helper and operational scripts to manage SOA1 services, perform smoke checks, and assist development/testing workflows. These scripts are primarily intended for developer convenience and local testing rather than production deployment automation.

## Files

- `check_keepalive.py`
  - Purpose: Smoke test to verify `ModelClient.chat()` posts `keep_alive: -1` to the `/api/chat` endpoint.
  - Notes: Uses monkeypatch-like approach by temporarily overriding `requests.post` to capture calls.

- `cleanup-soa1.sh`
  - Purpose: Stop the SOA1 API, remove PID files, and perform cleanup of temporary files/logs.
  - Notes: Wraps `stop-soa1.sh` and performs additional file cleanup.

- `start-soa1.sh`
  - Purpose: Start the SOA1 API server via Uvicorn in the background and save PID.
  - Notes: Sets PYTHONPATH and environment variables for the project.

- `start-webui.sh`
  - Purpose: Start the WebUI Uvicorn server with `--reload` and appropriate environment variables.
  - Notes: Meant for development use.

- `stop-soa1.sh`
  - Purpose: Stop the SOA1 API server by PID or process lookup.
  - Notes: Cleans up PID files after stopping.

- `stop-webui.sh`
  - Purpose: Stop the WebUI server by PID or process lookup.
  - Notes: Cleans up PID files after stopping.

## Observations
- Scripts are consistent and small but not prepared for production use (no systemd-friendly behavior, health-checks, or robust logging).
- Process management logic is duplicated between start/stop scripts for SOA1 and WebUI, but separation is acceptable since they manage different services.

## Recommendations
- Consider moving production startup/stop logic to systemd service units (already present in `RemAssist/soa-webui.service` and `RemAssist/soa1-api.service`).
- Add simple health-checks to start scripts to confirm services are up (e.g., check `/health`).
- Document script usage in `README.md` or `CONTRIBUTING.md` for new contributors.
