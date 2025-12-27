# 📋 RemAssist — Unified Task Queue
*Supersedes previous `next-tasks.md` and `NEXT_TASKS.md`. All queues now live here.*

_Last updated: December 27, 2025 (Session 4)_

---

## 🔍 Current System Snapshot
- ✅ Working: SOA1 API, WebUI, Ollama, MemLayer, finance pipeline, E2E tests passing
- ✅ GPU Status: NemoAgent (9.4GB, GPU 0, 100%), phinance-json (4GB, GPU 1, 100%)
- ✅ Performance: Analysis pipeline ~9.4s total (transaction_extraction ~1.6s, anomaly_check ~7.8s)
- ✅ Consent endpoint registered at `/api/consent`
- ✅ Phinance model calls now logged to `logs/model_calls.jsonl`
- ✅ Smoke test (userflow_test.py) passing with consent flow
- ✅ Integration test (integration_test_12_files.py N=1) passing
- ✅ Monitoring Dashboard: `/monitoring` endpoint with system stats, services, GPUs, logs, jobs
- ✅ Dashboard JSON converter integrated - auto-generates `reports/{doc_id}/dashboard/` after analysis
- ✅ SSE event streaming: `/analysis-events/{doc_id}` for real-time pipeline progress
- ✅ Per-step timing: `/analysis-timing/{doc_id}` with detailed step durations
- ✅ NemoAgent anomaly detection integrated into analysis pipeline
- ✅ **Orchestrator prompt integration** - `agent.py` now loads from `orchestrator.md` file
- ✅ **Config cleanup** - Removed duplicate system prompts from `config.yaml` (162→57 lines)
- ✅ **Analysis History UI** - Enhanced `/api/analysis/jobs` with timing, steps, anomalies; expandable rows in monitoring dashboard

---

## 🚀 Immediate Priority Tasks

### 0. Smoke Test & Integration Validation ✅ COMPLETED
- [x] Run single-upload smoke test: upload PDF → POST /api/consent → POST /analyze-confirm → poll /analysis-status → verify DB records & files
- [x] Run integration_test_12_files.py with N=1
- [x] Verify `logs/model_calls.jsonl` contains NemoAgent and Phinance entries
- [ ] Scale integration_test_12_files.py to N=12 (optional stress test)

### 0.5. Monitoring Dashboard ✅ COMPLETED (Dec 26, 2025)
- [x] Add monitoring API endpoints to WebUI (GET /api/ollama/status, /api/gpu/status, /api/logs/list, /api/logs/{name}, /api/logs/{name}/tail, /api/analysis/jobs)
- [x] Create monitoring.html template with brutalist dark theme
- [x] System overview (CPU, Memory, Disk, Uptime)
- [x] Services status display
- [x] Ollama models and loaded models display
- [x] GPU status (2x RTX 5060 Ti) with memory/utilization bars
- [x] Log viewer with tabs (WebUI, Model Calls, SOA1 API)
- [x] Analysis jobs table
- [x] Auto-refresh (5s status, 3s logs)

### 1. Dashboard JSON Conversion Utility ✅ COMPLETED (Dec 26, 2025)
- [x] Implement `/home/ryzen/projects/home-ai/soa1/utils/dashboard_json.py` to convert phinance output to dashboard format
- [x] Integrate converter into analysis pipeline (auto-generates `dashboard/` subdirectory after analysis)
- [x] Validate output against dashboard requirements (categories aggregated, dates normalized, amounts negated)
- [x] Integrate NemoAgent for anomaly/edge case handling
- [x] Implement event streaming (SSE) for staged parsing events (STARTED, METADATA_READY, HEADERS_READY, TRANSACTIONS_READY, INSIGHTS_READY, ANOMALY_CHECK, COMPLETED)
- [x] Add per-step timing instrumentation to `_run_phinance_analysis` (metadata_extraction, headers_extraction, transaction_extraction, insights_generation, anomaly_check)
- [x] Implement SQLite persistence for transactions:
  - Added `doc_id` column to transactions table
  - Added `get_transactions_by_doc(doc_id)` to fetch transactions by document
  - Added `has_transactions_for_doc(doc_id)` to check if transactions exist (avoids re-parsing)
  - Added `save_transactions` alias for backward compatibility
- [x] Add a test that ensures parsed transactions are stored without requiring re-parse (`test_storage.py`)

### 1.1 Keep-Alive & Ollama API Standardization (NEW - High Priority)
- [ ] Audit & convert `home-ai/soa1/models.py` to use Ollama native `/api/chat` and ensure payload includes `"keep_alive": -1`. Add unit tests and a local smoke script.
- [ ] Audit & convert `home-ai/finance-agent/src/models.py` to use Ollama native `/api/chat` (or `/api/generate`) and include `"keep_alive": -1` for specialist model calls. Add unit tests.
- [ ] Add unit/integration test verifying that models are pinned (via `ollama ps` showing `UNTIL: Forever`) after load.
- [ ] Add a linter or CI check that flags calls to `/v1` endpoints where `keep_alive` is required.
- [ ] Update `RemAssist/OLLAMA_MIGRATION_GUIDE.md` with explicit guidance: "Prefer `/api/*` for pinning models; `/v1` may ignore `keep_alive`."
- [ ] Optional: Design a small, secure OpenAI-compat shim that forwards `/v1` → `/api` while preserving `keep_alive` (Phase-2).

### 2. Orchestrator System Prompt & Architecture ✅ COMPLETED (Dec 26, 2025 - Session 3)
- [x] Create `/home/ryzen/projects/home-ai/ARCHITECTURE.md` documenting SOA1 system architecture
- [x] Create `/home/ryzen/projects/home-ai/soa1/prompts/orchestrator.md` with **model-agnostic** system prompt (NO Modelfile - user will swap models)
- [x] Document routing logic and orchestrator rules
- [x] Add model verification endpoint `/api/models/verify` - returns orchestrator config, system prompt preview, loaded models
- [x] Add integration test `test_scripts/test_model_verification.py` to assert orchestrator is the only UI-facing model
- [x] **Integrate orchestrator.md into agent.py** - Modified `_load_system_prompt()` to load from file with fallback chain
- [x] **Clean up config.yaml** - Removed duplicate system prompts, simplified from 162 to 57 lines

### 3. SOA1 API Runtime Standardization ✅ COMPLETED (Dec 26, 2025)
- [x] Add systemd unit samples at `RemAssist/soa1-api.service` and `RemAssist/soa-webui.service`
- [x] Add start/stop scripts at `scripts/start-soa1.sh`, `scripts/stop-soa1.sh`
- [x] Add cleanup script at `scripts/cleanup-soa1.sh`
- [x] Add log rotation recommendations to `SERVICES_CONFIG.md`
- [x] Verify `/upload-pdf` and `/health` endpoints (verified via E2E test)

---

## 🔜 Potential Next Steps

### 4. Chat Context & Memory Improvements
- [ ] Implement chat history persistence (currently session-only)
- [ ] Add conversation memory to MemLayer for cross-session context
- [ ] Improve finance context injection in `/api/chat` (currently keyword-based)

### 5. UI Enhancements
- [ ] Add analysis results display in chat (cards, charts)
- [ ] Add spending dashboard page using dashboard JSON output
- [ ] Mobile responsive improvements

### 6. Multi-Document Analysis
- [ ] Support batch PDF uploads
- [ ] Cross-document spending comparison
- [ ] Trend analysis across time periods

---

## 🏁 Recently Completed (Dec 26, 2025 - Session 3)
- **Orchestrator Prompt Integration**: Modified `agent.py` to load system prompt from `orchestrator.md` file instead of inline config
- **Config Cleanup**: Removed 100+ line duplicate system prompts from `config.yaml` (162→57 lines)
- **Verified WebUI**: Chat consent flow, analysis display, and report generation all working
