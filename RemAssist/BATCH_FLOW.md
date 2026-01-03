# Batch Upload Flow — Progressive 5-Phase Pipeline

**Status**: Partially Implemented  
**Last Updated**: January 2, 2026  
**Related**: `PROGRESSIVE_BATCH_ARCHITECTURE.md` (full technical spec)

---

## Overview

This document describes the **user-facing flow** for batch PDF uploads. All batch/upload work MUST follow this flow.

**Key Principle**: Return immediately, process in background, poll for status.

---

## The 5 Phases

### Phase 1: Upload + Immediate Response (T+0 to T+3s)

```
User uploads 5 PDFs
    ↓
Frontend → POST /upload-batch
    ↓
Backend (SOA1):
  1. Save files to disk (~50ms)
  2. Extract quick metadata (filenames, pages, sizes)
  3. Quick header parse (2-3 files)
  4. Create batch via batch_processor.create_batch()
  5. Start background_analyze() task
  6. Call NemoAgent for acknowledgment
    ↓
RETURN IMMEDIATELY (~3s):
  {
    "status": "SUCCESS",
    "batch_id": "batch-abc123",
    "file_count": 5,
    "agent_response": "I've received 5 Apple Card statements (Jan-May 2025)..."
  }
    ↓
User sees acknowledgment + consent question
```

**What user sees**: "I've received 5 Apple Card statements. Would you like me to analyze them?"

---

### Phase 2: Background Analysis (T+3s onwards)

```
[Background task - user doesn't wait]
    ↓
Parse all PDF text fully
    ↓
NemoAgent preliminary analysis:
  - Extract transactions
  - Detect patterns  
  - Identify categories
  - Spot anomalies
    ↓
BUILD PHINANCE PROMPT (cached, ready to fire on consent)
    ↓
Update batch state:
  - status: "ready" (was "analyzing")
  - preliminary_insights: {...}
  - phinance_prompt: "..." (pre-built)
  - interesting_findings: [...]
```

**Frontend polling**: `GET /api/batch/status/{batch_id}` until `status == "ready"`

---

### Phase 3: User Grants Consent → Parallel Execution

```
User: "Yes, analyze my spending"
    ↓
POST /api/batch/consent {batch_id, action: "analyze"}
    ↓
IMMEDIATE response (no wait):
  - Send preliminary insights
  - "Analyzing now! Here's what I noticed:
     📊 847 transactions found
     💰 Highest category: Dining $2,340
     📈 Trend: +12% vs last month"
    ↓
PARALLEL (background):
  - Fire pre-built Phinance prompt (already cached from Phase 2!)
  - User engaged with preliminary while Phinance runs (~10-15s)
    ↓
Phinance completes
    ↓
Update batch state:
  - status: "complete"
  - phinance_analysis: {...}
```

---

### Phase 4: Phinance Completes → Offer Options + Pre-Generate

```
NemoAgent presents full analysis:
  "Here's what I found across your 5 statements:
   📊 Total Spending: $12,847.32 across 847 transactions
   💰 Top Category: Dining ($2,340 - 18.2%)
   🏪 Top Merchant: Amazon ($1,892)
   
   Would you like:
   • 📊 Interactive Dashboard
   • 📄 PDF Report  
   • 🖼️ Visual Summary
   • 💬 Just ask questions"
    ↓
PARALLEL (background, while user reads):
  - Pre-generate dashboard JSON
  - Pre-generate PDF prompt
  - Pre-generate infographic prompt
    ↓
Update batch state:
  - outputs_ready: true
  - outputs: {dashboard_json, pdf_prompt, infographic_prompt, text_summary}
```

---

### Phase 5: User Selects → Instant Delivery

```
User: "Show me the dashboard"
    ↓
GET /api/output/{batch_id}/dashboard
    ↓
Dashboard JSON already ready → Render instantly

User: "Generate PDF"
    ↓
PDF prompt already built → Fire to generator → Fast delivery (~5-10s)
```

---

## Required Endpoints

| Endpoint | Purpose | Status |
|----------|---------|--------|
| `POST /upload-batch` | Phase 1 - receive files, return immediately | ✅ Exists |
| `GET /api/batch/status/{batch_id}` | Poll for batch state (status, outputs_ready) | ❌ **MISSING** |
| `POST /api/batch/consent` | Phase 3 - grant consent, trigger analysis | ✅ Exists |
| `GET /api/output/{batch_id}/{format}` | Phase 5 - get pre-generated outputs | ✅ Exists |

---

## Batch State Machine

```
uploading → analyzing → ready → [consent] → processing → complete
    ↓           ↓         ↓                      ↓           ↓
  files      parsing   phinance_prompt      phinance    outputs_ready
  saved      text      built & cached       running     = true
```

### BatchState Fields

```python
@dataclass
class BatchState:
    batch_id: str
    status: str  # "uploading"|"analyzing"|"ready"|"processing"|"complete"|"failed"
    files: List[Dict]
    
    # Phase 2 results
    preliminary_insights: Optional[Dict] = None
    phinance_prompt: Optional[str] = None  # Pre-built, ready to fire
    transaction_count: int = 0
    interesting_findings: List[str] = []
    
    # Phase 3-4 results  
    phinance_analysis: Optional[Dict] = None
    
    # Phase 4-5 pre-generated outputs
    outputs: Dict[str, Any] = {
        "dashboard_json": None,
        "pdf_prompt": None,
        "infographic_prompt": None,
        "text_summary": None,
    }
    outputs_ready: bool = False
    
    # Timestamps
    created_at: float
    analysis_ready_at: Optional[float] = None
    phinance_complete_at: Optional[float] = None
    outputs_ready_at: Optional[float] = None
```

---

## Frontend Polling Logic

```javascript
async function pollBatchStatus(batchId) {
    const interval = setInterval(async () => {
        const response = await fetch(`/api/batch/status/${batchId}`);
        const data = await response.json();
        
        if (data.status === 'ready') {
            // Phase 2 complete - show consent question
            clearInterval(interval);
            showConsentQuestion(data.preliminary_insights);
        } else if (data.status === 'complete') {
            // Phase 4 complete - show full analysis
            clearInterval(interval);
            showAnalysisResults(data);
        } else if (data.status === 'failed') {
            clearInterval(interval);
            showError(data.error);
        }
        // else: still processing, keep polling
    }, 2000); // Poll every 2 seconds
}
```

---

## Key Timing Targets

| Event | Target | Notes |
|-------|--------|-------|
| Initial response | < 3s | User sees acknowledgment immediately |
| Phase 2 complete | < 10s | Background, user reading response |
| Preliminary insights | Instant | Cached from Phase 2 |
| Phinance analysis | 10-15s | Masked by user engagement |
| Output delivery | < 1s | Pre-generated in Phase 4 |

---

## What This Fixes

**Before** (broken):
- WebUI polled `/upload-status/{doc_id}` for individual docs
- But `/upload-batch` uses `batch_processor` with `batch_id`
- No endpoint to get batch state
- Frontend stuck at "Processing in background" forever

**After** (correct):
- Add `GET /api/batch/status/{batch_id}` to SOA1
- Returns `batch_processor.get_batch_state(batch_id)` 
- Frontend polls batch status, sees `status` transitions
- Shows consent question when `status == "ready"`

---

## Implementation Checklist

- [ ] Add `GET /api/batch/status/{batch_id}` to `home-ai/soa1/api.py`
- [ ] Update WebUI `/api/batch/status` to proxy to SOA1's endpoint
- [ ] Fix frontend to check `status` field (not `outputs_ready` alone)
- [ ] Test full flow: upload → poll → consent → analysis → output

---

## Related Documents

- `PROGRESSIVE_BATCH_ARCHITECTURE.md` — Full technical spec with security layer
- `PROJECT_STATE.md` — Current system state
- `IMPLEMENTATION_GUIDE.md` — Consent-first rules (applies to Phase 3)
- `LLM_DRIVEN_RESPONSES.md` — All user messages from LLM (applies to all phases)
