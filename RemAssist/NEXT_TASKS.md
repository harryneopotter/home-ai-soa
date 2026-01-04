# 📋 RemAssist — Unified Task Queue
*Supersedes previous `next-tasks.md` and `NEXT_TASKS.md`. All queues now live here.*

_Last updated: January 4, 2026 (Self-Spawning Phinance Session)_

---

## 🔍 Current System Snapshot
- ✅ **Self-Spawning Phinance**: Agent spawns own background thread, no API cooperation needed
- ✅ **Hybrid Calculation Architecture**: Python calculates (100% accurate), qwen2.5 generates insights (6.3s total)
- ✅ **Rate Limiting Implemented**: Configured for all public-facing endpoints (10/min for uploads, 20/min for TTS, 100/min for general API).
- ✅ **Apple Card Extraction FIXED**: State machine parser replaces broken regex, extracts 266+ transactions from 5 PDFs
- ✅ Working: SOA1 API, WebUI, Ollama, MemLayer, finance pipeline, E2E tests passing
- ✅ GPU Status: NemoAgent (13GB, GPU 0, 100%), phinance-json (4GB, GPU 1, 100%)
- ✅ **Progressive Flow**: Implemented stateful orchestration and instant delivery (Session 27).
- ✅ **Progressive Flow Phase Separation**: Consent returns immediately, phinance runs in background (Session 29)
- ✅ **Model Call Logging**: Enhanced with correlation IDs, attempt tracking, and proper source identification.
- ✅ **Full Batch Persistence**: Compressed text storage (~98% compression), auto-recovery on startup

---

## 🚀 Immediate Priority Tasks

### 1. Refined Output Implementation (Session 28)
**Goal**: Finalize the generation logic for each report format.
- [ ] **Dashboard JSON**: Ensure it matches all fields required by `soa_dashboard.html`.
- [ ] **PDF Export**: Implement the actual `generate_pdf` shell script/tool.
- [ ] **Infographic**: Integrate with an image generation model (e.g., Z image turbo).

### 2. Merchant Categorization Improvement
- [ ] Too many transactions falling into "Other" category (65%+ in test)
- [ ] Expand `_categorize_merchant()` keyword lists
- [ ] Consider LLM-assisted categorization for unknown merchants

### 3. Memory Architecture Upgrade (MAJOR FEATURE)
- [ ] **Phase 1: Mem0 Setup** (Week 1)
  - [ ] Install Mem0, configure Kuzu + ChromaDB + Ollama
  - [ ] Create family entity schema, test extraction
  - [ ] Integrate with SOA1Agent, replace MemLayer

---

## 🏁 Recently Completed (Jan 4, 2026 - Session 30)
- **Session 30**: Self-Spawning Phinance Analysis
  - Root cause: `/api/chat/stream` was missing `trigger_phinance_background` handler
  - Solution: Made agent self-contained - spawns own background thread via `_spawn_phinance_background()`
  - Removed API-side `_run_phinance_background()` function
  - Added `pre_generate_outputs_sync()` to batch_processor for thread compatibility
  - Files: agent.py, api.py, batch_processor.py

## 🏁 Recently Completed (Jan 3, 2026 - Session 29)
- **Session 29**: Progressive Flow Phase Separation
  - Fixed collapsed phases 2 & 3 - consent now returns immediately
  - Added `_run_phinance_background()` async function in api.py
  - Agent returns `trigger_phinance_background` signal for async processing
  - Enhanced `/api/batch/status/{batch_id}` with `analysis_summary` and `completion_message`
  - Fixed duplicate "How would you like the report?" prompt (was in both `_run_hybrid_analysis` and `_format_analysis_response`)
  - Files: agent.py, api.py

## 🏁 Recently Completed (Jan 3, 2026 - Session 28)
- **Session 28**: Apple Card Multi-Line Parser Fix
  - Root cause: APPLE_CARD_REGEX expected single-line format, but PDFs extract to multi-line
  - Implemented `_extract_apple_card_transactions()` state machine parser
  - Handles: date lines, merchant+address lines, cashback %, cashback $, transaction total
  - Filters: returns, negatives, amounts < $1.00
  - Results: 266 transactions / $33,455.07 from 5 PDFs (was 0 before)
  - Fixed f-string syntax error (backslash in expression)
  - Full E2E test passed: Upload → Extraction → Analysis → Output prompt
  - Files: batch_processor.py

## 🏁 Recently Completed (Jan 3, 2026 - Session 27)
- **Session 27**: Refined Agent Flow & Instant Delivery
  - Implemented stateful orchestration (intent question first)
  - Added engagement findings during processing
  - Pre-generated outputs (JSON, PDF command, Image prompt) for instant delivery
  - Files: api.py, agent.py, batch_processor.py, output_generator.py, soa-webui/main.py

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