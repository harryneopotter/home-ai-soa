### January 9, 2026 - M2 Memory v0 Complete (Session 42 Continued)

#### Goal
Complete M2 (Memory v0) implementation — typed, auditable memory system with propose/commit pattern.

#### M2 Implementation ✅
Created `soa1/memory/` package with:
- `__init__.py` - Package exports (MemoryClient, MemoryManager, SessionMemory)
- `client.py` - Moved from `memory.py` (MemoryClient for MemLayer backend)
- `memory_manager.py` - Kernel-controlled memory with propose/commit pattern
- `session_memory.py` - Ephemeral session state dataclass

#### Three Memory Types (Do Not Mix)
1. **BOOT_CONTEXT** - Read-only, injected via prompts (identity, role, consent rules)
2. **SESSION** - Ephemeral, stored in-memory dict (batch_id, pipeline stage, running summary)
3. **USER_PROFILE** - Durable, requires backend (preferences, confirmed rules)

#### Key Pattern: Propose/Commit
- Agents call `propose_write(key, value, memory_type, reason)` - creates pending proposal
- Kernel calls `commit_write(key)` or `reject_write(key, reason)` - finalizes or discards
- Uncommitted proposals NOT visible via `query()` - prevents agent self-reinforcement
- Full audit log of all proposals and decisions

#### Integration in agent.py
```python
from memory import MemoryClient
from memory.memory_manager import MemoryManager, MemoryType
from memory.session_memory import SessionMemory

# In __init__:
backend = self.memory if self._memory_available else None
self.memory_manager = MemoryManager(backend=backend)
self._sessions: dict[str, SessionMemory] = {}

# New methods:
def get_session(self, session_id: str) -> SessionMemory
def clear_session(self, session_id: str) -> None
```

#### Files Created
- `home-ai/soa1/memory/__init__.py`
- `home-ai/soa1/memory/client.py` (moved from `memory.py`)
- `home-ai/soa1/memory/memory_manager.py`
- `home-ai/soa1/memory/session_memory.py`
- `home-ai/soa1/tests/test_memory.py` (11 unit tests)

#### Files Modified
- `home-ai/soa1/agent.py` - Import new memory module, add MemoryManager + session helpers
- `RemAssist/NEXT_TASKS.md` - Marked M2 complete

#### Test Results
- 11/11 tests passing for memory isolation
- SOA1 service starts successfully
- Upload flow verified at ~15s latency

#### Commit
- `8d3dc7c` feat(M2): implement Memory v0 with typed propose/commit pattern

---

### January 8, 2026 - M0 Implementation Complete (Session 42)

#### Goal
Implement Modular Orchestrator Pre-requisites (M0) — capability-based consent and CONTROL header system.

#### M0.2: Consent Policy Update ✅
- Updated `IMPLEMENTATION_GUIDE.md` with capability-based consent model (6 capabilities)
- Upload now grants `READ_UPLOADS` and `ANALYZE_DETERMINISTIC` implicitly
- No consent prompts for read-only analysis
- Updated `orchestrator.py` with `Capability` enum and implicit grant on upload

#### M0.3: Capability Enum ✅
Implemented 6 capabilities in `orchestrator.py`:
- `READ_UPLOADS` (implicit on upload)
- `ANALYZE_DETERMINISTIC` (implicit on upload)
- `WRITE_PERSISTENT` (explicit consent required)
- `CREATE_RULES` (explicit consent required)
- `DEVICE_CONTROL` (explicit consent required)
- `EXTERNAL_API` (explicit consent required)

#### M0.1: CONTROL Header System ✅
Created `soa1/control_header.py` with:
- `PipelineStage` enum: UPLOADING, PDF_PARSE, NORMALIZE, AGGREGATE, READY, ANALYZING, COMPLETE, FAILED
- `DataKind`, `AllowedAction`, `ForbiddenAction`, `ExpectedNext` enums
- `ControlHeaderContext` dataclass
- `build_control_header()` function generating structured blocks
- `status_to_stage()` and `data_kind_for_stage()` helpers

Updated `agent.py`:
- `_format_document_context()` now generates CONTROL + DATA blocks instead of prose

Updated `orchestrator.md`:
- Documented CONTROL header format and stage behavior rules
- Added "Reading the CONTROL Block" instructions

#### CONTROL Header Enforcement ✅
Added `ControlHeaderEnforcer` class in `orchestrator.py`:
- `assert_can_invoke_specialist()` → hard fail if stage != READY or not in allowed_actions
- `assert_can_write_db()` → hard fail + audit log if write_db forbidden
- `warn_expected_next()` → warning (non-fatal) on violation

**Critical Invariant**: `invoke_specialist` ONLY allowed when `stage=READY`
- Enforced in `STAGE_ALLOWED_ACTIONS` mapping
- Runtime assertion in `build_control_header()`
- Documented in `orchestrator.md`

Audit logging to `logs/control_violations.jsonl` with:
- timestamp, stage, action, reason, fatal flag
- allowed_actions and forbidden_actions snapshot

#### Documentation Updates
- `IMPLEMENTATION_GUIDE.md` Section 15.1-15.2: CONTROL header enforcement + "No UX Exceptions" rule
- `AGENTS.md`: Added "Do NOT relax enforcement for UX smoothness" to Hard Rules
- `NEXT_TASKS.md`: Marked M0.1, M0.2, M0.3 complete with full details

#### Files Created
- `home-ai/soa1/control_header.py` (~230 lines)

#### Files Modified
- `home-ai/soa1/orchestrator.py` - Capability enum, ControlHeaderEnforcer
- `home-ai/soa1/agent.py` - CONTROL header integration
- `home-ai/soa1/prompts/orchestrator.md` - CONTROL header docs
- `RemAssist/IMPLEMENTATION_GUIDE.md` - Enforcement rules
- `RemAssist/NEXT_TASKS.md` - M0 tasks marked complete
- `AGENTS.md` - Added enforcement rule

#### Tests Performed
- CONTROL header generation verified
- `invoke_specialist` invariant verified across all stages
- `ControlHeaderEnforcer` assertions tested (4 test cases)
- Audit log entries verified

---

### January 8, 2026 - Modular Orchestrator Planning (Session 41 Continuation)

#### Goal
Design a modular orchestrator architecture so adding new domain specialists (health, scheduling, home automation) requires minimal/zero code changes to the core orchestrator.

#### Research Completed
- **Explore Agent**: Inventoried all orchestrator-related files and finance couplings
- **Librarian Agent**: Researched LangChain, Semantic Kernel, OpenAI function calling, Auto-GPT patterns

#### Design Pinning Questions Resolved
Answered 6 critical design questions to lock architectural decisions:

| Question | Answer |
|----------|--------|
| 1. Entry point | `SOA1Agent.ask()` in `agent.py` - **LOCKED** |
| 2. memory.py | Live, trusted, wrap don't replace - **LOCKED** |
| 3. Consent source of truth | New `ConsentManager` (DB-backed) - **DECIDED** |
| 4. Session boundary | `X-Session-ID` header (or IP fallback) - **LOCKED** |
| 5. Specialists vs helpers | Only phinance is real; others are stubs - **LOCKED** |
| 6. Implicit memory | OK via chat_history (20 turns), no hidden state - **AGREED** |

#### Ollama KV Cache Quantization
Confirmed `OLLAMA_KV_CACHE_TYPE=q8_0` already configured in systemd service.
- ~30-40% VRAM savings on KV cache
- Updated HARDWARE_SPECS.md with documentation

#### SOA Kernel Alignment Review
Reviewed `/projects/soa_kernel_alignment_memory_consent_and_agent_awareness.md` for alignment:

**Aligned:**
- Single user-facing agent (Chat Agent)
- Kernel as router + state machine
- Capability-based consent model
- Memory v0 interface design
- Deferred features (no graph memory yet)

**Gaps Identified:**
- CONTROL Header system not implemented (prose instructions instead)
- Upload should imply READ_UPLOADS consent (currently asks)
- Memory concepts mixed (Boot Context vs Session vs User Profile)
- Capability enum needs expansion (6 capabilities, not 4)

#### Documents Created/Updated
- **`RemAssist/MODULAR_ORCHESTRATOR_PLAN.md`** - Complete implementation plan
- **`RemAssist/HARDWARE_SPECS.md`** - Added KV cache quantization docs
- **`RemAssist/NEXT_TASKS.md`** - Added M1 tasks + alignment tasks

---

### January 6, 2026 - Stability Fixes + Phinance Context Window (Session 41)

#### Stability Tasks Completed
- **S3: Zombie Task Auto-Timeout** - Added 10-min timeout in `batch_processor.py` for tasks stuck in "parsing"
- **S4: Frontend Polling Timeout** - Added 300-attempt limit (~10 min) in `index.html` for both batch status and analysis polling

#### Phinance Context Window Optimization
- **Changed `num_ctx` from 32768 → 4096** in `models.py`
- **Analysis**: Prompt sends aggregated summaries (~550 tokens), not raw transactions
- **Typical usage**: ~1000 tokens total (system ~133 + user ~550 + response ~300)
- **Headroom**: 3000+ tokens (75% unused) - 4K is more than sufficient
- **Impact**: Reduces VRAM waste, 32K was massive overkill
- **Documentation**: Added "DO NOT CHANGE" warnings in AGENTS.md, HARDWARE_SPECS.md, SERVICES_CONFIG.md, ARCHITECTURE.md

#### Commits
- `3d8c3e1` feat: stability improvements + multi-session fixes (S37-S41)
- `64b55bd` feat: add PDF validation and LLM critic utilities
- `2c2dad5` docs: add implementation guides and analysis docs
- `1f0cde1` chore: update .gitignore for temp analysis/debug files

---

### January 6, 2026 - LLM-Assisted Merchant Categorization (Session 40)

#### Feature Implemented
Implemented Phase 2 from `LLM_MERCHANT_CATEGORIZATION.md` - Phinance-assisted categorization for unknown merchants.

#### Changes Made

**1. `models.py` - Added LLM categorization function**
- `categorize_merchants_llm(merchants)` - Batch categorizes merchants via Phinance
- `VALID_CATEGORIES` list - 20 categories matching Title Case standard
- `CATEGORIZATION_SYSTEM_PROMPT` - Optimized prompt for categorization
- Category alias mapping for common LLM variations (e.g., "Dining" → "Food & Dining")

**2. `storage.py` - Added batch cache functions**
- `get_merchant_mappings_batch(raw_names)` - Batch lookup by raw name
- `upsert_merchant_mappings_batch(mappings)` - Batch insert with stable_id generation

**3. `batch_processor.py` - Integrated LLM categorization**
- `USE_LLM_CATEGORIZATION` feature flag (DISABLED until Phase 3)
- `_llm_categorize_unknown_merchants(transactions)` - Pipeline function
- Called after regex extraction, before financial calculation
- Flow: Check cache → Call LLM for uncached → Save to cache → Update transactions

#### Pipeline Flow
```
Regex categorization → Collect "Other" merchants → Cache lookup
    ↓
Uncached merchants → Phinance LLM categorization → Cache results
    ↓
Update transaction categories → Calculate financials
```

#### Test Results
- LLM correctly categorized: WHATABURGER → Food & Dining, SHELL → Gas, NETFLIX → Entertainment
- Cache hit verified: Second run found 3/3 merchants in cache, no LLM call
- Results stored in `merchant_mappings` table with `source='phinance'`

#### Feature Disabled
- `USE_LLM_CATEGORIZATION = False` - Disabled until Phase 3 (chat-based correction)
- Reason: Without correction mechanism, LLM errors accumulate in cache with no way to fix
- Re-enable after Phase 3 implementation

#### Stability Tasks Added to NEXT_TASKS.md
Consolidated 10 tasks from `MASTER_ISSUES_AND_FIXES.md`:
- S1-S3: High priority (persistence hardening, async HTTP, zombie timeout)
- S4-S5: Medium priority (frontend polling, double-submit prevention)
- S6-S10: Low priority (imports, merchant service, logging, refactoring, Docker)

---

### January 5, 2026 - Merchant System Planning (Session 33)

#### Issues Identified

**1. Transaction Duplication Bug (CRITICAL)**
- All transactions being saved to ALL doc_ids instead of their source doc_id
- Result: 9096 transactions in DB when should be ~1500-1800 (5-6x bloat)
- Root cause: `agent.py` line 282 - `doc_txns = [t for t in all_transactions]` copies all, doesn't filter

**2. "Other" Category Overuse**
- 412 unique merchants in "Other" category
- 6306 transactions affected (65%+ of total)
- Python regex/keyword matching only covers major brands

#### Documents Created

| Document | Purpose |
|----------|---------|
| `LLM_MERCHANT_CATEGORIZATION.md` | Plan for Phinance-assisted categorization |
| `MERCHANT_SYSTEM_IMPLEMENTATION_GUIDE.md` | Complete 3-phase implementation guide (684 lines) |
| `NEXT_TASKS.md` | Updated with Tasks 0.5 and 0.6 |

#### Implementation Guide Overview

**Phase 1: Transaction Duplication Fix**
- Extract transactions per-document, tag with `doc_id`
- Filter by `doc_id` when saving
- DB cleanup script to dedupe existing data

**Phase 2: LLM-Assisted Categorization**
- Phinance warming on first finance doc detection
- Batch unknown merchants through Phinance
- Cache results in `merchant_mappings` table
- Flag "other" results for future review

**Phase 2.5: Backfill Existing "Other" Merchants**
- One-time script to categorize 412 existing merchants
- Target: <15% in "Other" after backfill

**Phase 3: Chat-Based Correction**
- `find_merchant_candidates()` - fuzzy search
- `update_merchant_category()` - with audit logging
- `undo_last_mapping_change()` - revert support
- Tool registration for agent function calling

#### Key Stats
- Current "Other": 6306 transactions, 412 unique merchants
- Target "Other": <15% of transactions
- DB bloat: 9096 rows → ~1500-1800 after dedup

#### No Code Changes This Session
Planning and documentation only. Implementation in next session.

---

### January 4, 2026 - Merchant Stable IDs & Normalization Fix (Session 32)

#### Problem Solved
1. **Merchant names in PDF export were raw** (e.g., "AMZN MKTP US*ABC123" instead of "Amazon")
2. **No stable linkage for future graph memory** - dictionary changes would break historical links

#### Root Cause
- `normalize_transactions()` was called AFTER `save_transactions_for_doc()` in agent.py
- Transactions saved to DB had raw merchant names
- No stable identifier existed for merchants across dictionary versions

#### Solution Implemented

**Fix 1: Normalization Order**
- Moved `normalize_transactions()` call BEFORE `save_transactions_for_doc()` in agent.py
- Fixed `storage.py` to properly save `merchant` (normalized) vs `raw_merchant` (original)

**Fix 2: Stable IDs (per security-cleanup-feedback.md)**
- Added `compute_merchant_stable_id()` - sha256 hash of canonicalized merchant name
- Added `MERCHANT_DICT_VERSION = "1.0.0"` for tracking dictionary changes
- Normalizer now returns 4-tuple: `(name, category, confidence, stable_id)`
- `normalize_transactions()` adds `merchant_stable_id` and `merchant_dict_version` to each transaction
- DB schema updated with `merchant_stable_id` column + migration

#### Key Design Decision
Following feedback from `security-cleanup-feedback.md`:
- **Display names can change** as dictionary improves
- **Stable IDs never change** - sha256(canonical_name) remains constant
- Future graph memory nodes keyed by stable IDs won't break when display names update

#### Files Modified
| File | Change |
|------|--------|
| `home-ai/soa1/agent.py` | Moved normalize before save, removed hardcoded responses |
| `home-ai/finance-agent/src/storage.py` | Fixed raw_merchant saving, added merchant_stable_id column |
| `home-ai/soa1/utils/merchant_normalizer.py` | Added stable ID computation, dict version tracking |

#### Commits
- `147a5b3` - fix: normalize merchants before DB save, remove hardcoded responses
- `fc66b7f` - feat: add merchant_stable_id for graph-safe linkage

---

### January 4, 2026 - PDF Export Feature (Session 31)

#### Feature Added
Complete PDF export pipeline - user clicks "📄 PDF Export" button, agent returns download URL, frontend triggers file download.

#### Implementation

| Component | File | Change |
|-----------|------|--------|
| PDF Endpoint | `soa-webui/main.py` | Added `GET /export/pdf/{batch_id}` - queries SQLite, renders template, WeasyPrint converts to PDF |
| PDF Template | `soa-webui/templates/pdf_report.html` | A4 print-optimized layout with metrics cards, category bars, top merchants, transaction table |
| Agent | `home-ai/soa1/agent.py` | Returns `download_url: "/export/pdf/{batch_id}"` when PDF format selected |
| API Model | `home-ai/soa1/api.py` | Added `download_url` field to `ChatResponse` model |
| API Streaming | `home-ai/soa1/api.py` | Pass `download_url` through in streaming `done` payload |
| Frontend | `soa-webui/templates/index.html` | Handle `download_url` - create anchor element, trigger click for download |

#### Flow
```
User clicks "📄 PDF Export" → sends "pdf export" message
    ↓
Agent detects PDF format intent, finds active batch
    ↓
Returns: {"answer": "Generating your PDF...", "download_url": "/export/pdf/batch-xxx"}
    ↓
API streaming passes download_url in done payload
    ↓
Frontend receives download_url, creates <a> element, triggers click
    ↓
Browser downloads PDF via /export/pdf/{batch_id}
    ↓
WeasyPrint renders pdf_report.html → PDF (22KB typical)
```

#### PDF Report Contents
- **Header**: Title, subtitle, date range
- **Metrics Cards**: Total spending, transaction count, categories, merchants
- **Spending by Category**: Horizontal bar chart with percentages
- **Top Merchants**: 2-column grid with amounts
- **Transaction Details**: Table with last 50 transactions (date, merchant, category, amount)
- **Footer**: Batch ID, generation timestamp

#### Dependencies
- WeasyPrint (`pip install weasyprint`) - HTML to PDF conversion
- Already installed on system

---

### January 4, 2026 - Self-Spawning Phinance Analysis (Session 30)

#### Problem Solved
When using the `/api/chat/stream` endpoint, phinance analysis never started because the streaming endpoint was missing the `trigger_phinance_background` handler. The agent returned the trigger signal, but the API endpoint didn't act on it.

#### Root Cause
The architecture required API endpoints to cooperate by checking for `trigger_phinance_background` in the agent response and spawning background tasks. When we added `/api/chat/stream`, we forgot to add this handler, causing analysis to get stuck at "analyzing" status.

#### Solution: Self-Contained Agent
Made the agent "system aware" - it now spawns its own background thread for phinance analysis instead of returning a trigger signal for the API to handle.

**Before**: Agent returns `{"trigger_phinance_background": batch_id}` → API must spawn task
**After**: Agent calls `self._spawn_phinance_background()` directly → No API cooperation needed

#### Key Changes

| File | Change |
|------|--------|
| `soa1/agent.py` | Added `threading` import |
| `soa1/agent.py` | Added `_spawn_phinance_background()` method - spawns daemon thread for analysis |
| `soa1/agent.py` | Removed `trigger_phinance_background` from return dict, calls spawn method instead |
| `soa1/batch_processor.py` | Added `pre_generate_outputs_sync()` - sync wrapper for use in threads |
| `soa1/api.py` | Removed `_run_phinance_background()` async function (no longer needed) |
| `soa1/api.py` | Removed `trigger_phinance_background` handlers from `/api/chat` and `/api/chat/stream` |

#### Benefits
- Works regardless of which endpoint calls `agent.ask()`
- No duplicate handler code needed in multiple endpoints
- Agent is self-contained and "system aware"
- Simpler mental model - agent handles its own background work

#### Error Handling
All existing protections remain in place:
- Phinance model calls have 3x retry with exponential backoff
- JSON parsing has fallback defaults
- Background thread catches all exceptions, sets `state.status = "failed"` on error
- Output pre-generation failure is caught and logged (non-fatal)

---

### January 4, 2026 - Action Buttons for Analysis Consent (Session 30 continued)

#### Feature Added
After document upload, the agent now returns action buttons for the user to select:
- **"Run Detailed Analysis"** - Triggers phinance analysis
- **"Ask Something Else"** - Lets user ask a different question

#### Implementation

| File | Change |
|------|--------|
| `soa1/api.py` | Added `actions` field to `ChatResponse` model |
| `soa1/api.py` | Upload endpoint returns `actions` from agent result |
| `soa1/agent.py` | Returns `actions` array when batch is in "ready" state with extracted transactions |
| `soa-webui/templates/index.html` | `appendMessage()` now accepts optional `actions` parameter |
| `soa-webui/templates/index.html` | Renders buttons with `brutal-btn` styling, click sends action value as message |

#### Flow
```
User uploads PDFs
    ↓
Parser extracts transactions (background)
    ↓
Agent response includes actions: [
    {"label": "Run Detailed Analysis", "value": "yes, run detailed analysis"},
    {"label": "Ask Something Else", "value": "I have a different question"}
]
    ↓
Frontend renders buttons below message
    ↓
User clicks button → value sent as chat message → triggers analysis
```

---

### January 3, 2026 - Progressive Flow Phase Separation (Session 29)

#### Problem Solved
Phases 2 & 3 were collapsed - when user said "yes, analyze", they received the ENTIRE analysis immediately instead of progressive engagement.

#### Root Cause
In `agent.py` line ~574, `_invoke_phinance()` ran **synchronously** and returned full result immediately. No separation between consent acknowledgment and analysis completion.

#### Solution Implemented: Async Phase Separation
- **Phase 2 (Consent)**: Returns `interesting_findings` immediately with engagement message
- **Background**: Phinance analysis runs asynchronously via `asyncio.create_task()`
- **Phase 3 (Complete)**: Frontend polls `/api/batch/status/{batch_id}` for completion

#### Key Changes

| File | Change |
|------|--------|
| `soa1/agent.py` | When `[INVOKE:phinance]` detected with `status="ready"`, return immediately with findings and signal `trigger_phinance_background` |
| `soa1/api.py` | Added `_run_phinance_background()` async function, triggered by chat endpoint |
| `soa1/api.py` | Enhanced `/api/batch/status/{batch_id}` to include `analysis_summary` and `completion_message` when `status="complete"` |

#### Duplicate Output Prompt Fixed
Removed duplicate "How would you like the report?" section from `_run_hybrid_analysis()` - kept only the one in `_format_analysis_response()`.

#### New Flow
```
User: "yes, analyze"
    ↓
API: Calls agent.ask()
    ↓
Agent: Detects [INVOKE:phinance], returns immediately:
    "Starting analysis! While I work, here's what I noticed:
     • Total spending: $33,455.07 across 266 transactions
     • Highest category: Shopping at $X..."
    + trigger_phinance_background = batch_id
    ↓
API: Starts asyncio task _run_phinance_background()
    Returns response to user immediately
    ↓
Background: _invoke_phinance() runs (5-10s)
    Sets state.status = "complete"
    Triggers output pre-generation
    ↓
Frontend: Polls /api/batch/status/{batch_id}
    Detects status="complete"
    Shows completion_message with format options
```

#### Files Modified
- `home-ai/soa1/agent.py` - Phase separation in `ask()` method
- `home-ai/soa1/api.py` - Background phinance task, enhanced status endpoint

---

### January 3, 2026 - Refined Agent Flow & Instant Delivery (Session 27)

#### Improvements Implemented
- **True Orchestration**: Refined the agent's acknowledgment logic to use a system directive instead of a hardcoded query. The LLM now analyzes injected document metadata to generate specific, engaging responses.
- **Situational Awareness**: Updated `_format_document_context` to include the `BatchState` (status, transaction count, preliminary findings). The orchestrator is now aware of the pipeline's progress and results.
- **Progressive Flow Implementation**: Restructured the upload process to perform a quick metadata scan (~500ms) for immediate response, deferring full parsing and PII redaction to a background task.
- **Instant Delivery Architecture**: Consolidated the output schema to a flat JSON format and implemented pre-generation of Dashboard JSON, PDF Commands, and Infographic Prompts immediately after Specialist completion.
- **Dashboard Consolidation**: Standardized on `soa_dashboard.html` as the primary UI, with dynamic data fetching for both individual documents and full batches.
- **Apple Card Multiline Regex**: Updated `APPLE_CARD_REGEX` in `batch_processor.py` to support the multi-line format (Date, Merchant, Cashback, Amount) found in extracted text, fixing the zero transaction extraction bug.
- **UI Contrast Improvements**: Improved contrast for better readability on the dark background across the chat interface and status bar.

#### Files Modified
- **`home-ai/soa1/pdf_processor.py`**: Added `inferred_type` to `process_uploaded_pdf` and updated response fields.
- **`home-ai/soa1/api.py`**: Refactored `/upload-batch` for progressive response, fixed syntax error in `/api/output`, and updated output retrieval logic.
- **`home-ai/soa1/batch_processor.py`**: Updated `APPLE_CARD_REGEX` for multiline support, refactored `background_analyze` to `background_full_process` and standardized `outputs` dictionary using `pdf_command`.
- **`home-ai/soa1/agent.py`**: Refactored `_format_document_context` and `_run_hybrid_analysis` for better situational awareness and engagement.
- **`home-ai/soa1/output_generator.py`**: Refined output generation logic and flattened JSON schema.
- **`soa-webui/main.py`**: Added `/api/proxy/output` endpoint and refined dashboard routing (disabled consolidated view).
- **`soa-webui/templates/index.html`**: Improved UI contrast.
- **`soa-webui/templates/soa_dashboard.html`**: Implemented dynamic data source logic.

---

### January 3, 2026 - Two-Tier Memory Architecture Design (Session 26)

#### 🧠 Memory System Redesign: Mem0 + LightRAG

**Problem**: Current MemLayer is limited - needs better conversation memory, entity tracking, and document analysis capabilities for household use cases.

**Decision**: Implement two-tier memory architecture:

| Tier | System | Purpose | Response Time |
|------|--------|---------|---------------|
| **Warm Memory** | Mem0 (Kuzu + ChromaDB) | Conversation memory, entity tracking, family knowledge, schedules | <100ms |
| **Cold/Document Memory** | LightRAG (NetworkX + vector) | PDF analysis, document RAG, historical queries | 1-3s |

#### Coverage Analysis

**Mem0 handles (95% of queries):**
- Entity lookups ("When is Jake's exam?")
- Relationship queries ("What subjects does Emma struggle with?")
- Recent context, reminders, pattern recognition
- Schedule queries, pet care tracking

**LightRAG handles (5% of queries):**
- Document analysis ("What did the vet report say?")
- PDF extraction ("Jake's course syllabi")
- Historical documents, financial comparisons

#### Implementation Plan (3 weeks)
- **Week 1**: Mem0 setup - Kuzu + ChromaDB + Ollama, replace MemLayer
- **Week 2**: LightRAG setup - document ingestion, query router
- **Week 3**: Integration - nightly sync, entity linking, testing

#### Architecture Diagram
```
┌─────────────────────────────────────────────────────────────────┐
│  User Query → SOA1 Orchestrator (NemoAgent)                     │
│                        │                                         │
│         ┌──────────────┴──────────────┐                         │
│         ↓                             ↓                         │
│  ┌─────────────────┐       ┌─────────────────────┐              │
│  │     MEM0        │       │      LIGHTRAG       │              │
│  │ (Conversation)  │       │    (Documents)      │              │
│  │                 │       │                     │              │
│  │ • Kuzu Graph    │       │ • NetworkX Graph    │              │
│  │ • ChromaDB      │       │ • Vector Store      │              │
│  │ • Fast lookups  │       │ • PDF/Doc Store     │              │
│  └─────────────────┘       └─────────────────────┘              │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │             NIGHTLY SYNC (Background Job)                │    │
│  │  • Promote Mem0 facts → persistent storage              │    │
│  │  • Ingest new documents → LightRAG                      │    │
│  │  • Cross-link entities between systems                  │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

#### Key Benefits
- **100% household scenario coverage** with no compromises
- **Ollama-native** - both systems support local LLM
- **Clear separation** - conversation vs document queries
- **Scalable** - can add more tiers later (scheduler, budgeting)

## 2026-01-05 - Finance Benchmarking Suite
- Created `fin-benchmark/` directory.
- Captured 3 sets of real-world financial stats for benchmarking.
- Implemented `benchmark_models.sh` for automated A/B testing of Ollama models with optimized parameters (temp 0.2, ctx 4096).

---

## 📅 Recovered Sessions (2-17) from pre_shrink_versions/History_d4730b69.md

---

### January 1, 2026 - Progressive Batch Architecture Implementation (Session 17)

#### 🛠️ Implementation
- **Security Layer:**
    - Created `soa1/security/pii_redactor.py`: Implements regex-based PII detection and redaction (Credit Cards, Bank Accounts, SSN, etc.).
    - Created `soa1/security/encrypted_storage.py`: Implements AES-256-GCM encryption for sensitive data storage.
    - **Integrated Security Layer** into `home_ai/soa1/pdf_processor.py`: Raw text is now redacted immediately after extraction and encrypted before being returned in the result dictionary.
- **Batch Processing:**
    - Created `home_ai/soa1/batch_processor.py`: Implements `BatchState` dataclass and `BatchProcessor` for managing multi-file upload states.
- **Output Generation:**
    - Created `home_ai/soa1/output_generator.py`: Implements `OutputGenerator` for pre-generating dashboard JSON, PDF prompts, and infographic prompts.
- **API Updates:**
    - Modified `home_ai/soa1/api.py`:
        - Added `POST /upload-batch` endpoint for multi-file uploads with LLM-driven response.
        - Added `GET /api/output/{batch_id}/{format}` endpoint for retrieving pre-generated outputs.
        - Integrated `batch_processor` and `output_generator`.

#### 📝 Files Created/Modified
- `soa1/security/pii_redactor.py` - NEW
- `soa1/security/encrypted_storage.py` - NEW
- `home_ai/soa1/pdf_processor.py` - Integrated PII redaction and encryption
- `home_ai/soa1/batch_processor.py` - NEW
- `home_ai/soa1/output_generator.py` - NEW
- `home_ai/soa1/api.py` - Added batch upload and output endpoints

#### ✅ Verified
- `pii_redactor.py` unit test: Successfully redacted credit cards, bank accounts, SSNs, emails, and phones.
- `encrypted_storage.py` unit test: Successfully encrypted and decrypted sensitive strings.
- `pdf_processor.py` integration: Verified imports and initialization with security layer.
- `api.py` syntax: Verified with basic checks.

---

### January 1, 2026 - Documentation & Architecture Capture (Session 16)

#### 📄 Documentation Created
- **New Document:** `RemAssist/PROGRESSIVE_BATCH_ARCHITECTURE.md` — Complete 5-phase progressive batch upload pipeline with security layer (PII redaction, AES-256 encryption), captured from Session 15 discussion

#### 🛠️ Documentation Updates
- **Fixed `RemAssist/NEXT_TASKS.md`**: Removed contradictory "Known Issue" line (was showing issue as both fixed and unfixed)
- **Added Progressive Batch Architecture tasks** to NEXT_TASKS.md with proper priority ordering
- **Updated `home-ai/ARCHITECTURE.md`**: Updated status section from December 2025 to January 2026, added references to new architecture doc
- **Updated `AGENTS.md`**: Added Architecture Reference Documents section pointing to PROGRESSIVE_BATCH_ARCHITECTURE.md

#### 📝 Files Modified
- `RemAssist/PROGRESSIVE_BATCH_ARCHITECTURE.md` - NEW comprehensive architecture document
- `RemAssist/NEXT_TASKS.md` - Fixed contradiction, added batch architecture tasks
- `RemAssist/History.md` - Session 16 entry
- `home-ai/ARCHITECTURE.md` - Updated status section
- `AGENTS.md` - Added architecture reference section

---

### January 1, 2026 - Upload Response Architecture Fix (Session 15)

#### 📄 Documentation Created
- **New Document:** `RemAssist/LLM_DRIVEN_RESPONSES.md` — Comprehensive explanation of the LLM-driven response principle, the bug chain, fix implementation plan, and verification checklist

#### 🐛 Problem Identified
- **Issue**: Upload response returning hardcoded "Analysis ready." instead of LLM-generated contextual response
- **Root Cause**: When `consent_request` was removed from API response (Session 14 fix), frontend fell back to hardcoded string in `index.html` line 287

#### 🏗️ Architectural Decision
**Route upload response through LLM instead of hardcoded frontend strings.**

**Rationale:**
- Single round trip (lower latency)
- Frontend stays dumb, backend handles orchestration
- Document context already available in API
- Works automatically for future clients (mobile, CLI)
- Atomic operation (upload + response)

#### 🛠️ Implementation Completed
1. **Modified `/upload-pdf`** in `home-ai/soa1/api.py`:
   - After successful upload, calls `SOA1Agent.ask()` with document context
   - Includes filename, pages, size, detected type, preview text
   - Returns `agent_response` field with LLM-generated text
   
2. **Updated frontend** in `soa-webui/templates/index.html`:
   - Changed line 287 to use `data.agent_response || \`Received: \${file.name}\``
   - Removed hardcoded "Analysis ready." fallback

#### ✅ Verified Result
```json
{
  "status": "UPLOADED",
  "doc_id": "finance-20260101-195110-e96226",
  "filename": "Apple Card Statement - April 2025.pdf",
  "pages": 6,
  "agent_response": "I've received **Apple Card Statement - April 2025.pdf**.\n\nFrom the first page, I can see:\n- A minimum payment of **$25.00**...\n\nYou can:\n• Ask me a specific question about this statement\n• Get a quick summary...\n\nNothing happens unless you say so."
}
```

#### 📝 Files Modified
- `home-ai/soa1/api.py` - Added agent call after upload with document context
- `soa-webui/templates/index.html` - Display agent_response directly
- `RemAssist/LLM_DRIVEN_RESPONSES.md` - NEW architectural document
- `AGENTS.md` - Added LLM-Driven Responses as constitutional document
- `home-ai/ARCHITECTURE.md` - Added 6th design principle

#### 📚 Reference
See `RemAssist/LLM_DRIVEN_RESPONSES.md` for full architectural explanation.

---

### January 1, 2026 - MVP Demo UI Enhancements (Session 14)

#### 🎯 Cross-Document Comparison UI
- **File Modified:** `soa-webui/templates/consolidated_dashboard.html`
  - Added checkboxes to Documents page for selecting docs to compare
  - Added "Select All" / "Clear" / "Compare Selected (N)" buttons
  - New comparison section showing side-by-side totals, category breakdown with diff column, shared merchants
  - Leverages existing `/api/reports/compare` endpoint
  - Smooth scroll to comparison results

#### 🏷️ Merchant Normalization in Dashboard
- **File Modified:** `soa-webui/reports.py`
  - Integrated `normalize_transactions()` into `/api/reports/consolidated`
  - Transactions now show clean merchant names (Amazon vs AMZN*MKTP)
  - Raw merchant name preserved in `merchant_raw` field
  - Added `_aggregate_merchants()` helper function
  - Graceful degradation with `MERCHANT_NORMALIZER_AVAILABLE` flag

#### 🎨 Chat UI Contrast Fixes
- **File Modified:** `soa-webui/templates/index.html`
  - Fixed disabled button contrast: `color: #333` → `#666`, `border-color: #333` → `#555`
  - Fixed upload area border: `border-gray-800` → `border-gray-600`
  - Fixed add icon visibility: `text-gray-800` → `text-gray-500`
  - Fixed "DROP PDFs OR CLICK" text: `text-gray-500` → `text-gray-400`
  - Fixed notice text opacity: `opacity-30` → `opacity-50`

#### 📤 Multi-File PDF Upload
- **File Modified:** `soa-webui/templates/index.html`
  - Added `multiple` attribute to file input
  - Shows "N files selected" when multiple files chosen
  - Sequential upload with progress indicator ("UPLOADING 2/5: filename.pdf...")
  - Final summary shows success/failure counts
  - Button text changes to "PROCESS FILES" for multiple selections

---

### December 31, 2025 - Chat History, Cross-Doc Compare, Merchant Normalization (Session 13)

#### 💬 Chat History Persistence
- **File Modified:** `home-ai/finance-agent/src/storage.py`
  - Added `chat_history` table schema in `init_db()`
  - Functions: `save_chat_message()`, `get_chat_history()`, `clear_chat_history()`, `get_recent_sessions()`
- **File Modified:** `home-ai/soa1/api.py`
  - Import `chat_storage` module with `CHAT_STORAGE_AVAILABLE` flag
  - `/api/chat` endpoint now saves user/assistant messages and loads history
- **File Modified:** `home-ai/soa1/agent.py`
  - `ask()` method now accepts `chat_history: Optional[List[Dict[str, str]]]` parameter
  - Prepends chat history to conversation for multi-turn context

#### 📊 Cross-Document Comparison
- **File Modified:** `soa-webui/reports.py`
  - New endpoint: `POST /api/reports/compare` - compare spending across 2-10 documents
    - Returns: totals comparison, category breakdown per doc, top merchants, shared merchants
  - New endpoint: `GET /api/reports/compare/{doc_id1}/{doc_id2}` - convenience GET for 2-doc compare

#### 🏷️ Merchant Normalization Utility
- **File Created:** `home-ai/soa1/utils/merchant_normalizer.py`
  - 40+ regex patterns for common merchants (Amazon, Uber, Starbucks, Netflix, etc.)
  - `normalize_merchant(raw_name)` → (normalized_name, category, confidence)
  - `normalize_transactions(tx_list)` - normalizes merchant names in place
  - `get_merchant_stats(tx_list)` - reports normalization statistics
  - Categories inferred: Shopping, Food & Dining, Transportation, Entertainment, Groceries, Gas, Health, etc.
- **File Modified:** `home-ai/soa1/utils/__init__.py`
  - Added exports for `normalize_merchant`, `normalize_transactions`, `get_merchant_stats`, `MERCHANT_PATTERNS`

#### 🧪 Keep-Alive Integration Test
- **File Created:** `test_scripts/test_ollama_keepalive_integration.py`
  - Tests `ollama ps` shows "Forever" for loaded models
  - Verifies NemoAgent and phinance-json are pinned with `keep_alive: -1`

---

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
- **Batch Test Results**
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

### January 6, 2026 (Session 35)

#### Accomplishments
- **Phinance JSON Output Fix**: Resolved critical JSON parsing issues by aligning the prompt schema and significantly improving the `repair_json()` function in `llm_validation.py`. Achieved 10/10 JSON parse success rate in testing.
- **E2E Test Runs**: Successfully ran two E2E analysis tests (4 documents each) on Apple Card PDFs, confirming the stability of the core pipeline (upload, extraction, analysis completion).
- **Instrumented Test**: Performed a detailed, instrumented E2E run, measuring step-by-step timing (Total time: ~15.12s).

#### Failures and New Issues
- **Analysis Persistence Failure (CRITICAL)**: Discovered that the `phinance_analysis` JSON is not being persisted to the `batches` table upon job completion, blocking final report generation.
- **LLM Logging Failure**: The expected LLM interaction logging API endpoint (`/api/log/analysis/{doc_id}`) returned a 404 error.
- **Merchant Categorization Timeout**: The background task delegated to the Oracle agent for categorizing "Other" merchants timed out and was cancelled.

#### Next Priority
- **CRITICAL**: Fix Analysis Persistence and Logging (Task 0.7 in `NEXT_TASKS.md`).
- Re-attempt Merchant Categorization.
- Implement NemoAgent Critic Pass (Task 0.0).