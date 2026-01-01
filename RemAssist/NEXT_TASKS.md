# 📋 RemAssist — Unified Task Queue
*Supersedes previous `next-tasks.md` and `NEXT_TASKS.md`. All queues now live here.*

_Last updated: December 31, 2025 (Session 11)_

---

## 🔍 Current System Snapshot
- ✅ Working: SOA1 API, WebUI, Ollama, MemLayer, finance pipeline, E2E tests passing
- ✅ GPU Status: NemoAgent (13GB, GPU 0, 100%), phinance-json (4GB, GPU 1, 100%)
- ✅ GPU Fix: `num_gpu: 99`, `num_ctx: 32768` applied to all model calls
- ✅ Performance: 8 PDFs in 84s (~10.5s avg), 437 transactions extracted
- ✅ **Consolidated Dashboard**: `/dashboard/consolidated` with charts, tables, filtering
- ✅ **LLM Response Validation**: Pydantic schemas for phinance output validation
- ✅ **Retry Logic Wired**: `call_phinance()` now retries with validation feedback (max 3 attempts)
- ✅ **Security Hardened**: XSS fixes (escapeHtml), path traversal protection
- ✅ **UI Enhanced**: Date range picker, CSV export for transactions
- ✅ Consent endpoint registered at `/api/consent`
- ✅ Phinance model calls now logged to `logs/model_calls.jsonl`
- ✅ Monitoring Dashboard: `/monitoring` endpoint with system stats, services, GPUs, logs, jobs

---

## 🚀 Immediate Priority Tasks

### 0. LLM Response Validation ✅ COMPLETED (Dec 31, 2025)
- [x] Create Pydantic schemas for phinance LLM response validation
- [x] Implement JSON extraction from markdown code blocks
- [x] Add date format validation, amount bounds checking
- [x] Handle bare list responses (no wrapper object)
- [x] Create retry infrastructure base (RetryConfig, RetryContext, build_retry_prompt)
- [x] Integrate validation into `call_phinance()` with optional `validate` parameter
- [x] Add `call_phinance_validated()` for typed returns
- [x] Test with real phinance output files

### 0.1 GPU Eviction Fix ✅ COMPLETED (Dec 31, 2025)
- [x] Fix `num_gpu: 1` → `99` in finance-agent/src/models.py
- [x] Add `num_ctx: 32768` for NemoAgent, `num_ctx: 4096` for phinance
- [x] Fix Ollama response parsing in soa1/models.py
- [x] Verify 100% GPU usage during batch test

### 0.2 Consolidated Dashboard ✅ COMPLETED (Dec 31, 2025)
- [x] Create `/api/reports/consolidated` endpoint
- [x] Create consolidated_dashboard.html with Chart.js
- [x] Add spending by category chart
- [x] Add monthly trends chart
- [x] Add transactions table with search/filter
- [x] Add insights and recommendations display
- [x] Test with 8 PDFs batch

### 1. Wire Retry Logic ✅ COMPLETED (Dec 31, 2025)
- [x] Integrate retry loop into `call_phinance()` using `build_retry_prompt()`
- [x] Add configurable max_attempts (default: 3)
- [x] Log retry attempts with validation errors
- [ ] Add metrics for retry success rate (deferred - needs monitoring integration)

### 1.1 Keep-Alive & Ollama API Standardization
- [x] `home-ai/soa1/models.py` - uses `/api/chat` with `keep_alive: -1` ✅
- [x] `home-ai/finance-agent/src/models.py` - uses `num_gpu: 99`, `num_ctx` ✅
- [ ] Add unit/integration test verifying models are pinned (`ollama ps` shows `UNTIL: Forever`)
- [ ] Add linter/CI check for `/v1` endpoints where `keep_alive` is required

### 2. Input Validation & Sanitization ✅ COMPLETED (Dec 31, 2025)
- [x] Audit XSS vulnerabilities in dashboard templates (merchant names, categories)
- [x] Add path traversal protection for PDF uploads
- [x] Verify Jinja2 autoescape is enabled (client-side JS needed escapeHtml())
- [ ] Add input length limits to all API endpoints (deferred)

### 3. UI Enhancements ✅ COMPLETED (Dec 31, 2025)
- [x] Consolidated dashboard with charts ✅
- [x] Add date range picker to consolidated dashboard
- [x] Add export to CSV functionality
- [ ] Add export to PDF functionality (needs jsPDF library)
- [ ] Add spending alerts/thresholds
- [ ] Mobile responsive improvements

### 4. Performance Optimizations ✅ COMPLETED (Dec 31, 2025)
- [x] Parallel PDF processing for batch uploads (`/analyze-batch` with ThreadPoolExecutor)
- [x] Transaction caching to avoid re-extraction (`has_transactions_for_doc()` check)
- [x] Lazy loading for large transaction tables (paginated `/api/transactions` + UI pagination)

---

## 🔜 Potential Next Steps

### 5. Chat Context & Memory Improvements
- [ ] Implement chat history persistence (currently session-only)
- [ ] Add conversation memory to MemLayer for cross-session context
- [ ] Improve finance context injection in `/api/chat`

### 6. Multi-Document Analysis
- [x] Support batch PDF uploads in single request (`/analyze-batch` endpoint)
- [ ] Cross-document spending comparison
- [ ] Trend analysis across time periods
- [ ] Merchant normalization (same merchant, different names)

### 7. Security Hardening
- [ ] Rate limiting on all API endpoints
- [ ] API key authentication for sensitive endpoints
- [ ] Audit logging for all data access
- [ ] HTTPS enforcement

---

## 🏁 Recently Completed (Dec 31, 2025 - Sessions 9, 10, 11 & 12)
- **Performance Optimizations**: Parallel batch processing, transaction caching, paginated lazy loading
- **Security Hardening**: XSS fixes with escapeHtml(), path traversal protection
- **Retry Logic Wired**: call_phinance() now retries with validation feedback
- **UI Enhanced**: Date range picker, CSV export, pagination controls for transactions
- **GPU Eviction Fix**: Models now stay at 100% GPU throughout analysis
- **Consolidated Dashboard**: Full dashboard with charts, tables, AI insights
- **LLM Response Validation**: Pydantic schemas catch malformed LLM responses
- **Batch Testing**: 8 PDFs, 437 transactions, 84s total - all validated
