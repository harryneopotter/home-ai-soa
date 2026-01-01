# 📚 RemAssist - Task History

## 📅 Session History

### December 31, 2025 - Performance Optimizations (Session 12)

#### ⚡ Parallel Batch PDF Processing
- **New Endpoint:** `POST /analyze-batch`
  - Accepts `{"doc_ids": [...], "max_concurrent": 2}`
  - Uses `ThreadPoolExecutor` with max 2 workers (GPU contention limit)
  - Checks cache before processing each document
  - Returns batch status with queued/cached/error counts
- **File Modified:** `soa-webui/main.py`
  - Added `_pdf_executor` ThreadPoolExecutor
  - Added `BatchAnalyzeRequest` model
  - Added `/analyze-batch` endpoint

#### 💾 Transaction Caching
- **File Modified:** `soa-webui/main.py` - `_run_phinance_analysis()`
  - Now checks `has_transactions_for_doc()` before parsing
  - If cached, marks job as completed with `from_cache: True`
  - Skips expensive LLM calls for already-processed documents

#### 📄 Paginated Transactions API
- **New Endpoint:** `GET /api/transactions`
  - Query params: `page`, `page_size`, `doc_id`, `category`, `merchant`, `date_from`, `date_to`
  - Returns paginated transactions with metadata
  - Supports filtering and server-side pagination

#### 🎨 Dashboard Lazy Loading
- **File Modified:** `soa-webui/templates/consolidated_dashboard.html`
  - Added pagination state management (`paginationState`)
  - Added pagination controls (Prev/Next, page size selector)
  - `renderTransactionTable()` now paginates instead of slicing to 500
  - `filterTransactions()` resets to page 1 on filter change
  - `changePage()` and `changePageSize()` functions for navigation

---

### December 31, 2025 - Security Hardening & UI Enhancements (Session 11)

#### 🔧 Retry Logic Wired into call_phinance()
- **File Modified:** `home-ai/soa1/models.py`
  - Added `retry_config: Optional[RetryConfig] = None` parameter to `call_phinance()`
  - Implemented retry loop with validation feedback when `retry_config` is provided
  - On validation failure, builds retry prompt with error feedback using `build_retry_prompt()`
  - Logs retry attempts with warning level
  - `call_phinance_validated()` now uses retry by default (max_attempts=3)
- **File Modified:** `home-ai/soa1/utils/__init__.py`
  - Added exports: `RetryConfig`, `RetryContext`, `build_retry_prompt`

#### 🛡️ Security Fixes - XSS & Path Traversal
- **XSS Fixes in Templates:**
  - `soa-webui/templates/consolidated_dashboard.html`: Added `escapeHtml()` function for safe HTML rendering, applied to merchant names, categories, dates, insights, recommendations, doc_ids
  - `soa-webui/templates/analysis_dashboard.html`: Same `escapeHtml()` function applied to transactions table and insights
- **Path Traversal Fixes:**
  - `home-ai/soa1/api.py`: PDF upload filename sanitization with `re.sub(r'[^\w\-_\.]', '_', os.path.basename(filename))`
  - `home-ai/soa1/api.py`: Audio endpoint with `os.path.basename()` check and `".."` rejection

#### 🎨 UI Enhancements - Date Range Picker & CSV Export
- **File Modified:** `soa-webui/templates/consolidated_dashboard.html`
  - Added CSS for date inputs and export button (dark theme styling)
  - Added date range picker inputs (`dateFrom`, `dateTo`) to filter bar
  - Added "Export CSV" button with green accent styling
  - Implemented `parseDate()` to handle MM/DD/YYYY and YYYY-MM-DD formats
  - Updated `filterTransactions()` to filter by date range
  - Added `currentFilteredTransactions` to track filtered results
  - Implemented `exportToCSV()`: generates CSV with proper escaping, downloads as `transactions_YYYY-MM-DD.csv`

#### 📝 Git Commit
- Commit `335486a`: "feat: security hardening + retry wiring + UI enhancements"
- Pushed to `origin/main`

---

### December 31, 2025 - LLM Response Validation & Consolidated Dashboard (Session 10)

#### 🛡️ LLM Response Validation System
- **Created `home-ai/soa1/utils/llm_validation.py`**: Full Pydantic validation for phinance LLM outputs
  - `Transaction` model: validates date formats, amount bounds (-1M to 1M), merchant presence
  - `TransactionsResponse`: handles bare list or wrapped `{"transactions": [...]}` format
  - `AnalysisResponse`: validates totals, categories, merchants, insights
  - `LLMValidationError`: rich exception with `feedback_prompt` for retry loops
  - JSON extraction from markdown code blocks, embedded JSON in prose
- **Retry Infrastructure (Base Setup)**:
  - `RetryConfig`: max_attempts, include_previous_response, include_error_feedback
  - `RetryContext`: tracks attempt number, previous errors
  - `build_retry_prompt()`: constructs retry prompt with validation feedback
  - NOT wired yet - ready for integration when needed
- **Updated `home-ai/soa1/models.py`**:
  - Added `validate` parameter to `call_phinance()`
  - Added `call_phinance_validated()` returning typed Pydantic objects
  - Added `validate_phinance_response()` for standalone validation
- **Updated `home-ai/soa1/utils/__init__.py`**: exports validation functions

#### ✅ Validation Tests Passing
- Real phinance output: 25 transactions validated ✅
- Empty response detection ✅
- JSON in markdown code blocks extraction ✅
- Invalid date format rejection ✅
- Bare list handling (no wrapper) ✅
- Amount bounds checking ✅

---

### December 31, 2025 - GPU Eviction Fix & Consolidated Dashboard (Session 9)

#### 🐛 GPU Eviction Bug Fixed
- **Problem**: NemoAgent kept falling back to 96% CPU / 4% GPU during analysis
- **Root Cause**: `num_gpu: 1` hardcoded in `home-ai/finance-agent/src/models.py` and missing `num_ctx`
- **Fix Applied**:
  - `home-ai/finance-agent/src/models.py`: Changed `num_gpu: 1` → `99`, added `num_ctx: 32768` for NemoAgent, `4096` for phinance
  - `home-ai/soa1/models.py`: Added options block with `num_gpu: 99, num_ctx: 32768`, fixed Ollama response parsing

#### 📊 Consolidated Finance Dashboard
- **New Files**:
  - `soa-webui/templates/consolidated_dashboard.html`: Full dashboard with Chart.js visualizations
  - `soa-webui/templates/analysis_dashboard.html`: Individual analysis view
- **New API Endpoints**:
  - `GET /api/reports/consolidated`: Aggregates all reports into single JSON
  - `GET /dashboard/consolidated`: Serves consolidated dashboard template
- **Dashboard Features**:
  - Overview cards (total spending, transaction count, document count)
  - Spending by category doughnut chart
  - Top 15 merchants list
  - Monthly spending trends bar chart
  - All transactions table with search/filter/sort
  - AI-generated insights and recommendations
  - Document summaries for each analyzed PDF

#### 📊 Batch Test Results
- **8 PDFs processed**: 437 transactions, 84.2 seconds total (~10.5s avg per PDF)
- **Both models at 100% GPU** throughout entire batch
- **Reports generated** in `/home/ryzen/projects/home-ai/finance-agent/data/reports/`

#### 🧹 Cleanup
- Removed duplicate `templates/` directory (moved to `soa-webui/templates/`)
- Removed stale session files (`session-ses_*.md`, `fail.md`)
- Added `test_logs/` to `.gitignore`

#### 📝 Git Commit
- Commit `b3d8252`: "feat: consolidated dashboard + GPU eviction fix + cleanup"
- Pushed to `origin/main`

---

### December 28, 2025 - Gemini CLI Context Setup & Documentation (Session 7)

#### 📝 Documentation Rewrite
- **GEMINI.md**: Completely rewrote `GEMINI.md` to reflect the current project structure (`home-ai`, `soa-webui`, `RemAssist`), service mappings (ports 8000, 8001, 8080, etc.), and mandatory context tracking requirements.
- **Rules**: Re-integrated strict execution rules and added mandatory updates for `History.md`, `NEXT_TASKS.md`, and `errors.md` after every task.

#### 🛠️ Actions Taken
- Analyzed codebase structure using file system tools.
- Verified service configurations in `config.yaml` files across the monorepo.
- Updated `GEMINI.md` with detailed project context to improve agent grounding and established `NEXT_TASKS.md` as the primary task queue.

### December 28, 2025 - WebUI Overhaul & Demo Prep (Session 8)

#### 🎨 UI/UX Redesign
- **Redesigned Main WebUI**: Replaced the generic admin-style `index.html` with a **Brutalist Dark Theme** chat interface, matching the `monitoring.html` aesthetic.
- **Integrated Chat & Upload**: Added a unified interface for file uploads and chatting directly on the dashboard.
- **Added Proxy Endpoint**: Implemented `/api/proxy/upload` in `soa-webui/main.py` to securely forward file uploads to the backend API (`soa1/api.py`), resolving CORS/port isolation issues.

#### 🔧 Functional Verification
- Verified `soa-webui/main.py` routing and proxy logic.
- Ensured `index.html` serves as the primary entry point with full functionality.
- Confirmed "Local Appliance" context in `Critical-review.md`.

### December 28, 2025 - WebUI Finance Pipeline Fixes (Session 6)

#### 🐛 Issues Fixed

**1. UNIQUE Constraint Violation in save_analysis_job**
- **Error:** `UNIQUE constraint failed: analysis_jobs.doc_id`
- **Root Cause:** SOA1 API and WebUI created jobs with different `job_id`s for the same `doc_id`. The `save_analysis_job()` function checked for existing records by `job_id` instead of `doc_id` (the actual UNIQUE constraint), causing INSERT failures.
- **Fix:** Modified `save_analysis_job()` in `home-ai/finance-agent/src/storage.py` to check by `doc_id` first, and UPDATE using `WHERE doc_id=?`.

**2. Wrong Parser Import - parse_apple_card_statement Not Found**
- **Error:** `cannot import name 'parse_apple_card_statement' from 'home_ai.finance_agent.src.parser'`
- **Root Cause:** WebUI's `_run_phinance_analysis()` assumed a simple function `parse_apple_card_statement(path)` but the actual parser is class-based (`FinanceStatementParser`) with async methods requiring a specific call chain.
- **Fix:** Rewrote `_run_phinance_analysis()` in `soa-webui/main.py` to use `FinanceStatementParser` class with `asyncio.run()` wrapper for the async method chain: `get_identity_context()` → `get_structural_summary()` → `extract_transactions()`.

**3. Ollama Response Format Mismatch**
- **Error:** `RuntimeError: Unexpected Nemotron response: {'model': 'NemoAgent', 'message': {'content': '...'}, ...}`
- **Root Cause:** `call_nemotron()` and `call_phinance()` in `models.py` tried to parse OpenAI format (`data["choices"][0]["message"]["content"]`) but Ollama's `/api/chat` returns `data["message"]["content"]`.
- **Fix:** Updated both functions in `home-ai/finance-agent/src/models.py` to check for Ollama format first, with fallback to OpenAI format.

#### 📝 Files Modified
- `home-ai/finance-agent/src/storage.py` - Fixed `save_analysis_job()` to check by `doc_id`
- `home-ai/finance-agent/src/models.py` - Fixed response parsing for Ollama format
- `soa-webui/main.py` - Rewrote `_run_phinance_analysis()` to use `FinanceStatementParser` class
- `RemAssist/errors.md` - Documented all 3 errors with root causes and fixes

#### ✅ Verified
- Userflow test (`test_scripts/userflow_test.py`) passes end-to-end
- Full pipeline works: Upload → Stage A/B → Consent → Analyze → Reports
- 83 transactions extracted from Apple Card statement
- Phinance insights generated with category breakdown ($8,321.71 total)
- Reports created at `home-ai/finance-agent/data/reports/{doc_id}/`
- Chat follow-up works after analysis completion

#### 📊 Test Results
```
doc_id: finance-20251228-001842-5417ca
transactions: 83
total_spent: $8,321.71
top_category: travel ($3,109.79)
phinance_insights: ✅ Generated
reports: transactions.json (21KB), analysis.json (2KB)
```

---

### December 27, 2025 - Progressive Engagement Implementation (Session 5)

#### 🛠️ Implementation
- **Updated `orchestrator.md` system prompt**: Added Progressive Engagement Protocol (Phases 1-4), document context format `[DOCUMENT CONTEXT]...[/DOCUMENT CONTEXT]`, and specific vs generic response examples
- **Modified `agent.py`**: Added `_format_document_context()` method and extended `ask()` signature to accept `document_context: Optional[Dict] = None` parameter
- **Updated `api.py`**: Added session-based document tracking (`_pending_documents`), helper functions `_get_session_id()`, `_get_pending_document_context()`, `_add_pending_document()`, and wired document context into `/api/chat` and `/ask` endpoints

#### 📝 Files Modified
- `home-ai/soa1/prompts/orchestrator.md` - Added progressive engagement behavior and document context format
- `home-ai/soa1/agent.py` - Added document context formatting and injection into model prompts
- `home-ai/soa1/api.py` - Added session-based document tracking and context injection to chat endpoints

#### ✅ Verified
- Python syntax validation passes on both `agent.py` and `api.py`
- Document context flows: upload → metadata stored → chat request → context injected → orchestrator sees document details

#### 🎯 Key Design Decision
- **Session-based document tracking**: Documents are tracked per session (via `X-Session-ID` header or client IP fallback)
- **Immediate acknowledgment with specifics**: When user uploads a PDF and chats, orchestrator now receives document metadata (filename, pages, size, detected type) and can respond specifically instead of generically
- **Consent-gated analysis**: Orchestrator can acknowledge and describe document but must still request consent before invoking phinance specialist

---

### December 27, 2025 - Analysis History UI Enhancement (Session 4)

#### 🛠️ Implementation
- **Fixed WebUI startup**: Created missing `__init__.py` files in `home-ai/` and `home-ai/soa1/` directories
- **Verified enhanced `/api/analysis/jobs` endpoint**: Now returns `duration_s`, `step_timings`, `pipeline_ms`, `anomaly_count`, `anomalies`
- **Tested monitoring dashboard**: Analysis History section displays properly with expandable rows

#### 📝 Files Created
- `home-ai/__init__.py` - Created empty init file for Python package
- `home-ai/soa1/__init__.py` - Created empty init file for Python package

#### ✅ Verified
- WebUI starts successfully with `PYTHONPATH=/home/ryzen/projects`
- `/api/analysis/jobs` returns enhanced data:
  - `duration_s`: 9.35 seconds
  - `step_timings`: { transaction_extraction: 1580.6ms, anomaly_check: 7769.1ms }
  - `pipeline_ms`: 9349.7ms total
  - `anomaly_count`: 1, with full anomaly details
- Monitoring page loads (620 lines) with Analysis History section
- Smoke test (`userflow_test.py`) passes: 83 transactions, 9.35s total

#### 🔧 Additional Verification (Dec 27, 2025)
- Confirmed OpenAI-style endpoints replaced with Ollama native endpoints where model persistence is required:
  - `home-ai/soa1/model.py` — uses `/api/chat` and sets `keep_alive: -1`.
  - `soa-webui/model_manager.py` — uses `/api/generate` and sets `keep_alive: -1`.
- Noted modules still using OpenAI-compatible `/v1` endpoints (e.g., `home-ai/finance-agent/src/models.py`, `home-ai/soa1/models.py`) which may include `keep_alive` but the compatibility layer can ignore it; recommended auditing and standardizing to native `/api/*` or adding a small OpenAI-compat shim that preserves `keep_alive`.
- Updated `RemAssist/OLLAMA_MIGRATION_GUIDE.md` with guidance on API choice & keep_alive semantics, and added unit test tasks to `RemAssist/NEXT_TASKS.md` to assert `keep_alive` is sent and models are pinned.

#### 📊 Performance Update
- Analysis pipeline: ~9.4s total (improved from ~13s)
- Transaction extraction: ~1.6s
- Anomaly check: ~7.8s (NemoAgent bottleneck)

---

### December 26, 2025 - Orchestrator Prompt Integration (Session 3)

#### 🛠️ Implementation
- **Integrated `orchestrator.md` into agent.py**: Modified `SOA1Agent.__init__` to load system prompt from file instead of inline config
- **Created `_load_system_prompt()` function**: Fallback chain: `orchestrator.prompt_file` → `prompts/orchestrator.md` → `orchestrator.system_prompt` → `agent.system_prompt`
- **Cleaned up `config.yaml`**: Removed 100+ line duplicate `orchestrator.system_prompt` and legacy `agent.system_prompt` sections
- **Verified WebUI chat behavior**: Consent flow, analysis display, and finance context injection all working

#### 📝 Files Modified
- `home-ai/soa1/agent.py` - Added `_load_system_prompt()`, now loads from `orchestrator.md`
- `home-ai/soa1/config.yaml` - Removed duplicate system prompts, simplified orchestrator section (57 lines vs 162)

#### ✅ Verified
- Agent initialization test passes, loads 4769 char prompt from `orchestrator.md`
- Prompt contains "Daily Home Assistant" identity and consent rules
- 21 analysis reports exist with transactions.json and analysis.json files
- Latest report shows 66 transactions, $6400 total spent, proper category breakdown

#### 🎯 Key Design Decision Enforced
- **NO Modelfile for orchestrator** - Prompt loaded at runtime for model swapping
- **Model-agnostic prompt** at `home-ai/soa1/prompts/orchestrator.md`
- Config only specifies model name, temperature, max_tokens

---

### December 26, 2025 - Model Verification Endpoint & Production Readiness

#### 🛠️ New Features
- **`/api/models/verify` endpoint**: Returns orchestrator config, system prompt preview, loaded models with roles
- **Integration test**: `test_scripts/test_model_verification.py` verifies orchestrator is UI-facing
- **Systemd units**: Updated `soa1-api.service`, added `soa-webui.service` with security hardening
- **Log rotation**: Added logrotate config recommendations to SERVICES_CONFIG.md

#### 📝 Files Created/Modified
- `soa-webui/main.py` - Added `/api/models/verify` endpoint
- `test_scripts/test_model_verification.py` - New integration test
- `RemAssist/soa1-api.service` - Updated with security hardening
- `RemAssist/soa-webui.service` - New systemd unit
- `RemAssist/SERVICES_CONFIG.md` - Added log rotation section

#### ✅ Verified
- All syntax checks pass
- Endpoint returns model configuration correctly

---

### December 26, 2025 - SQLite Persistence for Transactions

#### 🛠️ Implementation
- **Added `doc_id` column** to transactions table for document-level tracking
- **Added `get_transactions_by_doc(doc_id)`** to fetch all transactions for a specific document
- **Added `has_transactions_for_doc(doc_id)`** to check if transactions already exist (avoids re-parsing)
- **Added `save_transactions` alias** for backward compatibility with existing main.py code
- **Made DB_PATH configurable** via `FINANCE_DB_PATH` environment variable

#### 📝 Files Modified
- `home-ai/finance-agent/src/storage.py` - Schema update + new functions
- `home-ai/finance-agent/test_storage.py` - New test file for persistence

#### ✅ Verified
- Test passes: save 3 transactions → verify they exist → load from cache
- Re-parse skip logic works: `has_transactions_for_doc()` returns True after save

---

### December 26, 2025 - Design Decision: Model-Agnostic Orchestrator Prompt

#### 🎯 Decision
**NO Modelfile for orchestrator (NemoAgent or any future model)**. Instead, use a **model-agnostic system prompt** stored as plain markdown.

#### 📝 Rationale
- User will experiment with different models as orchestrator
- Modelfile ties system prompt to a specific model
- Model-agnostic prompt allows hot-swapping models without rebuilding

#### 📂 Implementation
- System prompt will live at: `/home/ryzen/projects/home-ai/soa1/prompts/orchestrator.md`
- Prompt is loaded at runtime and injected via API (not baked into model)
- phinance-json retains its Modelfile (it's a fixed specialist, not user-swappable)

#### ⚠️ Agent Note
When working on orchestrator/NemoAgent tasks:
- **DO NOT** create `.modelfile` files for the orchestrator
- **DO** use plain markdown prompts that work with any model
- **DO** pass system prompt via Ollama API's `system` parameter

---

### December 26, 2025 - GPU Performance Fix (Session 2)

#### 🐛 Bug Fixed
- **Persistent 90%/10% CPU/GPU Split for phinance-json**: Model kept loading with only 1/33 layers on GPU despite `num_gpu: 99` being set in code.

#### 🔍 Root Cause Analysis
1. Ollama logs showed: `load_tensors: offloaded 1/33 layers to GPU`
2. Model call logs showed `num_gpu: 1` despite source code having `num_gpu: 99`
3. Cause: Python bytecode cache (`.pyc`) was stale + WebUI process hadn't been restarted after code changes

#### 🛠️ Fix Applied
1. Cleared all `__pycache__` directories in home-ai
2. Restarted WebUI service
3. Manually reloaded phinance-json with `num_gpu: 99` via API

#### 📊 Performance Results
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| `transaction_extraction` | ~23s | ~3.6s | **6.4x faster** |
| Total pipeline | ~35s | ~13.4s | **2.6x faster** |
| phinance GPU allocation | 90% CPU / 10% GPU | 100% GPU | ✅ |
| VRAM usage (GPU 1) | 889 MiB | 4277 MiB | Correct |

#### ✅ Verified
- Both models stable at 100% GPU after E2E test
- Model call logs now show `num_gpu: 99` for phinance
- Analysis timing confirms ~3.6s for transaction_extraction

---

### December 26, 2025 - SSE Events, Timing & NemoAgent Anomaly Detection

#### 🛠️ New Features
- **Per-Step Timing Instrumentation**: Added detailed timing for each analysis step
  - `metadata_extraction`: PDF metadata and identity context
  - `headers_extraction`: Structural summary via NemoAgent
  - `transaction_extraction`: Regex/fallback extraction (~20s)
  - `insights_generation`: Phinance insights
  - `anomaly_check`: NemoAgent data validation (~8s)
  - Total pipeline time tracked: ~28s for 83 transactions

- **SSE Event Streaming**: Real-time analysis progress via `/analysis-events/{doc_id}`
  - Events: STARTED, METADATA_READY, HEADERS_READY, TRANSACTIONS_READY, INSIGHTS_READY, ANOMALY_CHECK, COMPLETED, FAILED
  - Keepalive every 30s, auto-disconnect on completion
  - Past events replayed on connect for late subscribers

- **NemoAgent Anomaly Detection**: Post-extraction data validation
  - Detects large transactions (>$500)
  - Flags duplicate transactions
  - Identifies category spending anomalies
  - Returns structured JSON with type, description, severity

- **New API Endpoints**:
  - `GET /analysis-events/{doc_id}` - SSE stream of analysis events
  - `GET /analysis-timing/{doc_id}` - Detailed timing breakdown + anomalies

#### 📝 Files Modified
- `soa-webui/main.py`:
  - Added `AnalysisEvent` enum, `StepTiming` dataclass
  - Extended `AnalysisJob` with timings, events, anomalies
  - Added `broadcast_event()` and `_check_anomalies_with_nemo()`
  - Rewrote `_run_phinance_analysis()` with full instrumentation
  - Added SSE endpoint `/analysis-events/{doc_id}`
  - Added timing endpoint `/analysis-timing/{doc_id}`

#### ✅ Verified
- E2E test passes with all new features
- Timing shows 4 steps totaling ~28s
- 6 events captured per analysis run
- NemoAgent found 3 anomalies in test data (travel 40%, dining/transport >$500)

---

### December 26, 2025 - Dashboard JSON Converter Integration

#### 🛠️ New Features
- **Implemented Dashboard JSON Converter**: `/home/ryzen/projects/home-ai/soa1/utils/dashboard_json.py`
  - Converts phinance output (`transactions.json`, `analysis.json`) to dashboard-compatible format
  - Date normalization: `MM/DD/YYYY` → `YYYY-MM-DD`
  - Category aggregation: merges `gas` + `transportation` → `Transportation`
  - Amount conversion: positive amounts → negative (expenses)
  - Transaction ID generation with hash suffix
  - Top merchants truncation (40 char limit)

- **Integrated Converter into Analysis Pipeline**: 
  - Auto-generates `reports/{doc_id}/dashboard/` directory after phinance analysis
  - Contains `transactions.json` and `analysis.json` in dashboard format

#### 📝 Files Modified
- `home-ai/soa1/utils/dashboard_json.py` - Fixed category aggregation bug
- `soa-webui/main.py` - Added dashboard JSON generation after `_save_analysis_reports()`
- `scripts/start-webui.sh` - Added PYTHONPATH export for home_ai imports

#### ✅ Verified
- E2E test passes: upload → consent → analyze → dashboard JSON generated
- Dashboard output verified: 83 transactions, categories properly aggregated
- Transportation now correctly shows 534.85 (was split into gas + transportation)

---

### December 26, 2025 - Monitoring Dashboard Implementation

#### 🛠️ New Features
- **Created Monitoring Dashboard**: Full system monitoring at `/monitoring` endpoint
- **Added 7 new API endpoints to WebUI**:
  - `GET /api/ollama/status` - Ollama models, loaded models, VRAM usage
  - `GET /api/gpu/status` - NVIDIA GPU status via nvidia-smi
  - `GET /api/logs/list` - List available log files
  - `GET /api/logs/{log_name}` - Get log content with pagination
  - `GET /api/logs/{log_name}/tail` - Tail log files
  - `GET /api/analysis/jobs` - Analysis jobs status
  - `GET /monitoring` - Serves the monitoring dashboard template

#### 🎨 Dashboard Features
- Brutalist dark theme matching `plan/UI/code.html` design reference
- System overview: CPU, Memory, Disk, Uptime
- Services status with running/stopped indicators
- Ollama status with loaded models and VRAM info
- GPU status for 2x RTX 5060 Ti (memory/utilization bars, temperature)
- Log viewer with tabs (WebUI, Model Calls, SOA1 API)
- Analysis jobs table with status tracking
- Auto-refresh: 5s for status, 3s for logs

#### 📝 Files Modified
- `soa-webui/main.py` - Added monitoring API endpoints (~lines 965-1115)
- `soa-webui/templates/monitoring.html` - Created brutalist monitoring dashboard

#### ✅ Verified
- All monitoring endpoints return correct data
- Dashboard renders at http://localhost:8080/monitoring
- model_calls.jsonl contains both NemoAgent and Phinance entries

---

### December 26, 2025 - Consent Flow Fix & Smoke Test Passing

#### 🛠️ Critical Fixes
- **Fixed consent flow in smoke test**: The test was missing the consent step between stage-ab and analyze-confirm, causing analysis to never start.
- **Added `grant_consent()` function to `test_scripts/userflow_test.py`**: Calls `POST /api/consent` with doc_id and specialist to grant consent before triggering analysis.
- **Fixed `test_scripts/integration_test_12_files.py`**: Rewrote to follow same pattern as userflow_test (single upload flow, proper consent step, PYTHONPATH handling for restart).
- **Fixed job creation in `/analyze-stage-ab`** (from previous session): Now creates job record if missing, fixing "Job record not found" errors.

#### ✅ Verified
- Smoke test (`userflow_test.py`) passes end-to-end: upload → stage-ab → consent → analyze-confirm → poll → completed
- Integration test (`integration_test_12_files.py N=1`) passes including WebUI restart and chat rehydration
- All 83 transactions extracted from Apple Card statement
- Reports created: transactions.json (23KB), analysis.json (2KB)

#### 📝 Files Modified
- `test_scripts/userflow_test.py` - Added grant_consent() function and consent step in main()
- `test_scripts/integration_test_12_files.py` - Rewrote to use single upload flow with consent
- `RemAssist/errors.md` - Documented consent flow fix
- `RemAssist/NEXT_TASKS.md` - Updated to reflect completed smoke test tasks

#### 🔜 Next Steps
- Scale integration test to N=12 (optional stress test)
- Verify `logs/model_calls.jsonl` contains NemoAgent and Phinance entries
- Continue with Dashboard JSON Conversion Utility (Section 1 in NEXT_TASKS.md)
- Continue with NemoAgent System Prompt & Architecture (Section 2 in NEXT_TASKS.md)

---

### December 25, 2025 - Consent Router Registration & Phinance Model Logging

#### 🛠️ Critical Fixes
- **Prepared /consent endpoint**: Implemented `home-ai/soa1/consent.py` with a POST `/consent` route that records user consent. NOTE: the router is implemented but intentionally NOT mounted at module-import time to avoid startup issues; mount the router safely inside `create_app()` (deferred import) when ready to enable it.
- **Added structured model-call logging for Phinance**: Instrumented `call_phinance()` and `call_phinance_insights()` in `home-ai/finance-agent/src/models.py` to use the existing `log_model_call` helper. Phinance requests/responses will log to `logs/model_calls.jsonl` with latency, status, and redacted prompts.

#### ✅ Verified
- All uuid4 usages across the codebase are properly imported (no bare `uuid4()` without import)
- Syntax checks pass on all modified files

#### 📝 Files Modified
- `home-ai/soa1/consent.py` - Implemented consent endpoint with safe lazy import of finance storage
- `home-ai/finance-agent/src/models.py` - Added structured logging for Phinance calls

#### 🔜 Next Steps
- Safely mount `/api/consent` by importing the router inside `create_app()` and re-run smoke tests (upload → consent → analyze-confirm → verify DB/files)
- Run integration_test_12_files.py when smoke test passes
- Verify `logs/model_calls.jsonl` contains both NemoAgent and Phinance entries for a full run
- Update SERVICES_CONFIG.md with consent flow documentation (already updated)

#### 📘 New Documentation
- **Added** `RemAssist/CONSENT_PHINANCE_CHANGES.md` which summarizes the changes and next steps.
- **Added** `RemAssist/ACTIONS_DETAILED.md` which contains a detailed action-by-action log: what changed, why it was needed, how it affected functionality, and the benefits to the project.

---

### December 25, 2025 - GPU Fix & E2E Pipeline Verification

#### 🛠️ Critical Fixes
- **Fixed phinance-json GPU allocation**: Model was running 90% CPU / 10% GPU. Root cause was missing `num_gpu` parameter in Ollama API calls.
- **Updated `soa-webui/model_manager.py`**: Added `num_gpu: 99` to force full GPU offload when loading models.
- **Fixed duplicate API call bug**: Removed accidental duplicate POST request in model loader.
- **Fixed test script path resolution**: Updated `test_finance_pipeline.py` to use correct `FINANCE_DATA_DIR` environment variable instead of relative path.

#### ✅ E2E Pipeline Verified
- All tests pass: Model init, PDF upload, NemoAgent conversation, Stage A/B analysis, Phinance extraction, follow-up questions
- **phinance-json**: 4.0 GB on GPU 0, 100% GPU
- **NemoAgent**: 9.4 GB on GPU 1, 100% GPU
- 83 transactions extracted from Apple Card statement with insights

#### 📝 Files Modified
- `soa-webui/model_manager.py` - Added `num_gpu` option, removed duplicate POST
- `soa-webui/test_finance_pipeline.py` - Fixed upload directory path resolution

---

### December 25, 2025 - GPU Migration, Model Fixes, Dashboard Output, Architecture

#### 🛠️ Critical Fixes
- Diagnosed and resolved Ollama running in CPU-only mode after hardware migration (Intel X670 + 2x RTX 5060 Ti, 32GB VRAM)
- Restarted Ollama, confirmed models now run on GPU with proper VRAM allocation
- Updated model keep_alive settings to prevent unloading from VRAM
- Fixed SOA1 config to use NemoAgent as orchestrator model
- Unloaded unnecessary models (qwen2.5, llama3.2) from VRAM

#### 📊 Dashboard Output & Conversion Utility
- Validated dashboard expects analysis.json and transactions.json in specific format
- Planned and approved separate Python utility for robust conversion of phinance output to dashboard JSON
- Utility will handle anomalies and edge cases, using NemoAgent for reasoning/inference if needed

#### 🧠 Architecture Clarification
- NemoAgent confirmed as main orchestrator for SOA1 (not just finance)
- Architecture updated: NemoAgent (GPU 0) orchestrates, phinance-json (GPU 1) as finance specialist
- All services (SOA1 API, WebUI, Ollama, MemLayer) running and verified

#### ✅ Completed Tasks
- GPU migration and model config fixes
- Dashboard output requirements validated
- Conversion utility planned
- Architecture clarified

#### 🔜 Next Steps
- Implement dashboard JSON conversion utility (separate file)
- Integrate NemoAgent for anomaly handling in conversion
- Finalize architecture documentation and system prompt for NemoAgent
- Verify logging for all model actions, reasoning, tool calls (with timestamp)

---

### December 25, 2025 - Model Loader Diagnostic Logging & Qwen Audit

#### 🔎 Troubleshooting & Diagnostics
- Added diagnostic logging to `soa-webui/model_manager.py` to log every outgoing Ollama request (model name, payload, endpoint, timestamp)
- Ran end-to-end userflow test (`test_finance_pipeline.py`) to monitor for any requests to qwen2.5:7b-instruct
- Confirmed only NemoAgent and phinance-json models were requested/loaded
- No evidence in logs or test output of any qwen2.5:7b-instruct requests originating from project code

#### #### 📝 Key Decisions
- Diagnostic logging comment retained for maintainability and clarity
- Confirmed codebase is not responsible for unexplained qwen requests; any further qwen loads must originate outside this project

#### ✅ Completed Tasks
- Diagnostic logging patch implemented
- Userflow test run and logs verified

#### 🔜 Next Steps
- If unexplained qwen requests persist in Ollama logs, trace external processes or Ollama state
- Continue with dashboard JSON utility and architecture documentation
- Standardize SOA1 API runtime: add systemd unit and start/stop scripts; recommend using the Uvicorn CLI for predictable runtime and logging
- Add cleanup scripts and instructions to prevent stale processes and resource leaks
- Verify `/upload-pdf` and `/health` endpoints after restart

---

### December 25, 2025 - Finance Upload Consent & Persistence

#### 📘 Design Doc Created
- Created `RemAssist/FINANCE_UPLOAD_CONSENT_AND_PERSISTENCE.md` documenting the full upload → staged parsing → consent → persistence → analysis flow, database schema for `documents`/`transactions`/`merchant_dictionary`, event and API shapes (job events, SSE/WebSocket, `/analyze-confirm`), and enforcement of consent guardrails from `IMPLEMENTATION_GUIDE.md`.

#### 🛠️ Actions Taken
- Documented required orchestrator behavior (state machine, consent enforcement), staged parser events (METADATA_READY, HEADERS_READY, DOC_TEXT_READY, TRANSACTIONS_READY), and storage patterns (persist parsed transactions to SQLite to avoid re-parsing).
- Added recommended next steps: implement `home-ai/soa1/orchestrator.py` (consent engine), `home-ai/soa1/parser.py` (staged parsing), and `home-ai/finance-agent/src/storage.py` (DB schema and DAO helpers).

#### ✅ Notes / Rationale
- Aligns with Implementation Guide: upload ≠ consent, agent may preview metadata at Stage B, specialist calls require explicit confirmation.
- Ensures the agent has full parsed data persisted for future sessions and avoids re-parsing PDFs.

#### 🔜 Next Steps
- Implement orchestrator, parser, and storage files (in that order) and add unit/integration tests validating consent enforcement and persistence.
- Add event streaming (SSE or WebSocket) for UI engagement and per-step timing instrumentation for the analysis pipeline.


---
