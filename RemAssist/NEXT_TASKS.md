# 📋 RemAssist — Unified Task Queue
*Supersedes previous `next-tasks.md` and `NEXT_TASKS.md`. All queues now live here.*

_Last updated: January 2, 2026 (Bug Fix and Input Validation Session)_

---

## 🔍 Current System Snapshot
- ✅ **Rate Limiting Implemented**: Configured for all public-facing endpoints (10/min for uploads, 20/min for TTS, 100/min for general API).
- ✅ **Apple Card Fix Implemented**: Logic fixed in `models.py` to correctly trigger specialized extraction prompt, resulting in non-zero metrics.
- ✅ Working: SOA1 API, WebUI, Ollama, MemLayer, finance pipeline, E2E tests passing
- ✅ GPU Status: NemoAgent (13GB, GPU 0, 100%), phinance-json (4GB, GPU 1, 100%)
- ✅ **Progressive Batch Architecture**: Logic complete (WebUI integration complete, backend logic complete).
- ✅ **Model Call Logging**: Enhanced with correlation IDs, attempt tracking, and proper source identification.

---

## 🚀 Immediate Priority Tasks

### 1. Progressive Batch Architecture (MAJOR FEATURE)
**Reference:** `RemAssist/PROGRESSIVE_BATCH_ARCHITECTURE.md`

Complete 5-phase pipeline for batch uploads with parallel processing:
- [x] **Security Layer** (Priority 1 - required for production)
- [x] **Batch Processing** (Priority 2 - enables better UX)
- [x] **Output Pre-generation** (Priority 3 - polish)
- [x] **WebUI Integration** (Priority 4)
  - [x] Update `index.html` for batch upload UI
  - [x] Implement progressive display (Phase 1-5)
  - [x] Add output selection buttons (Dashboard, PDF, Infographic)

### 2. Pipeline Enhancements
- [x] Integrate merchant normalization into transaction extraction pipeline
- [x] Add metrics for retry success rate (phinance_attempts tracked in BatchState)
- [x] Add input length limits to all API endpoints

### 3. Comprehensive Security Hardening (Deferred)
- [ ] Comprehensive Security Hardening (API Key Auth, Audit Logging, HTTPS Enforcement) for future development phase.

---

## 📚 Session Documentation
- [x] Update `RemAssist/History.md` with current session summary.
- [x] Update `RemAssist/NEXT_TASKS.md` with final status.

---

## 🏁 Recently Completed (Jan 2, 2026 - Sessions 19-21)
- **Session 21**: Fixed _invoke_phinance() tuple unpacking bug, added input length limits to all API endpoints, code cleanup.
- **Session 20**: Implemented Rate Limiting on all public API endpoints. Deferred comprehensive security hardening.
- **Session 19**: Fixed critical Apple Card extraction bug in `models.py` and verified non-zero metrics via E2E test.

---

## 🏁 Recently Completed (Dec 31, 2025 - Sessions 9-13)
- **Session 13**: Chat history persistence, cross-document comparison, merchant normalization, keepalive test
- **Session 12**: Parallel batch processing, transaction caching, paginated lazy loading
- **Session 11**: XSS fixes with escapeHtml(), path traversal protection, retry logic wired
- **Session 10**: Consolidated dashboard, LLM response validation with Pydantic
- **Session 9**: GPU eviction fix, batch testing (8 PDFs, 437 transactions)