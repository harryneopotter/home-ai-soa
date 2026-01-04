# Progressive Flow Architecture

**Version**: 1.0  
**Created**: January 3, 2026  
**Status**: CANONICAL - This is the authoritative document for the upload-to-analysis flow

> ⚠️ **AGENTS: READ THIS FIRST** before touching any upload, batch, or analysis code.

---

## Overview

The system uses a **progressive chunked flow** where background processing happens while the user reads/responds. The goal is to make every user interaction feel instant by pre-computing the next step while they're engaged.

**Key Principle**: Never make the user wait. Always be one step ahead.

---

## The Four Phases

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 1: Quick Acknowledgment (~1-2s)                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ User uploads PDFs                                                            │
│     ↓                                                                        │
│ Parse metadata: file count, names, page counts, headers (1-2 files)          │
│     ↓                                                                        │
│ LLM generates engagement:                                                    │
│   "Looks like you uploaded 4 Apple Card statements (May-July 2025).         │
│    Want me to analyze them, or do you have specific questions?"              │
│     ↓                                                                        │
│ Return immediately to user                                                   │
│                                                                              │
│ 🔄 BACKGROUND STARTS: Regex extraction + calculate_financials()              │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 2: User Gives Consent                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ User: "yes, analyze them"                                                    │
│     ↓                                                                        │
│ LLM detects consent → triggers [INVOKE:phinance]                             │
│     ↓                                                                        │
│ 1. Save transactions to DB (NOW we persist - not before!)                    │
│ 2. Send prompt to phinance for deep insights                                 │
│ 3. LLM immediately responds with pre-computed "interesting findings":        │
│    "Thanks! Starting analysis. While I crunch the numbers, I noticed         │
│     you spent $847 at restaurants - 32% higher than your 3-month average..." │
│                                                                              │
│ 🔄 BACKGROUND: Phinance generating insights                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 3: Analysis Ready - Ask Output Format                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ Phinance returns → merge with Python-calculated numbers                      │
│     ↓                                                                        │
│ LLM presents summary and asks for output format:                             │
│   "Analysis ready! Quick summary:                                            │
│    📊 Total: $4,637.33 across 66 transactions                               │
│    💰 Top: Dining $847, Shopping $1,203                                     │
│    🔍 Found 3 potential hidden drains                                       │
│                                                                              │
│    How do you want the detailed report?                                      │
│    1. Web Dashboard  2. PDF Export  3. Infographic"                          │
│                                                                              │
│ 🔄 BACKGROUND STARTS: Pre-generate ALL three output formats                  │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 4: Instant Output Delivery (~1s)                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│ User: "web dashboard" (or "PDF" or "infographic")                            │
│     ↓                                                                        │
│ Grab pre-generated output from BatchState.outputs                            │
│     ↓                                                                        │
│ Deliver instantly:                                                           │
│   • Web → Render soa_dashboard.html with dashboard_json                      │
│   • PDF → Execute pre-built pdf_command                                      │
│   • Infographic → Send pre-built prompt to flux/image model                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Critical Design Decisions

### 1. Transactions are NOT saved until consent
- Phase 1 background: Extract transactions, calculate totals → store in **memory only**
- Phase 2 on consent: NOW save to database
- Rationale: User agency - we don't persist their financial data without explicit permission

### 2. Python does ALL math, LLMs do qualitative analysis
- `calculate_financials()` → totals, categories, top merchants (0.05ms, 100% accurate)
- `phinance` / `qwen2.5` → insights, recommendations, potential savings (5-6s)
- Rationale: LLMs are terrible at arithmetic on large datasets

### 3. Regex extracts transactions, not LLM
- `FinanceStatementParser` uses `APPLE_CARD_REGEX` / `GENERIC_BANK_REGEX`
- Only falls back to LLM (nemotron) if regex finds nothing
- Location: `home-ai/finance-agent/src/parser.py`

### 4. Pre-generate all outputs while user reads
- After Phase 3 summary, immediately generate:
  - `dashboard_json` for web report
  - `pdf_command` for PDF export
  - `infographic_prompt` for image generation
- When user chooses, output is already ready

---

## BatchState Structure

```python
@dataclass
class BatchState:
    batch_id: str
    status: str  # uploading → extracting → ready → analyzing → complete
    files: List[Dict]
    
    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 1: Background extraction (IN MEMORY - NOT in DB)
    # ═══════════════════════════════════════════════════════════════════════
    extracted_transactions: List[Dict] = None    # From regex extraction
    calculated_summary: Dict = None              # From calculate_financials()
    interesting_findings: List[str] = None       # Hooks for user engagement
    
    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 2: After user consent
    # ═══════════════════════════════════════════════════════════════════════
    transactions_persisted: bool = False         # True ONLY after consent + DB save
    
    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 3: Phinance analysis results
    # ═══════════════════════════════════════════════════════════════════════
    phinance_analysis: Dict = None               # Full analysis from phinance
    phinance_attempts: int = 0                   # Retry tracking
    
    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 4: Pre-generated outputs (ready for instant delivery)
    # ═══════════════════════════════════════════════════════════════════════
    outputs: Dict = field(default_factory=lambda: {
        "dashboard_json": None,      # JSON for soa_dashboard.html
        "pdf_command": None,         # Command string ready to execute
        "infographic_prompt": None,  # Prompt ready for flux/image model
        "text_summary": None,        # Plain text summary
    })
    outputs_ready: bool = False
    
    # ═══════════════════════════════════════════════════════════════════════
    # Timestamps for performance tracking
    # ═══════════════════════════════════════════════════════════════════════
    created_at: float
    extraction_complete_at: float = None
    consent_given_at: float = None
    analysis_complete_at: float = None
    outputs_ready_at: float = None
```

---

## File Responsibilities

| File | Responsibility |
|------|----------------|
| `soa1/api.py` | HTTP endpoints, session management |
| `soa1/batch_processor.py` | BatchState management, background extraction, output pre-generation |
| `soa1/agent.py` | LLM interaction, consent detection, `_invoke_phinance()`, **spawns own background phinance thread** |
| `soa1/output_generator.py` | Generate dashboard JSON, PDF command, infographic prompt |
| `finance-agent/src/parser.py` | `FinanceStatementParser` - regex transaction extraction |
| `soa1/utils/financial_calculator.py` | Python calculation utilities |

---

## Endpoint Flow

### Upload: `POST /upload-batch`
```
1. Parse PDFs → extract metadata (filename, pages, headers)
2. Create BatchState with status="uploading"
3. Kick off background task: extract_and_calculate()
4. Call LLM with metadata → generate acknowledgment
5. Return immediately: {batch_id, agent_response}
```

### Chat: `POST /api/chat`
```
1. Get session's active BatchState
2. If user gives consent AND [INVOKE:phinance] detected:
   a. Agent spawns background thread for phinance analysis
   b. Save transactions to DB (transactions_persisted = True)
   c. Return "interesting_findings" immediately
3. If phinance complete → present summary, ask output format
4. If user selects output → return pre-generated output instantly
```

### Output Delivery: `GET /api/batch/{batch_id}/output/{type}`
```
type = "dashboard" | "pdf" | "infographic"
1. Get BatchState
2. Return outputs[type] if ready
3. If not ready, generate on-demand (fallback)
```

---

## Background Tasks

### Task 1: `extract_and_calculate()` (runs after upload)
```python
async def extract_and_calculate(batch_id: str):
    state = get_batch_state(batch_id)
    state.status = "extracting"
    
    # 1. Run regex extraction on all PDFs
    all_transactions = []
    for doc in state.files:
        txns = regex_extract(doc["full_text"], doc.get("is_apple_card"))
        all_transactions.extend(txns)
    
    # 2. Calculate financials (Python - instant, accurate)
    summary = calculate_financials(all_transactions)
    
    # 3. Build interesting findings for engagement
    findings = build_interesting_findings(all_transactions, summary)
    
    # 4. Store in BatchState (NOT database!)
    state.extracted_transactions = all_transactions
    state.calculated_summary = summary
    state.interesting_findings = findings
    state.extraction_complete_at = time.time()
    state.status = "ready"
```

### Task 2: `run_phinance_analysis()` (runs after consent)

**Note**: As of Session 30, phinance analysis is spawned directly by the agent via `_spawn_phinance_background()`, not triggered by API endpoints.

```python
def _spawn_phinance_background(batch_id: str, document_context: Dict):
    """Agent spawns its own background thread - no API cooperation needed."""
    
    def _run_analysis():
        state.status = "analyzing"
        
        # 1. Save transactions to DB (consent was given)
        save_transactions_to_db(state.extracted_transactions)
        state.transactions_persisted = True
        
        # 2. Call phinance for deep insights
        analysis = _invoke_phinance(document_context)
        
        # 3. Merge Python numbers with LLM insights
        state.phinance_analysis = merge_calculated_with_llm(...)
        state.status = "complete"
        
        # 4. Immediately start pre-generating outputs
        pre_generate_outputs_sync(batch_id)
    
    thread = threading.Thread(target=_run_analysis, daemon=True)
    thread.start()
```

### Task 3: `pre_generate_outputs()` (runs after analysis)
```python
async def pre_generate_outputs(batch_id: str):
    state = get_batch_state(batch_id)
    analysis = state.phinance_analysis
    
    # Generate all three formats in parallel
    dashboard_task = generate_dashboard_json(analysis)
    pdf_task = build_pdf_command(analysis)
    infographic_task = build_infographic_prompt(analysis)
    
    results = await asyncio.gather(dashboard_task, pdf_task, infographic_task)
    
    state.outputs = {
        "dashboard_json": results[0],
        "pdf_command": results[1],
        "infographic_prompt": results[2],
    }
    state.outputs_ready = True
    state.outputs_ready_at = time.time()
```

---

## Timing Expectations

| Phase | User Wait Time | Background Work |
|-------|----------------|-----------------|
| Phase 1 | ~1-2s | Extraction starts (5-10s) |
| Phase 2 | ~1s (immediate response) | Phinance runs (5-10s) |
| Phase 3 | ~1s (summary ready) | Output generation (2-3s) |
| Phase 4 | <1s (instant) | Already done |

**Total perceived wait**: ~4-5s  
**Total actual processing**: 15-25s  
**User never waits more than 2s** at any step

---

## Error Handling

### Extraction fails
- Log error, set status="failed"
- LLM responds: "I had trouble reading your documents. Could you try uploading again?"

### Phinance fails after retries
- Fall back to Python-only summary (still accurate numbers, just no LLM insights)
- LLM responds: "Here's what I found..." (calculated data only)

### Output generation fails
- Generate on-demand when user requests
- Slightly slower but still works

---

## Related Documents

- `BATCH_FLOW.md` - Original 5-phase pipeline (being superseded by this)
- `HYBRID_EXTRACTION_ARCHITECTURE.md` - Python + LLM hybrid approach
- `PROJECT_STATE.md` - Overall system state
- `IMPLEMENTATION_GUIDE.md` - Consent rules (upload ≠ consent)
- `LLM_DRIVEN_RESPONSES.md` - All responses from LLM, not hardcoded

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-04 | Updated Task 2 to reflect self-spawning phinance (agent spawns own thread) |
| 2026-01-03 | Initial version - documented progressive flow architecture |
