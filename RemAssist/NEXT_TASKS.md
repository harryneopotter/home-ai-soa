# 📋 RemAssist — Unified Task Queue
*Supersedes previous `next-tasks.md` and `NEXT_TASKS.md`. All queues now live here.*

_Last updated: January 2, 2026 (Hybrid Calculation Architecture Session)_

---

## 🔍 Current System Snapshot
- ✅ **Hybrid Calculation Architecture**: Python calculates (100% accurate), qwen2.5 generates insights (6.3s total)
- ✅ **Rate Limiting Implemented**: Configured for all public-facing endpoints (10/min for uploads, 20/min for TTS, 100/min for general API).
- ✅ **Apple Card Fix Implemented**: Logic fixed in `models.py` to correctly trigger specialized extraction prompt, resulting in non-zero metrics.
- ✅ Working: SOA1 API, WebUI, Ollama, MemLayer, finance pipeline, E2E tests passing
- ✅ GPU Status: NemoAgent (13GB, GPU 0, 100%), phinance-json (4GB, GPU 1, 100%)
- ✅ **Progressive Batch Architecture**: Logic complete (WebUI integration complete, backend logic complete).
- ✅ **Model Call Logging**: Enhanced with correlation IDs, attempt tracking, and proper source identification.

---

## 🚀 Immediate Priority Tasks

### 1. Full Batch State Persistence (Options B/C) - COMPLETED
**Current State:** Full batch persistence implemented with compressed text storage
**Implementation:** Compressed extracted text + Phinance analysis JSON in SQLite

**What was implemented:**
- Added `extracted_text_gz` BLOB column (gzip compressed text, ~98% compression)
- Added `phinance_analysis` TEXT column (JSON)
- Gzip compression helpers: `compress_text()`, `decompress_text()`
- Persistence functions: `save_batch_extracted_text()`, `save_batch_phinance_analysis()`
- Hydration: `BatchProcessor.hydrate_from_db()` restores batches on startup
- Auto-save: Extracted text saved on upload, Phinance analysis saved on completion

**Files modified:**
- `home-ai/finance-agent/src/storage.py` — schema + persistence functions
- `home-ai/soa1/batch_processor.py` — hydration method
- `home-ai/soa1/api.py` — startup hydration + text persistence on upload
- `home-ai/soa1/agent.py` — Phinance analysis persistence on completion

**Recovery flow:**
1. SOA1 startup → `batch_processor.hydrate_from_db(storage)`
2. Load incomplete batches with `extracted_text_gz`
3. Decompress text → rebuild `BatchState.phinance_prompt`
4. If `phinance_analysis` exists → restore and set status=complete

### 2. Progressive Batch Architecture (MAJOR FEATURE)
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
- [x] **Hybrid Calculation Architecture** - Python for math, LLM for insights

### 3. Comprehensive Security Hardening (Deferred)
- [ ] Comprehensive Security Hardening (API Key Auth, Audit Logging, HTTPS Enforcement) for future development phase.

---

## 📚 Session Documentation
- [x] Update `RemAssist/History.md` with current session summary.
- [x] Update `RemAssist/NEXT_TASKS.md` with final status.

---

## 🏁 Recently Completed (Jan 3, 2026 - Session 25)
- **Session 25**: Full batch persistence with compressed text storage
  - Added `extracted_text_gz` BLOB and `phinance_analysis` TEXT columns
  - Gzip compression (~98% reduction on real data)
  - Auto-save extracted text on upload, Phinance analysis on completion
  - `BatchProcessor.hydrate_from_db()` for startup recovery
  - Files: storage.py, batch_processor.py, api.py, agent.py

## 🏁 Recently Completed (Jan 3, 2026 - Session 24)
- **Session 24**: Batch persistence (Option A) - batch_id ↔ session_id mapping in SQLite
  - Added `batches` table to storage.py
  - Added status callback in batch_processor.py
  - New endpoint: `GET /api/batch/session/{session_id}` for page refresh recovery
  - Fixed WebUI proxy to use SOA1's /upload-batch (was creating orphan batch_ids)

## 🏁 Recently Completed (Jan 2, 2026 - Sessions 19-23)
- **Session 23**: Hybrid Calculation Architecture - Python calculates (100% accurate, 0.05ms), qwen2.5 generates insights (6.3s). Fixed Phinance insights issue (baked-in Modelfile).
- **Session 22**: Created HARDWARE_SPECS.md, updated AGENTS.md with mandatory GPU check rule.
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