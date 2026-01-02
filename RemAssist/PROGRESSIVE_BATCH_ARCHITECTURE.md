# Progressive Batch Upload Architecture

**Status**: PROPOSED (Not Yet Implemented)  
**Created**: January 1, 2026 (Session 15)  
**Priority**: High (next major feature after current MVP)

---

## Overview

This document captures the complete 5-phase progressive engagement pipeline designed during Session 15. The architecture enables batch PDF uploads with parallel processing, background analysis, and pre-generated outputs for instant delivery.

### Key Goals
- **Perceived latency**: ~3s to first response, continuous engagement thereafter
- **User engagement**: Show preliminary insights while full analysis runs
- **Instant delivery**: Pre-generate all output formats (dashboard, PDF, infographic) before user asks
- **Security**: PII redaction and encrypted storage throughout

---

## Complete Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│              COMPLETE PROGRESSIVE ENGAGEMENT PIPELINE (5 PHASES)                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  PHASE 1: BATCH UPLOAD + IMMEDIATE RESPONSE (T+0 to T+3s)                       │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                       │
│  • Upload all files → Save to NVMe → Quick metadata extraction                   │
│  • Chunk 1 (summary + 2-3 headers) → NemoAgent                                  │
│  • LLM responds: "I've received 11 Apple Card statements..."                    │
│  • User sees consolidated acknowledgment                                         │
│                                                                                  │
│  PHASE 2: BACKGROUND ANALYSIS (T+3s onwards, while user reads)                  │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                     │
│  • Chunks 2-5 → NemoAgent preliminary analysis                                   │
│  • Extract transactions, patterns, categories, anomalies                         │
│  • BUILD PHINANCE PROMPT (cached, ready to fire)                                │
│  • Cache interesting findings for engagement                                     │
│                                                                                  │
│  PHASE 3: USER GRANTS CONSENT → PARALLEL EXECUTION                              │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                     │
│  • User: "Yes, analyze"                                                          │
│  • IMMEDIATE: NemoAgent sends preliminary insights                               │
│  • PARALLEL: Fire pre-built Phinance prompt (GPU 1)                             │
│  • User engaged with insights while Phinance works                              │
│                                                                                  │
│  PHASE 4: PHINANCE COMPLETES → OFFER OPTIONS + PRE-GENERATE                     │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                     │
│  • Phinance returns detailed analysis                                            │
│  • NemoAgent presents summary + asks: "Would you like..."                       │
│  • PARALLEL BACKGROUND: Pre-generate ALL output formats                         │
│      ├── Dashboard JSON (charts, tables, metrics)                               │
│      ├── PDF report prompt (ready for generation)                               │
│      └── Infographic prompt (ready for generation)                              │
│                                                                                  │
│  PHASE 5: USER SELECTS FORMAT → INSTANT DELIVERY                                │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                     │
│  • User: "Show me the dashboard" → Already ready, instant                       │
│  • User: "Generate PDF" → Fire pre-built prompt, fast                           │
│  • User: "Just answer questions" → Use cached analysis context                  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase Details

### Phase 1: Batch Upload + Immediate Response

```
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 1: BATCH UPLOAD + IMMEDIATE RESPONSE (T+0 to T+3s)                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  [Frontend]                    [Backend]                                 │
│  Upload 11 PDFs ──────────────► Save all to NVMe (~50ms)                │
│                                      │                                   │
│                                      ▼                                   │
│                                Extract metadata for all                  │
│                                (filenames, pages, sizes)                 │
│                                      │                                   │
│                                      ▼                                   │
│                                Quick header parse (2-3 files)            │
│                                      │                                   │
│                                      ▼                                   │
│                          ┌─────────────────────────┐                     │
│                          │  CHUNK 1 → NemoAgent    │                     │
│                          │  (Summary + Headers)    │                     │
│                          └───────────┬─────────────┘                     │
│                                      │                                   │
│                                      ▼                                   │
│  ◄─────────────────────── LLM Response (consolidated)                   │
│  "I've received 11 Apple Card                                           │
│   statements (Jan-Nov 2025)..."                                         │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Phase 2: Background Analysis

```
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 2: BACKGROUND PROCESSING (T+3s onwards, PARALLEL)                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  [Background Task - runs while user reads response]                      │
│                                                                          │
│  ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐     │
│  │ CHUNK 2          │   │ CHUNK 3          │   │ CHUNK 4          │     │
│  │ Files 1-4 text   │   │ Files 5-8 text   │   │ Files 9-11 text  │     │
│  └────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘     │
│           │                      │                      │                │
│           └──────────────────────┼──────────────────────┘                │
│                                  ▼                                       │
│                    ┌─────────────────────────────┐                       │
│                    │   NemoAgent (GPU 0)         │                       │
│                    │   Preliminary Analysis:     │                       │
│                    │   • Extract transactions    │                       │
│                    │   • Detect patterns         │                       │
│                    │   • Identify categories     │                       │
│                    │   • Spot anomalies          │                       │
│                    │   • BUILD PHINANCE PROMPT   │◄── Ready for consent  │
│                    └─────────────────────────────┘                       │
│                                  │                                       │
│                                  ▼                                       │
│                    ┌─────────────────────────────┐                       │
│                    │   CACHED STATE:             │                       │
│                    │   • preliminary_insights    │                       │
│                    │   • phinance_prompt (ready) │                       │
│                    │   • transaction_count       │                       │
│                    │   • interesting_findings    │                       │
│                    └─────────────────────────────┘                       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Phase 3: Consent + Parallel Execution

```
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 3: USER GRANTS CONSENT                                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  User: "Yes, analyze my spending"                                        │
│           │                                                              │
│           ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  PARALLEL EXECUTION:                                            │    │
│  │                                                                  │    │
│  │  [IMMEDIATE - GPU 0]              [BACKGROUND - GPU 1]          │    │
│  │  NemoAgent sends                   Phinance receives            │    │
│  │  preliminary insights              pre-built prompt             │    │
│  │  to user:                          (fires immediately!)         │    │
│  │                                           │                      │    │
│  │  "Analyzing now! While I                  │                      │    │
│  │   work on the full report,                ▼                      │    │
│  │   here's what I noticed:           ┌─────────────┐              │    │
│  │                                    │  Phinance   │              │    │
│  │   📊 Found 847 transactions        │  (GPU 1)    │              │    │
│  │   💰 Highest: Dining $2,340        │  Deep       │              │    │
│  │   📈 Trend: +12% vs last month"    │  Analysis   │              │    │
│  │                                    └──────┬──────┘              │    │
│  │           │                               │                      │    │
│  │           ▼                               │                      │    │
│  │  [User engaged with                       │                      │    │
│  │   preliminary insights]                   │                      │    │
│  │           │                               │                      │    │
│  │           │◄──────────────────────────────┘                      │    │
│  │           │         Phinance done (~10-15s)                      │    │
│  │           ▼                                                      │    │
│  │  "Here's the complete analysis..."                              │    │
│  │                                                                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Phase 4 & 5: Pre-Generated Outputs + Instant Delivery

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  PHASE 4: PHINANCE COMPLETES → PRESENT OPTIONS + PRE-GENERATE                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  [Phinance returns]                                                              │
│         │                                                                        │
│         ▼                                                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  NemoAgent formats and presents:                                        │    │
│  │                                                                          │    │
│  │  "Here's what I found across your 11 statements (Jan-Nov 2025):         │    │
│  │                                                                          │    │
│  │   📊 Total Spending: $12,847.32 across 847 transactions                 │    │
│  │   💰 Top Category: Dining ($2,340 - 18.2%)                              │    │
│  │   🏪 Top Merchant: Amazon ($1,892)                                       │    │
│  │   📈 Trend: Spending up 12% from Jan to Nov                             │    │
│  │   ⚠️ Anomaly: Unusual $450 charge at 'XYZ Corp' in August               │    │
│  │                                                                          │    │
│  │   Would you like:                                                        │    │
│  │   • 📊 Interactive Dashboard (charts, filters, drill-down)              │    │
│  │   • 📄 PDF Report (printable, detailed breakdown)                       │    │
│  │   • 🖼️ Visual Summary (infographic style)                               │    │
│  │   • 💬 Just ask questions about the analysis                            │    │
│  │                                                                          │    │
│  │   Or I can give you a quick text summary right now."                    │    │
│  │                                                                          │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│         │                                                                        │
│         │  [PARALLEL - While user reads/decides]                                │
│         ▼                                                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  PRE-GENERATE ALL FORMATS (Background)                                  │    │
│  │                                                                          │    │
│  │  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────┐  │    │
│  │  │ DASHBOARD JSON      │  │ PDF PROMPT          │  │ INFOGRAPHIC     │  │    │
│  │  │                     │  │                     │  │ PROMPT          │  │    │
│  │  │ {                   │  │ "Generate a         │  │ "Create a       │  │    │
│  │  │  "summary": {...},  │  │  professional       │  │  visual         │  │    │
│  │  │  "charts": {        │  │  financial report   │  │  infographic    │  │    │
│  │  │    "by_category":   │  │  with sections:     │  │  showing:       │  │    │
│  │  │    "by_month":      │  │  - Executive sum    │  │  - Key metrics  │  │    │
│  │  │    "by_merchant":   │  │  - Category breakdown│ │  - Top 5 cats   │  │    │
│  │  │  },                 │  │  - Recommendations  │  │  - Trend arrow  │  │    │
│  │  │  "tables": {...},   │  │  ..."              │  │  ..."           │  │    │
│  │  │  "metrics": {...}   │  │                     │  │                 │  │    │
│  │  │ }                   │  │                     │  │                 │  │    │
│  │  │                     │  │                     │  │                 │  │    │
│  │  │ STATUS: ✅ READY    │  │ STATUS: ✅ READY    │  │ STATUS: ✅ READY│  │    │
│  │  └─────────────────────┘  └─────────────────────┘  └─────────────────┘  │    │
│  │                                                                          │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│  PHASE 5: USER SELECTS → INSTANT DELIVERY                                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  User: "Show me the dashboard"                                                   │
│         │                                                                        │
│         ▼                                                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  Dashboard JSON already ready → Render instantly                        │    │
│  │  Redirect to /dashboard/consolidated?batch_id=xxx                       │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  ─────────────────────────────────────────────────────────────────────────────  │
│                                                                                  │
│  User: "Generate a PDF report"                                                   │
│         │                                                                        │
│         ▼                                                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  PDF prompt already built → Fire to PDF generator                       │    │
│  │  "Generating your report... (progress bar)"                             │    │
│  │  → Download link ready in ~5-10s                                        │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  ─────────────────────────────────────────────────────────────────────────────  │
│                                                                                  │
│  User: "What did I spend on dining in August?"                                  │
│         │                                                                        │
│         ▼                                                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  Full analysis cached in context → NemoAgent answers instantly          │    │
│  │  "In August, you spent $342.15 on dining across 12 transactions.        │    │
│  │   Your top dining merchants were: Chipotle ($89), Uber Eats ($76)..."  │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Structures

### BatchState

```python
# home-ai/soa1/batch_processor.py

@dataclass
class BatchState:
    batch_id: str
    status: str  # "uploading"|"parsing"|"analyzing"|"ready"|"consent_granted"|"complete"
    files: List[Dict]
    
    # Phase 2: Preliminary analysis
    preliminary_insights: Optional[Dict] = None
    phinance_prompt: Optional[str] = None
    transaction_count: int = 0
    interesting_findings: List[str] = field(default_factory=list)
    
    # Phase 4: Phinance results + pre-generated outputs
    phinance_analysis: Optional[Dict] = None
    
    # Pre-generated outputs (ready to serve instantly)
    outputs: Dict[str, Any] = field(default_factory=lambda: {
        "dashboard_json": None,      # Ready for /dashboard/consolidated
        "pdf_prompt": None,          # Ready to fire to PDF generator
        "infographic_prompt": None,  # Ready to fire to image generator
        "text_summary": None,        # Quick text summary
    })
    outputs_ready: bool = False
    
    # Timestamps
    created_at: float = field(default_factory=time.time)
    analysis_ready_at: Optional[float] = None
    phinance_complete_at: Optional[float] = None
    outputs_ready_at: Optional[float] = None
```

### Background Analysis Task

```python
async def background_analyze(batch_id: str):
    """
    Runs in background after initial response sent.
    Feeds chunks 2-5 to NemoAgent for preliminary analysis.
    Builds Phinance prompt ready to fire on consent.
    """
    state = get_batch_state(batch_id)
    
    # Process all PDF text through NemoAgent
    all_text = collect_all_pdf_text(state.files)
    
    # NemoAgent preliminary analysis
    preliminary = await nemo_agent.analyze_preliminary(
        text=all_text,
        file_count=len(state.files),
    )
    
    # Build Phinance prompt (ready to fire)
    phinance_prompt = build_phinance_prompt(
        transactions=preliminary["transactions"],
        categories=preliminary["categories"],
    )
    
    # Cache results
    state.preliminary_insights = preliminary["insights"]
    state.phinance_prompt = phinance_prompt
    state.interesting_findings = preliminary["interesting"]
    state.status = "ready"
    state.analysis_ready_at = time.time()
```

### Output Pre-Generation

```python
async def pre_generate_outputs(batch_id: str):
    """
    Runs in background after Phinance completes.
    Pre-generates all output formats while user reads summary.
    """
    state = get_batch_state(batch_id)
    analysis = state.phinance_analysis
    
    # Generate all formats in parallel
    dashboard_task = asyncio.create_task(generate_dashboard_json(analysis))
    pdf_task = asyncio.create_task(build_pdf_prompt(analysis))
    infographic_task = asyncio.create_task(build_infographic_prompt(analysis))
    summary_task = asyncio.create_task(generate_text_summary(analysis))
    
    # Wait for all
    results = await asyncio.gather(
        dashboard_task, pdf_task, infographic_task, summary_task
    )
    
    state.outputs = {
        "dashboard_json": results[0],
        "pdf_prompt": results[1],
        "infographic_prompt": results[2],
        "text_summary": results[3],
    }
    state.outputs_ready = True
    state.outputs_ready_at = time.time()
```

### Consent Handler

```python
@app.post("/api/consent")
async def grant_consent(batch_id: str, action: str):
    state = get_batch_state(batch_id)
    
    if action == "analyze" and state.status == "ready":
        # PARALLEL: Send preliminary insights + fire Phinance
        
        # 1. Immediate response with preliminary insights
        yield {
            "type": "preliminary",
            "message": format_preliminary_insights(state.preliminary_insights),
            "interesting_findings": state.interesting_findings,
        }
        
        # 2. Fire pre-built Phinance prompt (no delay!)
        phinance_task = asyncio.create_task(
            call_phinance(state.phinance_prompt)
        )
        
        # 3. Wait for Phinance while user reads preliminary
        phinance_result = await phinance_task
        
        # 4. Send final analysis
        yield {
            "type": "final",
            "analysis": phinance_result,
        }
```

---

## Timing Comparison

| Event | Current | New Architecture |
|-------|---------|------------------|
| Upload 11 files | 11 sequential calls | 1 batch call |
| Initial response | ~55s (11 × 5s) | ~3s |
| User reads response | - | Background analysis runs |
| User grants consent | Wait for processing | **Instant preliminary** |
| Phinance analysis | Starts after consent | **Already running** |
| Full results | +15s after consent | +10-15s (masked by engagement) |

**Perceived latency: ~3s to first response, continuous engagement thereafter**

---

## Security Layer

### PII Redaction (CRITICAL)

All PII must be redacted **before** ANY storage or display.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    SECURITY LAYER: PII HANDLING                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  [RAW PDF TEXT - in memory only, never persisted]                               │
│         │                                                                        │
│         ▼                                                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  PII REDACTOR (runs before ANY storage or display)                      │    │
│  │                                                                          │    │
│  │  Detects & Redacts:                                                      │    │
│  │  ├── Credit Card Numbers    → "****-****-****-1234" (last 4 only)       │    │
│  │  ├── Bank Account Numbers   → "****1234"                                 │    │
│  │  ├── Routing Numbers        → "[ROUTING REDACTED]"                       │    │
│  │  ├── SSN/Tax ID             → "***-**-6789" (last 4 only)               │    │
│  │  ├── Full Names (optional)  → Keep or redact based on config            │    │
│  │  ├── Phone Numbers          → "***-***-1234"                            │    │
│  │  ├── Email Addresses        → "j***@***.com"                            │    │
│  │  └── Physical Addresses     → "[ADDRESS REDACTED]" or partial           │    │
│  │                                                                          │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│         │                                                                        │
│         ├──────────────────────────────────┐                                    │
│         │                                  │                                    │
│         ▼                                  ▼                                    │
│  ┌────────────────────────┐    ┌─────────────────────────────────────────┐      │
│  │  LLM PROCESSING        │    │  ENCRYPTED STORAGE                      │      │
│  │                        │    │                                          │      │
│  │  NemoAgent receives    │    │  AES-256-GCM encryption                 │      │
│  │  ONLY redacted text    │    │  Key from env/secure store              │      │
│  │                        │    │                                          │      │
│  │  Phinance receives     │    │  documents.db (SQLite)                  │      │
│  │  ONLY redacted txns    │    │  - Encrypted text blob                  │      │
│  │                        │    │  - Encrypted metadata                   │      │
│  └────────────────────────┘    └─────────────────────────────────────────┘      │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### PII Detection Patterns

```python
# soa1/security/pii_redactor.py

PII_PATTERNS = {
    # Credit Cards (Visa, MC, Amex, Discover)
    "credit_card": {
        "pattern": r"\b(?:4[0-9]{3}|5[1-5][0-9]{2}|3[47][0-9]{2}|6(?:011|5[0-9]{2}))[- ]?[0-9]{4}[- ]?[0-9]{4}[- ]?[0-9]{3,4}\b",
        "redact": lambda m: f"****-****-****-{m.group()[-4:]}",
        "severity": "critical",
    },
    
    # Bank Account Numbers (6-17 digits)
    "bank_account": {
        "pattern": r"\b(?:account|acct)[#:\s]*([0-9]{6,17})\b",
        "redact": lambda m: f"****{m.group(1)[-4:]}",
        "severity": "critical",
    },
    
    # Routing Numbers (9 digits, specific format)
    "routing_number": {
        "pattern": r"\b(?:routing|rtg|aba)[#:\s]*([0-9]{9})\b",
        "redact": "[ROUTING REDACTED]",
        "severity": "critical",
    },
    
    # SSN (XXX-XX-XXXX)
    "ssn": {
        "pattern": r"\b[0-9]{3}-[0-9]{2}-[0-9]{4}\b",
        "redact": "[SSN REDACTED]",
        "severity": "critical",
    },
    
    # EIN/Tax ID
    "ein": {
        "pattern": r"\b[0-9]{2}-[0-9]{7}\b",
        "redact": "[TAX ID REDACTED]",
        "severity": "high",
    },
    
    # Phone Numbers
    "phone": {
        "pattern": r"\b(?:\+1[-.\s]?)?(?:\(?[0-9]{3}\)?[-.\s]?)?[0-9]{3}[-.\s]?[0-9]{4}\b",
        "redact": lambda m: f"***-***-{m.group()[-4:]}",
        "severity": "medium",
    },
    
    # Email Addresses
    "email": {
        "pattern": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "redact": lambda m: f"{m.group()[0]}***@***.{m.group().split('.')[-1]}",
        "severity": "medium",
    },
    
    # Card CVV (3-4 digits near card context)
    "cvv": {
        "pattern": r"\b(?:cvv|cvc|csc)[:\s]*([0-9]{3,4})\b",
        "redact": "[CVV REDACTED]",
        "severity": "critical",
    },
    
    # Expiry Dates (MM/YY or MM/YYYY)
    "card_expiry": {
        "pattern": r"\b(?:exp|expir)[a-z]*[:\s]*([0-9]{2}/[0-9]{2,4})\b",
        "redact": "[EXPIRY REDACTED]",
        "severity": "high",
    },
}
```

### Encrypted Storage

```python
# soa1/security/encrypted_storage.py

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

class EncryptedStorage:
    """
    AES-256-GCM encrypted storage for sensitive financial data.
    Key loaded from environment or secure key file.
    """
    
    def __init__(self):
        self.key = self._load_or_generate_key()
        self.aesgcm = AESGCM(self.key)
    
    def _load_or_generate_key(self) -> bytes:
        """Load key from env or generate and store securely"""
        key_path = Path(os.environ.get("SOA1_KEY_PATH", "/mnt/models/soa1/.key"))
        
        if key_path.exists():
            return key_path.read_bytes()
        
        # Generate new key
        key = AESGCM.generate_key(bit_length=256)
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_bytes(key)
        os.chmod(key_path, 0o600)  # Owner read/write only
        return key
    
    def encrypt(self, data: str) -> bytes:
        """Encrypt string data with AES-256-GCM"""
        nonce = os.urandom(12)
        ciphertext = self.aesgcm.encrypt(nonce, data.encode(), None)
        return nonce + ciphertext  # Prepend nonce for decryption
    
    def decrypt(self, encrypted: bytes) -> str:
        """Decrypt AES-256-GCM encrypted data"""
        nonce = encrypted[:12]
        ciphertext = encrypted[12:]
        return self.aesgcm.decrypt(nonce, ciphertext, None).decode()
```

### Encrypted Database Schema

```sql
-- SQLite schema with encrypted columns

CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    batch_id TEXT,
    filename_hash TEXT,  -- SHA-256 hash, not actual filename
    filename_encrypted BLOB,  -- AES-256 encrypted
    pages INTEGER,
    size_bytes INTEGER,
    text_encrypted BLOB,  -- AES-256 encrypted (already PII-redacted)
    metadata_encrypted BLOB,  -- AES-256 encrypted JSON
    created_at REAL,
    FOREIGN KEY (batch_id) REFERENCES batches(batch_id)
);

CREATE TABLE IF NOT EXISTS transactions (
    tx_id TEXT PRIMARY KEY,
    doc_id TEXT,
    date TEXT,  -- Not sensitive
    merchant_redacted TEXT,  -- PII-redacted merchant name
    amount_encrypted BLOB,  -- AES-256 encrypted
    category TEXT,  -- Not sensitive (e.g., "Dining")
    metadata_encrypted BLOB,
    created_at REAL,
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
);

CREATE TABLE IF NOT EXISTS batches (
    batch_id TEXT PRIMARY KEY,
    status TEXT,
    file_count INTEGER,
    preliminary_encrypted BLOB,  -- AES-256 encrypted JSON
    phinance_encrypted BLOB,  -- AES-256 encrypted JSON
    outputs_encrypted BLOB,  -- AES-256 encrypted JSON
    created_at REAL,
    updated_at REAL
);

-- Index for fast lookups without exposing data
CREATE INDEX IF NOT EXISTS idx_documents_batch ON documents(batch_id);
CREATE INDEX IF NOT EXISTS idx_transactions_doc ON transactions(doc_id);
CREATE INDEX IF NOT EXISTS idx_batches_status ON batches(status);
```

---

## Secure Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         SECURE DATA FLOW                                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  [PDF Upload]                                                                    │
│       │                                                                          │
│       ▼                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  1. EXTRACT (in memory)                                                 │    │
│  │     raw_text = pdf_processor.extract_text(file)                         │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│       │                                                                          │
│       ▼                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  2. REDACT PII (before anything else)                                   │    │
│  │     redacted_text, pii_log = pii_redactor.redact(raw_text)              │    │
│  │     # pii_log: {"credit_cards": 2, "ssn": 1, ...} (counts only)         │    │
│  │     # raw_text: DISCARDED, never stored                                 │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│       │                                                                          │
│       ├──────────────────────────────────┐                                       │
│       │                                  │                                       │
│       ▼                                  ▼                                       │
│  ┌────────────────────────┐    ┌─────────────────────────────────────────┐      │
│  │  3a. LLM PROCESSING    │    │  3b. ENCRYPT & STORE                    │      │
│  │                        │    │                                          │      │
│  │  NemoAgent receives    │    │  encrypted = storage.encrypt(redacted)  │      │
│  │  ONLY redacted text    │    │  db.save(doc_id, encrypted)             │      │
│  │                        │    │                                          │      │
│  │  Phinance receives     │    │  # Original PDF also encrypted          │      │
│  │  ONLY redacted txns    │    │  pdf_encrypted = storage.encrypt(bytes) │      │
│  │                        │    │  save_to_secure_path(pdf_encrypted)     │      │
│  └────────────────────────┘    └─────────────────────────────────────────┘      │
│       │                                                                          │
│       ▼                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  4. WEBUI DISPLAY                                                       │    │
│  │                                                                          │    │
│  │  ✅ Shows: "AMAZON - $45.99 - Dining"                                   │    │
│  │  ✅ Shows: "Card ending in 1234"                                        │    │
│  │  ❌ Never: Full card number                                             │    │
│  │  ❌ Never: Account numbers                                              │    │
│  │  ❌ Never: SSN/Tax ID                                                   │    │
│  │  ❌ Never: Unredacted PII                                               │    │
│  │                                                                          │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Files to Create/Modify

### New Files

| File | Purpose |
|------|---------|
| `soa1/security/__init__.py` | Security module init |
| `soa1/security/pii_redactor.py` | PII detection & redaction |
| `soa1/security/encrypted_storage.py` | AES-256-GCM encryption, secure DB |
| `soa1/security/audit_log.py` | Log all data access (no PII in logs) |
| `soa1/batch_processor.py` | BatchState, background tasks |
| `soa1/output_generator.py` | Dashboard JSON, PDF/infographic prompts |

### Modified Files

| File | Changes |
|------|---------|
| `soa1/api.py` | Add `/upload-batch`, `/api/consent` batch support, `/api/output/{format}` |
| `soa1/agent.py` | Add `analyze_preliminary()`, batch context handling |
| `soa1/pdf_processor.py` | Integrate PII redaction immediately after extraction |
| `soa1/prompts/orchestrator.md` | Batch handling instructions, output options |
| `soa-webui/templates/index.html` | Batch upload, SSE streaming, output selection UI |

---

## Environment Setup

```bash
# .env file (never commit!)
SOA1_KEY_PATH=/mnt/models/soa1/.encryption_key
SOA1_DB_PATH=/mnt/models/soa1/data/finance.db
SOA1_SECURE_UPLOADS=/mnt/models/soa1/data/uploads_encrypted/

# Permissions
chmod 600 /mnt/models/soa1/.encryption_key
chmod 700 /mnt/models/soa1/data/
```

---

## Security Summary

| Layer | Protection |
|-------|------------|
| **Extraction** | PII redacted immediately, raw text never stored |
| **Processing** | LLMs only see redacted data |
| **Storage** | AES-256-GCM encryption for all persisted data |
| **Display** | WebUI only shows redacted/masked values |
| **Audit** | All access logged (without PII in logs) |
| **Keys** | Stored in secure path, 600 permissions |

---

## Implementation Priority

1. **Security Layer** (FIRST - required for production)
   - `pii_redactor.py` - PII detection and redaction
   - `encrypted_storage.py` - AES-256 encryption
   - Integrate into existing upload flow

2. **Batch Processing** (enables better UX)
   - `batch_processor.py` - BatchState management
   - Background analysis task
   - Update API endpoints

3. **Output Pre-generation** (polish)
   - `output_generator.py` - Dashboard, PDF, infographic prompts
   - Phase 4-5 implementation

---

## Related Documents

- `RemAssist/IMPLEMENTATION_GUIDE.md` - Core consent-first rules
- `RemAssist/LLM_DRIVEN_RESPONSES.md` - User-facing communication principle
- `RemAssist/FINANCE_UPLOAD_CONSENT_AND_PERSISTENCE.md` - Current upload flow
- `home-ai/ARCHITECTURE.md` - System architecture

---

*Document created from Session 15 discussion (January 1, 2026)*
