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

### January 2, 2026 - Security Hardening: Rate Limiting (Session 20)

#### 🛡️ Rate Limiting Implemented
- **Feature**: Implemented token bucket rate limiting on public-facing API endpoints.
- **File Modified**: `home-ai/soa1/utils/rate_limiter.py`
- **Logic**: Configured `get_limiter_for_endpoint` to correctly map endpoints to specific limits:
    - `/upload-batch` and `/upload-pdf` use `pdf_limiter` (10 requests/minute).
    - `/ask-with-tts` uses `tts_limiter` (20 requests/minute).
    - All other endpoints (`/api/chat`, `/ask`, `/api/batch/consent`, etc.) use `api_limiter` (100 requests/minute).
- **Rationale**: Mitigates resource exhaustion and abuse, aligning with the project's security goals.

#### 📝 Security Scope Clarification
- **Decision**: Deferred comprehensive security measures (API Key Authentication, Audit Logging, HTTPS Enforcement) as the system is currently restricted to a local, on-premise network via Tailscale.
- **Action**: Added a dedicated task for comprehensive security hardening to the `NEXT_TASKS.md` for a future development phase.

#### 📝 Files Modified
- `home-ai/soa1/utils/rate_limiter.py` - Updated endpoint mapping.
- `RemAssist/History.md` - Updated with current session summary.
- `RemAssist/NEXT_TASKS.md` - Updated with final status and new deferred task.

---

### January 2, 2026 - Bug Fix and Input Validation (Session 21)

#### 🐛 Fixed `_invoke_phinance()` Tuple Unpacking Bug
- **Issue**: `call_phinance()` was updated to return `Tuple[str, int]` (response, attempts), but `_invoke_phinance()` still expected a plain string, causing a TypeError.
- **File Modified**: `home_ai/soa1/agent.py`
- **Fix**: Changed `raw_response = call_phinance(...)` to `raw_response, _ = call_phinance(...)`

#### 🧹 Code Cleanup
- Removed unnecessary comments in `analyze_batch()` function per project hook rules:
  - `# Merge transactions into the analysis dictionary`
  - `# --- Merchant Normalization ---`
  - `# ------------------------------`

#### 🛡️ Input Length Limits Added
- **File Modified**: `home_ai/soa1/api.py`
- **Constants Added**:
  - `MAX_MESSAGE_LENGTH = 10000` (chars)
  - `MAX_FILE_SIZE = 10 * 1024 * 1024` (10 MB)
  - `MAX_BATCH_ID_LENGTH = 100` (chars)
- **Endpoints Protected**:
  - `/api/chat` - message length validation
  - `/ask` - query length validation
  - `/ask-with-tts` - query length validation
  - `/upload-batch` - file size validation per file
  - `/api/batch/consent` - batch_id length validation
  - `/upload-pdf` - already had file size validation (10MB)

#### 📝 Files Modified
- `home_ai/soa1/agent.py` - Bug fix and comment cleanup
- `home_ai/soa1/api.py` - Input validation constants and checks

---

### January 2, 2026 - Logging Enhancements (Session 21 continued)

#### 📊 Enhanced Model Call Logging
- **Correlation IDs**: Added `correlation_id` field to link request/response pairs
  - Generated via `generate_correlation_id()` helper function
  - Format: `req-{12-char-hex}`
- **Attempt Tracking**: Added `attempt` field for retry scenarios
  - Each retry attempt is logged individually with its timing
- **Dynamic prompt_source**: Fixed `_dispatch_request()` to use `endpoint.name` instead of hardcoded "phinance"
  - NemoAgent calls logged as `prompt_source="nemoagent"`
  - Phinance calls logged as `prompt_source="phinance"`

#### 📝 Files Modified
- `home_ai/soa1/utils/model_logging.py` - Added `generate_correlation_id()`, `correlation_id` and `attempt` fields
- `home_ai/soa1/models.py` - Updated `_dispatch_request()` signature, added logging params to retry loop
- `home_ai/soa1/model.py` - Added correlation_id to NemoAgent logging

#### Log Entry Structure
```json
{
  "timestamp_utc": "2026-01-02T10:28:57.569827Z",
  "correlation_id": "req-deee1a444716",
  "attempt": 1,
  "model_name": "phinance-json:latest",
  "prompt_source": "phinance",
  "prompt_type": "request|response",
  "latency_ms": 18187.5,
  "status": "success"
}
```

---


### January 2, 2026 - Hybrid Calculation Architecture Complete (Session 23)

#### Problem Solved
LLMs fundamentally struggle with arithmetic on large datasets. Phinance returned garbage totals, NemoAgent was accurate but 71s too slow.

#### Root Cause
LLMs process tokens, not numbers. They "simulate" math via pattern matching rather than actual computation.

#### Solution Implemented: Hybrid Architecture
- **Python** calculates all numbers (0.05ms, 100% accurate)
- **qwen2.5:7b-instruct** generates qualitative insights only (5-6s)
- Combined: 6.3s total, accurate numbers + quality insights

#### Key Discovery
Phinance has a baked-in Modelfile system prompt that forces it to output the full financial analysis schema. It ignores "insights only" requests and outputs malformed JSON. Solution: Use qwen2.5 for insights instead.

#### Hidden Drains Feature Added
- **Python** detects potential hidden drains (small recurring charges <$50, 3+ times)
- **LLM** verifies each drain contextually (is it truly discretionary/wasteful?)
- Results include `is_drain` boolean and `llm_reason` explanation

#### Files Created/Modified
- **Created** `home-ai/soa1/utils/financial_calculator.py` - Python calculation utilities
  - `calculate_financials()` - totals, categories, top merchants
  - `detect_hidden_drains()` - finds small recurring charges
  - `build_insights_prompt()` - includes drains for LLM verification
  - `strip_markdown_fences()` - handles LLM response formatting
- **Modified** `home-ai/soa1/models.py` - Added `call_insights_model()`, "insights" endpoint config
- **Modified** `home-ai/soa1/agent.py` - Updated `_invoke_phinance()` for hybrid approach, enhanced drain display
- **Updated** `RemAssist/INSIGHTS_QUALITY_COMPARISON.md` - Added hybrid results section
- **Updated** `RemAssist/HYBRID_EXTRACTION_ARCHITECTURE.md` - Full architecture documentation

#### Performance Results
| Approach | Time | Math Accuracy |
|----------|------|---------------|
| Phinance only | 10s | ❌ Missing |
| NemoAgent only | 71s | ⚠️ ~99% |
| **Hybrid (Python + qwen2.5)** | **~5s** | ✅ **100%** |

---

### January 2, 2026 - Hardware Specs Documentation (Session 22)

#### 📄 Created Hardware Specs Document
- **New File**: `RemAssist/HARDWARE_SPECS.md`
- **Purpose**: Comprehensive hardware reference for AI agents to understand resource limits
- **Contents**:
  - System identity (hostname, OS, IP)
  - CPU specs (i5-12600K, 16 threads)
  - RAM specs (128 GB DDR5)
  - GPU specs (2x RTX 5060 Ti, 16GB each)
  - Current GPU allocation (NemoAgent ~10.7GB, phinance ~10.8GB)
  - Storage specs (2x 1TB NVMe)
  - Ollama model inventory
  - Resource planning matrix with decision guide

#### 📝 Updated Documentation
- **AGENTS.md**: Added HARDWARE_SPECS.md reference with mandatory GPU check rule
- **PROJECT_STATE.md**: Updated VRAM figures, added hardware specs reference
- **home-ai/ARCHITECTURE.md**: Corrected CUDA version (13.0), updated VRAM figures

#### 🎯 Key Decision
- Agents MUST check HARDWARE_SPECS.md before proposing new models or GPU-intensive features
- This prevents proposals that exceed available VRAM budget

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
