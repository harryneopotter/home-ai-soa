# 📋 Services Configuration

_Last updated: January 9, 2026 (Session 42)_

## 🏁 Overview
This document provides a comprehensive reference for all SOA1 services, their configurations, ports, and purposes.

## 🌐 Service Inventory

### 1. SOA1 API Service
**Purpose**: Core API for SOA1 agent functionality
**Port**: 8001
**Model**: NemoAgent (main orchestrator) via Ollama
**Status**: ✅ ACTIVE — Running with NemoAgent orchestrator

**Key Endpoints**:
- `GET /health` — Health check
- `POST /api/chat` — Chat with NemoAgent
- `POST /upload-pdf` — Upload PDF, returns `job_id` and `doc_id` (requires consent before analysis)
- `POST /api/consent` — Record user consent for pending analysis job
- `POST /analyze-confirm` — Start analysis after consent is given (via WebUI on port 8080)

### 1.1 Finance Agent Service
**Purpose**: Specialized finance analysis using Phinance model
**Model**: phinance-json (custom Modelfile) on GPU 1
**Status**: ✅ WORKING — 100% GPU, validated output

### 2. WebUI Services
- Service Monitoring UI (secure_webui.py): Port 8080 — ACTIVE
- Agent Interaction UI (agent_webui.py): Port 8081 — ACTIVE
- **Consolidated Dashboard**: `/dashboard/consolidated` — Full finance overview with charts

### 3. MemLayer Service
- Port 8000 — Not yet implemented

### 4. Nginx Reverse Proxy
- Port 80/443 — Not yet configured

## 🖥️ Hardware & Model Configuration
- **Platform**: Intel X670 (migrated from AMD Threadripper)
- **GPUs**: 2x NVIDIA GeForce RTX 5060 Ti (16GB VRAM each, 32GB total)
- **GPU 0**: NemoAgent orchestrator (13GB, 100% GPU)
- **GPU 1**: phinance-json specialist (4GB, 100% GPU)
- **Model Settings**:
  - `num_gpu: 99` — Force full GPU offload
  - `num_ctx: 32768` — NemoAgent context window
  - `keep_alive: -1` — Models stay loaded indefinitely

### ⚠️ Phinance Context Window — DO NOT CHANGE
- **`num_ctx`: 4096** (set in `home-ai/soa1/models.py` line ~549)
- Prompt sends **aggregated summaries only**, not raw transactions
- Typical usage: ~1000 tokens (system ~133 + user ~550 + response ~300)
- Analyzed Jan 6, 2026: 4K provides 3K+ headroom, 32K was massive overkill
- **DO NOT increase** — wastes VRAM, no benefit

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

## 🛡️ LLM Response Validation

**New in Dec 31, 2025**: All phinance LLM responses are validated using Pydantic schemas.

### Validation Features:
- **Transaction validation**: date format, amount bounds (-1M to 1M), merchant presence
- **Analysis validation**: totals, categories, merchants, insights structure
- **JSON extraction**: handles markdown code blocks, embedded JSON
- **Error feedback**: `LLMValidationError` includes `feedback_prompt` for retry loops

### Usage:
```python
from utils.llm_validation import validate_transactions, validate_analysis, LLMValidationError

try:
    transactions, warnings = validate_transactions(raw_llm_response)
    analysis, warnings = validate_analysis(raw_llm_response)
except LLMValidationError as e:
    print(e.errors)
    print(e.feedback_prompt)  # Use for retry
```

### Retry Infrastructure (Base Setup):
- `RetryConfig`: max_attempts, include_previous_response, include_error_feedback
- `RetryContext`: tracks attempt number, previous errors
- `build_retry_prompt()`: constructs retry prompt with validation feedback
- **Status**: Ready but not wired into call flow yet

## 📊 Dashboard Endpoints

### Consolidated Dashboard
- **URL**: `http://localhost:8080/dashboard/consolidated`
- **API**: `GET /api/reports/consolidated`
- **Features**:
  - Overview cards (total spending, transactions, documents)
  - Spending by category chart (doughnut)
  - Monthly trends chart (bar)
  - Top 15 merchants
  - All transactions table with search/filter/sort
  - AI insights and recommendations

### Monitoring Dashboard
- **URL**: `http://localhost:8080/monitoring`
- **Features**:
  - System overview (CPU, Memory, Disk, Uptime)
  - Services status
  - Ollama models and VRAM usage
  - GPU status (2x RTX 5060 Ti)
  - Log viewer
  - Analysis jobs table

## Model Call Logging
All model calls (NemoAgent and Phinance) are logged to `logs/model_calls.jsonl` with:
- Timestamp, model name, endpoint, prompt hash
- Latency (ms), status (success/error)
- Redacted prompt preview (first 200 chars)

## Server Startup Recommendation
- Use the Uvicorn CLI to run the SOA1 API: 
  - Development: `uvicorn home-ai.soa1.api:create_app --factory --reload --host 0.0.0.0 --port 8001`
  - Production: `uvicorn home-ai.soa1.api:create_app --factory --host 0.0.0.0 --port 8001 --log-level info`
- Sample systemd units: `RemAssist/soa1-api.service`, `RemAssist/soa-webui.service`
- Use `scripts/start-soa1.sh` and `scripts/stop-soa1.sh` to manage the API during development

### Service Restart Ordering:
1. Stop WebUI first (port 8080) to avoid stale connections
2. Stop SOA1 API (port 8001)
3. Start SOA1 API (wait for `/health` to return OK)
4. Start WebUI

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

## 🗂️ Key Files Modified (Jan 9, 2026)

| File | Changes |
|------|---------|
| `home-ai/soa1/memory/__init__.py` | **NEW** - Package exports |
| `home-ai/soa1/memory/client.py` | **MOVED** - Was `memory.py` |
| `home-ai/soa1/memory/memory_manager.py` | **NEW** - Propose/commit pattern |
| `home-ai/soa1/memory/session_memory.py` | **NEW** - Ephemeral session state |
| `home-ai/soa1/tests/test_memory.py` | **NEW** - 11 unit tests |
| `home-ai/soa1/agent.py` | Integrated MemoryManager + session helpers |
| `home-ai/soa1/control_header.py` | **NEW** - CONTROL header system (M0) |
| `home-ai/soa1/orchestrator.py` | Added Capability enum, ControlHeaderEnforcer |

## 🗂️ Key Files Modified (Dec 31, 2025)

| File | Changes |
|------|---------|
| `home-ai/soa1/utils/llm_validation.py` | **NEW** - Pydantic validation schemas |
| `home-ai/soa1/models.py` | Added validation integration |
| `home-ai/soa1/utils/__init__.py` | Exports validation functions |
| `home-ai/finance-agent/src/models.py` | GPU fix: num_gpu: 99, num_ctx |
| `soa-webui/templates/consolidated_dashboard.html` | **NEW** - Full dashboard |
| `soa-webui/reports.py` | Added consolidated API endpoint |
| `soa-webui/main.py` | Added dashboard route |

---
