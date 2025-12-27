# 📋 Services Configuration

## 🏁 Overview
This document provides a comprehensive reference for all SOA1 services, their configurations, ports, and purposes.

## 🌐 Service Inventory

### 1. SOA1 API Service
**Purpose**: Core API for SOA1 agent functionality
**Port**: 8001
**Model**: NemoAgent (main orchestrator) via Ollama
**Status**: ✅ ACTIVE — Running with NemoAgent orchestrator (system prompt enhancement pending)

**Key Endpoints**:
- `GET /health` — Health check
- `POST /api/chat` — Chat with NemoAgent
- `POST /upload-pdf` — Upload PDF, returns `job_id` and `doc_id` (requires consent before analysis)
- `POST /api/consent` — Record user consent for pending analysis job
- `POST /analyze-confirm` — Start analysis after consent is given (via WebUI on port 8080)

### 1.1 Finance Agent Service
**Purpose**: Specialized finance analysis using Phinance model
**Model**: phinance-json (custom Modelfile) on GPU 1
**Status**: ✅ WORKING — JSON output fixed with custom Modelfile (Dec 25, 2025)

### 2. WebUI Services
- Service Monitoring UI (secure_webui.py): Port 8080 — ACTIVE
- Agent Interaction UI (agent_webui.py): Port 8081 — ACTIVE

### 3. MemLayer Service
- Port 8000 — Not yet implemented

### 4. Nginx Reverse Proxy
- Port 80/443 — Not yet configured

## 🔐 Consent-Gated Analysis Flow

The finance analysis pipeline requires explicit user consent before invoking the Phinance specialist.

### Flow Steps:
1. **Upload PDF** → `POST /upload-pdf` on SOA1 API (port 8001)
   - Returns `job_id`, `doc_id`, and `consent_request` message
   - Document metadata persisted to SQLite
   - Analysis job created with `status=pending`

2. **Record Consent** → `POST /api/consent` on SOA1 API (port 8001)
   - Body: `{"job_id": "...", "confirm": true, "specialist": "phinance"}`
   - Updates job status to `confirmed`, sets `consent_given=1`

3. **Start Analysis** → `POST /analyze-confirm` on WebUI (port 8080)
   - Body: `{"doc_id": "..."}`
   - Checks DB for consent before proceeding
   - Calls Phinance specialist, persists transactions and analysis results

4. **Poll Status** → `GET /analysis-status/<doc_id>` on WebUI (port 8080)
   - Returns current analysis status and results when complete

### Service Restart Ordering:
1. Stop WebUI first (port 8080) to avoid stale connections
2. Stop SOA1 API (port 8001)
3. Start SOA1 API (wait for `/health` to return OK)
4. Start WebUI

### Model Call Logging:
All model calls (NemoAgent and Phinance) are logged to `logs/model_calls.jsonl` with:
- Timestamp, model name, endpoint, prompt hash
- Latency (ms), status (success/error)
- Redacted prompt preview (first 200 chars)

## 🖥️ Hardware & Model Configuration
- Platform: Intel X670 (migrated from AMD Threadripper)
- GPUs: 2x NVIDIA GeForce RTX 5060 Ti (16GB VRAM each, 32GB total)
- GPU 0: NemoAgent orchestrator
- GPU 1: phinance-json specialist
- Model keep_alive: Enabled for all loaded models
- Model config: SOA1 config uses NemoAgent (not qwen2.5)

## 🧠 Architecture
- NemoAgent is the main orchestrator for SOA1 (not just finance)
- Architecture:
  - NemoAgent (GPU 0) orchestrates
  - phinance-json (GPU 1) as finance specialist
  - Future: budgeting, knowledge, scheduler agents

## Server startup recommendation
- Use the Uvicorn CLI to run the SOA1 API: 
  - Development: `uvicorn home-ai.soa1.api:create_app --factory --reload --host 0.0.0.0 --port 8001`
  - Production: `uvicorn home-ai.soa1.api:create_app --factory --host 0.0.0.0 --port 8001 --log-level info`
- Sample systemd units: `RemAssist/soa1-api.service`, `RemAssist/soa-webui.service`
- Use `scripts/start-soa1.sh` and `scripts/stop-soa1.sh` to manage the API during development
- Log/location recommendations:
  - Redirect logs to `/var/log/soa1/soa1-api.log` when deploying with systemd
  - Use log rotation (logrotate) to prevent disk growth
- Memory/process safety:
  - Run with a process manager (systemd) to restart on failure
  - Add resource limits (MemoryLimit) in systemd if needed

## 📄 Log Rotation Configuration

### Recommended Logrotate Config
Create `/etc/logrotate.d/soa1`:

```
/var/log/soa1/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 ryzen ryzen
    sharedscripts
    postrotate
        systemctl reload soa1-api 2>/dev/null || true
        systemctl reload soa-webui 2>/dev/null || true
    endscript
}

/home/ryzen/projects/home-ai/logs/*.jsonl {
    weekly
    rotate 4
    compress
    delaycompress
    missingok
    notifempty
    create 0640 ryzen ryzen
    size 50M
}
```

### Log Files to Monitor
| File | Location | Rotation |
|------|----------|----------|
| WebUI logs | `/tmp/soa-webui.log` | Daily, 7 days |
| SOA1 API logs | `/tmp/soa1-api.log` | Daily, 7 days |
| Model calls | `home-ai/logs/model_calls.jsonl` | Weekly, 50MB max |
| Finance DB | `home-ai/finance-agent/data/finance.db` | SQLite (no rotation) |

### Disk Space Recommendations
- Model calls log: ~1-5MB per day with moderate usage
- WebUI/API logs: ~500KB-2MB per day
- Finance DB: Grows with transactions, ~1MB per 1000 transactions
- **Recommended minimum free space**: 10GB on `/home` partition

## 
 🗂️ Directory Structure
- See History.md and NEXT_TASKS.md for current state and file locations

## 🔄 Recent Changes & Fixes (December 25, 2025)
- GPU migration and Ollama fix (models now use GPU, VRAM allocation verified)
- Model keep_alive and config fixes
- Dashboard output requirements validated
- Conversion utility planned (separate file)
- NemoAgent architecture clarified
- Unnecessary models unloaded
- Logging verification task added

## 📝 Next Steps
- Implement dashboard JSON conversion utility
- Integrate NemoAgent for anomaly handling
- Finalize architecture documentation and system prompt
- Verify logging for all model actions, reasoning, tool calls (with timestamp)

---
