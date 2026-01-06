# 📋 RemAssist — Unified Task Queue
*Supersedes previous `next-tasks.md` and `NEXT_TASKS.md`. All queues now live here.*

_Last updated: January 6, 2026 (Session 41 - Stability Fixes + Phinance Context Window)_

---

## 🔍 Current System Snapshot
- ✅ **LLM Merchant Categorization**: Phinance categorizes unknown merchants, results cached in DB (Session 40)
- ✅ **Merchant Stable IDs**: Graph-safe linkage with sha256 hash, survives dictionary updates
- ✅ **PDF Export**: Full pipeline - WeasyPrint generates A4 reports, agent returns download_url, frontend triggers download
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
- ✅ **Phase 1 Code Complete**: Transaction duplication fix deployed, cleanup script run (removed 223 dupes)
- ✅ **Phinance JSON Repair**: 10/10 success rate with improved `repair_json()` function (Session 35)
- ✅ **PDF Upload Validation**: Extension + magic byte validation prevents non-PDF uploads (Session 36)
- ✅ **Phinance Context Window**: Set to 4096 tokens - DO NOT CHANGE (Session 41)

---

## 🚀 Immediate Priority Tasks

### 0. Fix Phinance Prompt Schema Mismatch ✅ RESOLVED (Session 35)
**Problem**: System prompt (Modelfile) and user prompt had conflicting schemas
**Resolution**: 
- Updated `build_insights_prompt()` to include `drain_verifications` in example JSON when drains exist
- Improved `repair_json()` to handle phinance-3b quirks:
  - Unquoted numeric keys (2: → "2":)
  - Dict-style entries in arrays (["a", 2: "b"] → ["a", "b"])
  - Nested arrays ([["text"]] → ["text"])
  - Comments, trailing commas, orphan strings
- **Result**: 10/10 JSON parse success rate in testing

### 0.7 CRITICAL: Analysis Persistence and Logging Failure ✅ RESOLVED (Session 38)
**Source**: E2E Instrumented Test (see `RemAssist/E2E_Analysis_Failure.md`)
**Problem**: Analysis results (`phinance_analysis` JSON) were not being persisted to the `batches` table after job completion.
**Root Cause**: `_run_hybrid_analysis()` in agent.py stored analysis in memory (`state.phinance_analysis`) but never called `save_batch_phinance_analysis()` to persist to DB. The `analyze_batch()` method had the persist call, but `_spawn_phinance_background` → `_invoke_phinance` → `_process_with_batch_state` → `_run_hybrid_analysis` flow did not.
**Fix Applied**: Added `chat_storage.save_batch_phinance_analysis(state.batch_id, analysis)` call in `_run_hybrid_analysis()` after setting `state.phinance_analysis`.
**Files**: `home-ai/soa1/agent.py` (line ~365)

### 0.0 Implement NemoAgent Critic Pass
**Source**: Session 34 architecture discussion
**Purpose**: Validate Phinance output against source data before returning to user
**Status**: `llm_critic.py` created, basic integration added to `agent.py`
**Remaining**: Wire into production pipeline, add retry logic on validation failure

**Architecture** (2× 3060 12GB):
- GPU 0: NemoAgent (13GB) - always warm, orchestrator
- GPU 1: Phinance-JSON (4GB) - generator

**Pipeline**:
```
Phinance (generate) → NemoAgent (validate) → if fail → retry/escalate to qwen
```

**Files**: `utils/llm_critic.py`, `agent.py`

### 0.1 PDF Date Range Bug ✅ RESOLVED (Session 38)
**Problem**: PDF export showed "11/23/2025 to 12/31/2024" - dates were backwards
**Root Cause**: String comparison on MM/DD/YYYY format doesn't work (alphabetical vs chronological)
**Fix Applied**: Applied same `_parse_date_str()` pattern to second occurrence at line ~537 in soa-webui/main.py
**File**: `soa-webui/main.py`

### 0.5 CRITICAL: Transaction Duplication Bug - PHASE 1 COMPLETE ✅
**Status**: Code deployed, cleanup run (removed 223 dupes, 8873 remaining)
**Note**: Remaining transactions may still have cross-doc pollution from before fix. Consider full re-upload for clean data.

### 0.6 Backfill Existing "Other" Merchants ✅ COMPLETE (Session 37)
**Problem**: 412 unique merchants were in "Other" category (6306 transactions)
**Resolution**: 
- Phase 1: NemoAgent categorized 172 merchants, Qwen categorized remaining 37
- Cross-verified with Qwen, corrected 19 errors
- Phase 2: Categorized final 124 "Other" transactions (19 unique merchants)
- Qwen verification found and corrected 2 more issues
- **Result**: Reduced "Other" from 6,306 → 0 transactions (100% categorized)
**Files**: Various SQL updates to `finance.db`, categorization scripts in `/projects/fixes/`

**Goal**: Finalize the generation logic for each report format.
- [ ] **Dashboard JSON**: Ensure it matches all fields required by `soa_dashboard.html`.
- [x] **PDF Export**: ✅ Implemented with WeasyPrint (Session 31)
- [ ] **Infographic**: Integrate with an image generation model (e.g., Z image turbo).

### 2. Merchant Categorization Improvement ✅ COMPLETE (Session 40)
- [x] Too many transactions falling into "Other" category (65%+ in test)
- [x] Expand `_categorize_merchant()` keyword lists
- [x] LLM-assisted categorization for unknown merchants - IMPLEMENTED (but disabled)
  - Added `categorize_merchants_llm()` in `models.py`
  - Added batch cache functions in `storage.py`
  - Integrated into `batch_processor.py` after regex pass
  - **DISABLED**: `USE_LLM_CATEGORIZATION = False` until Phase 3
  - Caches results in `merchant_mappings` table with `source='phinance'`

### 2.5 Phase 3: Chat-Based Merchant Correction (BLOCKED)
**Prerequisite for enabling LLM categorization**
- [ ] `find_merchant_candidates()` - fuzzy search for merchants
- [ ] `update_merchant_category()` - correct wrong categorizations with audit log
- [ ] `undo_last_mapping_change()` - revert support
- [ ] Register as agent tools for chat-based correction
- [ ] **Enable `USE_LLM_CATEGORIZATION = True`** after this is complete

### 3. Memory Architecture Upgrade (MAJOR FEATURE)
- [ ] **Phase 1: Mem0 Setup** (Week 1)
  - [ ] Install Mem0, configure Kuzu + ChromaDB + Ollama
  - [ ] Create family entity schema, test extraction
  - [ ] Integrate with SOA1Agent, replace MemLayer

---

## 📅 Scheduled Tasks (Jan 6, 2026)

### 4. Confidence Score Integration
- [ ] **Merchant Confidence in LLM Prompts**: Pass `merchant_confidence` stats to `build_insights_prompt()` so LLM can flag uncertain categorizations
- [ ] **AI Insight Confidence Scores**: Investigate adding confidence scores to LLM-generated insights/recommendations
  - Should insights have confidence? (e.g., "High confidence: You spend most on Amazon" vs "Low confidence: Subscription pattern detected")
  - How to compute? LLM self-assessment? Heuristics based on data quality?
  - Where to display? PDF reports? Dashboard? Chat responses?

---

## 🔧 Stability & Architecture Tasks (from MASTER_ISSUES_AND_FIXES.md)

### S1. Analysis Persistence Hardening [PRIORITY: HIGH]
**Status**: Partially fixed in Session 38, needs rowcount hardening
**Problem**: `save_batch_phinance_analysis` UPDATE fails silently if batch record missing
**Impact**: Data loss - analysis results disappear

**Implementation**:
- File: `home-ai/finance_agent/src/storage.py`
- In `save_batch_phinance_analysis()`:
  - Check `cursor.rowcount` after UPDATE
  - If rowcount == 0, execute INSERT to create record
- Guardrails: Pure DB layer change, no user-facing impact, no consent flow affected

### S2. WebUI Async HTTP Calls [PRIORITY: HIGH]
**Problem**: `soa-webui/main.py` uses sync `requests.post` in async handlers
**Impact**: Large uploads freeze UI for all users (blocks event loop)

**Implementation**:
- File: `soa-webui/main.py`
- Replace `requests.post` with `httpx.AsyncClient` or `aiohttp`
- Endpoints affected: `/api/proxy/upload`, `/api/proxy/upload-batch`
- Guardrails: Implementation detail only, API contract unchanged, no consent flow affected

### S3. Zombie Task Auto-Timeout [PRIORITY: HIGH] ✅ COMPLETE (Session 41)
**Problem**: Background tasks can hang, leaving status as "parsing" forever
**Impact**: Frontend polls infinitely, user stuck

**Implementation**:
- File: `home-ai/soa1/batch_processor.py`
- In `get_batch_state()`:
  - If status == "parsing" AND `created_at` > 10 minutes ago → auto-set "failed"
  - Triggers status callback to persist to DB
- Guardrails: Self-correcting read logic, doesn't interfere with active tasks

### S4. Frontend Polling Timeout [PRIORITY: MEDIUM] ✅ COMPLETE (Session 41)
**Problem**: `index.html` polls forever if status doesn't change
**Impact**: Browser resource waste, no user feedback on failure

**Implementation**:
- File: `soa-webui/templates/index.html`
- Added `pollAttempts` counter to both `pollBatchStatus()` and `pollForAnalysisComplete()`
- If > 300 attempts (10 min at 2s intervals) → stop polling, show timeout message
- Guardrails: Client-side only, no backend changes

### S5. Double-Submission Prevention [PRIORITY: MEDIUM]
**Problem**: User can click "Process" or send messages multiple times while backend is thinking
**Impact**: Race conditions, duplicate processing

**Implementation**:
- File: `soa-webui/templates/index.html`
- Disable input/buttons on submission
- Re-enable only on response or error
- Guardrails: Client-side only, standard UX pattern

### S6. Brittle Dynamic Imports [PRIORITY: LOW]
**Problem**: `agent.py` imports storage inside methods, masking errors
**Impact**: Runtime failures instead of startup failures

**Implementation**:
- File: `home-ai/soa1/agent.py`
- Move imports to top level
- Use try/except with `STORAGE_AVAILABLE` flag pattern
- Guardrails: Makes failures explicit at startup, no behavior change

### S7. Merchant Service Extraction [PRIORITY: LOW - BLOCKED]
**Problem**: `batch_processor.py` has hardcoded regex dict, ignores DB mappings
**Blocked by**: Phase 3 (chat-based correction) - no point wrapping incomplete logic

**Implementation** (when unblocked):
- Create `home-ai/soa1/services/merchant_service.py`
- Encapsulate: DB Lookup → Regex Normalizer → LLM Fallback
- Update `batch_processor.py` to use service if available
- Guardrails: Strategy pattern allows gradual migration

### S8. Logging Endpoint [PRIORITY: LOW]
**Problem**: `/api/log/analysis/{doc_id}` referenced but missing
**Impact**: No debugging visibility for analysis issues

**Implementation**:
- File: `home-ai/soa1/api.py`
- Add GET endpoint
- Read from `logs/model_calls.jsonl`, filter by doc_id or return last N lines
- Guardrails: New read-only endpoint, no risk to existing flows

### S9. Service Layer Extraction [PRIORITY: LOW]
**Problem**: `agent.py` is a "God Object" (~800+ lines)
**Impact**: Hard to maintain and test

**Implementation**:
- Create `home-ai/soa1/services/` directory
- Extract `FinanceService` class for phinance-related logic
- Inject into `SOA1Agent`
- Guardrails: Incremental refactoring, soa1 remains primary orchestrator per IMPLEMENTATION_GUIDE.md

### S10. Containerization [PRIORITY: LOW]
**Problem**: Manual `nohup` deployment
**Impact**: Hard to reproduce environment, no isolation

**Implementation**:
- Create `docker-compose.yml` in project root
- Services: soa1-api, webui, (ollama if not external)
- Guardrails: Parallel deployment option, doesn't break existing scripts

---

## 🏁 Recently Completed (Jan 6, 2026 - Session 39)
- **Session 39**: Merchant Categorization Title Case Fix + DB Cleanup
  - **Problem**: `_categorize_merchant()` returned lowercase categories ("dining", "groceries") but DB standard is Title Case ("Food & Dining", "Groceries")
  - **Impact**: New uploads showed 70%+ "Other" in dashboard pie chart despite merchant backfill being complete
  - **Fix Applied**: Rewrote `_categorize_merchant()` at line 173 in `batch_processor.py`
    - Changed all category keys to Title Case matching DB standard
    - Expanded keywords using 209 merchant categorizations from Session 37
    - Added new categories: Insurance, Automotive, Government & Fees, Donations, Housing, Alcohol
    - Default return changed from "other" to "Other"
  - **DB Cleanup**: Re-categorized 1,050 transactions with lowercase "other"
    - First pass: Automated re-categorization using updated function logic
    - Second pass: Manual categorization for remaining 85 transactions
    - **Result**: 0 "Other" transactions remaining, 12,413 total properly categorized
  - **Final Distribution**: Shopping (3,311), Food & Dining (1,444), Gas (1,347), Utilities (1,038), Groceries (1,002), Subscriptions (901), Transportation (836), Travel (703), Government & Fees (457), Entertainment (314), Health (309), Automotive (296), Housing (136), Alcohol (108), Insurance (103), Personal Services (46), Transfer (23), Education (20), Donations (19)
  - **Files**: `home-ai/soa1/batch_processor.py`, `finance_agent/data/finance.db`

## 🏁 Recently Completed (Jan 6, 2026 - Session 38)
- **Session 38**: Critical Fixes + Merchant Backfill Complete + Dashboard Account Type
  - **Dashboard Account Type Cards**: Hide Income/Savings/Rate cards for credit card statements
    - Added `account_type` detection in `output_generator.py` based on `inferred_type`
    - Credit cards show only "Total Spending" card
    - Bank statements show all 4 cards (Income, Spending, Savings, Rate)
    - Frontend dynamically hides/shows cards based on `account_type` in JSON
  - **0.6 Merchant Backfill COMPLETE**: Eliminated 100% of "Other" category transactions
    - Phase 1: NemoAgent + Qwen categorized 209 unique merchants
    - Phase 2: Final 19 merchants categorized, 2 corrections applied
    - Result: 10,833 transactions fully categorized, 0 in "Other"
  - **0.7 Analysis Persistence FIXED**: `phinance_analysis` now persists to `batches` table
    - Root cause: `_run_hybrid_analysis()` missing DB persist call
    - Added `save_batch_phinance_analysis()` call after setting `state.phinance_analysis`
  - **0.1 PDF Date Range FIXED**: Second occurrence at line ~537 now uses proper date parsing
  - Files: `home-ai/soa1/agent.py`, `home-ai/soa1/output_generator.py`, `soa-webui/main.py`, `soa-webui/templates/soa_dashboard.html`

## 🏁 Recently Completed (Jan 6, 2026 - Session 36)
- **Session 36**: PDF Upload Validation Implementation
  - Created `soa1/utils/file_validation.py` utility module
  - Added validation to WebUI proxy endpoints (`/api/proxy/upload`, `/api/proxy/upload-batch`)
  - Added validation to SOA1 API endpoints (`/upload-batch`, `/upload-pdf`)
  - Validation checks: file extension, magic bytes (`%PDF-`), empty files, size limits
  - Mixed batches: valid files processed, invalid files skipped with warnings
  - All 6 resilience tests passing
  - Files: `home-ai/soa1/utils/file_validation.py`, `home-ai/soa1/api.py`, `soa-webui/main.py`
  - Documentation: `/projects/fixes/PDF_UPLOAD_VALIDATION_PLAN.md`

## 🏁 Recently Completed (Jan 4, 2026 - Session 32)
- **Session 32**: Merchant Stable IDs & Normalization Fix
  - Fixed merchant normalization order - now normalizes BEFORE saving to DB
  - Added `merchant_stable_id` (sha256 hash) for graph-safe linkage
  - Added `MERCHANT_DICT_VERSION` tracking (1.0.0)
  - DB schema updated with `merchant_stable_id` column + migration
  - Per `security-cleanup-feedback.md`: stable IDs survive dictionary updates
  - Commits: `147a5b3`, `fc66b7f`
  - Files: agent.py, storage.py, merchant_normalizer.py

## 🏁 Recently Completed (Jan 4, 2026 - Session 31)
- **Session 31**: PDF Export Feature Complete
  - Added `/export/pdf/{batch_id}` endpoint in soa-webui using WeasyPrint
  - Created `pdf_report.html` template - A4 print-optimized with metrics, categories, merchants, transactions
  - Agent returns `download_url` when user requests PDF export
  - API streaming passes `download_url` through to frontend
  - Frontend triggers file download when `download_url` received
  - Files: soa-webui/main.py, soa-webui/templates/pdf_report.html, home-ai/soa1/agent.py, home-ai/soa1/api.py, soa-webui/templates/index.html

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
### 0.5 CRITICAL: Transaction Duplication Bug (Session 33)
**Problem**: All transactions appear 5-6x in DB and dashboard reports
**Root Cause**: `agent.py` line 281-284 saves ALL transactions to EACH doc_id instead of filtering by source
```python
# BUG: This saves all 50 transactions to each of 5 doc_ids = 250 rows
for doc_id in doc_ids:
    doc_txns = [t for t in all_transactions]  # WRONG - no filtering!
    fa_storage.save_transactions_for_doc(doc_id, doc_txns)
```
**Evidence**: DB shows same transaction with same timestamp appearing 5x per doc_id
**Impact**: 9096 transactions in DB when there should be ~1500-1800

**Fix Required (Option B - track source doc_id)**:

1. **`batch_processor.py`** - Extract per-document, tag with doc_id:
```python
# In background_full_process(), replace combined extraction with:
all_transactions = []
for doc in state.files:
    doc_id = doc.get("doc_id")
    text = doc.get("full_text", "")
    is_apple = doc.get("is_apple_card", False)
    
    if is_apple:
        doc_transactions = _extract_apple_card_transactions(text)
    else:
        doc_transactions = _regex_extract(text, GENERIC_BANK_REGEX)
    
    for tx in doc_transactions:
        tx["doc_id"] = doc_id
    
    all_transactions.extend(doc_transactions)

state.extracted_transactions = all_transactions
```

2. **`agent.py`** - Filter by doc_id when saving:
```python
for doc_id in doc_ids:
    doc_txns = [t for t in all_transactions if t.get("doc_id") == doc_id]
    if doc_txns:
        fa_storage.save_transactions_for_doc(doc_id, doc_txns)
```

3. **DB Cleanup** - After fix, dedupe existing data:
```sql
-- Remove duplicates, keep lowest ID per unique transaction
DELETE FROM transactions WHERE id NOT IN (
    SELECT MIN(id) FROM transactions 
    GROUP BY doc_id, date, merchant, amount
);
```

**Files**: `home-ai/soa1/batch_processor.py`, `home-ai/soa1/agent.py`
**Priority**: CRITICAL - blocks accurate reporting
