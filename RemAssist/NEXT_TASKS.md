# 📋 RemAssist — Unified Task Queue
*Supersedes previous `next-tasks.md` and `NEXT_TASKS.md`. All queues now live here.*

_Last updated: December 31, 2025 (Session 13)_

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
- ✅ **Chat History**: Persistent chat history with multi-turn context
- ✅ **Cross-Doc Compare**: `/api/reports/compare` endpoint for multi-document comparison
- ✅ **Merchant Normalization**: 40+ patterns for common merchants (Amazon, Uber, etc.)
- ✅ Consent endpoint registered at `/api/consent`
- ✅ Phinance model calls now logged to `logs/model_calls.jsonl`
- ✅ Monitoring Dashboard: `/monitoring` endpoint with system stats, services, GPUs, logs, jobs

---

## 🚀 Immediate Priority Tasks

### 5. Chat Context & Memory Improvements ✅ COMPLETED (Dec 31, 2025)
- [x] Implement chat history persistence (`chat_history` table in storage.py)
- [x] Load chat history in `/api/chat` endpoint (last 20 messages)
- [x] Pass chat history to `agent.ask()` for multi-turn context
- [ ] Add conversation memory to MemLayer for cross-session context (future)
- [ ] Improve finance context injection in `/api/chat` (future)

### 6. Multi-Document Analysis ✅ COMPLETED (Dec 31, 2025)
- [x] Support batch PDF uploads in single request (`/analyze-batch` endpoint)
- [x] Cross-document spending comparison (`POST /api/reports/compare`)
- [x] Merchant normalization (same merchant, different names) - `merchant_normalizer.py`
- [ ] Trend analysis across time periods (future)
- [ ] Integrate merchant normalization into extraction pipeline (future)

### 1.1 Keep-Alive & Ollama API Standardization ✅ COMPLETED (Dec 31, 2025)
- [x] `home-ai/soa1/models.py` - uses `/api/chat` with `keep_alive: -1` ✅
- [x] `home-ai/finance-agent/src/models.py` - uses `num_gpu: 99`, `num_ctx` ✅
- [x] Add integration test verifying models are pinned (`test_ollama_keepalive_integration.py`)
- [ ] Add linter/CI check for `/v1` endpoints where `keep_alive` is required (future)

---

## 🔜 Potential Next Steps

### 7. Security Hardening
- [ ] Rate limiting on all API endpoints
- [ ] API key authentication for sensitive endpoints
- [ ] Audit logging for all data access
- [ ] HTTPS enforcement

### 8. UI Enhancements (Remaining)
- [ ] Add export to PDF functionality (needs jsPDF library)
- [ ] Add spending alerts/thresholds
- [ ] Mobile responsive improvements
- [ ] Cross-document comparison UI

### 9. Pipeline Enhancements
- [ ] Integrate merchant normalization into transaction extraction pipeline
- [ ] Add metrics for retry success rate (needs monitoring integration)
- [ ] Add input length limits to all API endpoints

---

## 🏁 Recently Completed (Dec 31, 2025 - Sessions 9-13)
- **Session 13**: Chat history persistence, cross-document comparison, merchant normalization, keepalive test
- **Session 12**: Parallel batch processing, transaction caching, paginated lazy loading
- **Session 11**: XSS fixes with escapeHtml(), path traversal protection, retry logic wired
- **Session 10**: Consolidated dashboard, LLM response validation with Pydantic
- **Session 9**: GPU eviction fix, batch testing (8 PDFs, 437 transactions)
