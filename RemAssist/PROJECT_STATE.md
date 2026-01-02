# SOA1 Project State - January 2026

**Version**: 2.1  
**Last Updated**: January 1, 2026 (Session 15)  
**Hardware**: Intel X670 + 2x NVIDIA RTX 5060 Ti (16GB each, 32GB total VRAM)

---

## Overview

**SOA1 (Son of Anton)** is a local-first, privacy-focused home assistant with financial analysis capabilities. It runs entirely on local hardware with no cloud dependencies.

### Core Principles
1. **Privacy-First**: All processing happens locally
2. **Consent-Based**: No specialist actions without explicit user confirmation
3. **User Agency**: User always controls what happens; silence ≠ consent
4. **LLM-Driven Communication**: All user-facing responses come from LLM, not hardcoded strings (see `RemAssist/LLM_DRIVEN_RESPONSES.md`)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│  │ WebUI (8080)    │  │ Chat Interface  │  │ Monitoring (8003)   │  │
│  │ Main dashboard  │  │ (8002)          │  │ Service status      │  │
│  └────────┬────────┘  └────────┬────────┘  └──────────┬──────────┘  │
│           │                    │                       │             │
│           └────────────────────┴───────────────────────┘             │
│                                │                                     │
└────────────────────────────────┼─────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         SOA1 API (8001)                             │
│  Endpoints: /upload-pdf, /api/chat, /api/consent, /health           │
│  FastAPI server with session tracking and consent enforcement       │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│ SOA1 Agent      │  │ MemLayer (8000)     │  │ SQLite Database     │
│ (agent.py)      │  │ Long-term memory    │  │ finance.db          │
│                 │  │ Episodic context    │  │ - documents         │
│ - Query handler │  │ Vector search       │  │ - transactions      │
│ - Memory search │  └─────────────────────┘  │ - analysis_jobs     │
│ - [INVOKE] tag  │                           │ - chat_history      │
│   detection     │                           └─────────────────────┘
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         OLLAMA (11434)                              │
│  ┌─────────────────────────┐  ┌─────────────────────────────────┐  │
│  │ NemoAgent (GPU 0)       │  │ phinance-json (GPU 1)           │  │
│  │ ~13GB VRAM              │  │ ~4GB VRAM                       │  │
│  │ Orchestrator model      │  │ Finance specialist              │  │
│  │ - Conversation          │  │ - Transaction analysis          │  │
│  │ - Intent classification │  │ - Spending insights             │  │
│  │ - Consent enforcement   │  │ - Category breakdown            │  │
│  │ - Response generation   │  │ - JSON output                   │  │
│  └─────────────────────────┘  └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Services & Ports

| Service | Port | Purpose | Status |
|---------|------|---------|--------|
| MemLayer | 8000 | Long-term memory, vector search | ✅ Running |
| SOA1 API | 8001 | Main API, chat, PDF upload | ✅ Running |
| SOA1 Web Interface | 8002 | Standalone chat interface | ✅ Running |
| Service Monitor | 8003 | Service status dashboard | ✅ Running |
| WebUI Dashboard | 8080 | Main user interface | ✅ Running |
| Ollama | 11434 | LLM inference | ✅ Running |

---

## Data Flow: PDF Upload to Analysis

### Step 1: Upload (with LLM Response)
```
User uploads PDF → POST /upload-pdf
                 → File saved to finance-agent/data/uploads/
                 → Document metadata saved to SQLite (documents table)
                 → Analysis job created (status: "pending")
                 → SOA1Agent.ask() called with document context
                 → NemoAgent generates contextual acknowledgment
                 → Returns: {status: "UPLOADED", doc_id, filename, pages, 
                            agent_response: "I've received [filename]..."}
```

**Key Design Decision (Session 15):** Upload response is generated by LLM, not hardcoded frontend strings. This ensures:
- Consistent, natural communication style
- Adherence to orchestrator.md guidelines
- Single source of truth (backend)
- Works for all clients (web, mobile, CLI)

### Step 2: Chat Engagement
```
User: "I uploaded a statement"
      ↓
POST /api/chat → SOA1Agent.ask()
              → Memory search for context
              → Document context injected via [DOCUMENT CONTEXT] block
              → NemoAgent generates response
              ↓
Response: "I've received [filename]. You can:
          • ask a specific question
          • get a quick summary
          • request a detailed spending analysis
          Nothing happens unless you say so."
```

### Step 3: Analysis Request
```
User: "analyze my spending"
      ↓
NemoAgent: "I can analyze your transactions and show you:
           • Spending breakdown by category
           • Top merchants and patterns
           • Potential insights
           Do you want me to proceed?"
```

### Step 4: User Consent
```
User: "yes"
      ↓
NemoAgent response includes: [INVOKE:phinance]
                            ↓
agent.py detects [INVOKE:phinance] tag
                            ↓
_invoke_phinance() called → Loads transactions from SQLite
                          → Calls phinance-json model
                          → Formats response
                          ↓
User sees: "Here's what I found from analyzing N transactions:
           📊 Total Spending: $X,XXX
           💰 By Category: ...
           🏪 Top Merchants: ...
           Would you like more details?"
```

### Step 5: Full Pipeline (via WebUI)
```
POST /analyze-stage-ab → Metadata preview (headers, institution)
                       ↓
POST /api/consent     → Grants consent for phinance specialist
                       ↓
POST /analyze-confirm → Background thread starts analysis
                       ↓
Background Thread:
  1. FinanceStatementParser extracts transactions
  2. Transactions saved to SQLite
  3. Phinance model generates insights
  4. Reports saved to finance-agent/data/reports/{doc_id}/
  5. Job status updated to "completed"
                       ↓
GET /analysis-status/{doc_id} → Poll until completed
                       ↓
Results available in consolidated dashboard
```

---

## Key Files

### SOA1 Core
| File | Purpose |
|------|---------|
| `home-ai/soa1/api.py` | FastAPI server, all HTTP endpoints |
| `home-ai/soa1/agent.py` | SOA1Agent class, query handling, [INVOKE:phinance] detection |
| `home-ai/soa1/model.py` | ModelClient for Ollama calls |
| `home-ai/soa1/models.py` | Phinance model calls with validation |
| `home-ai/soa1/orchestrator.py` | Consent state management |
| `home-ai/soa1/memory.py` | MemLayer client |
| `home-ai/soa1/prompts/orchestrator.md` | System prompt (model-agnostic) |
| `home-ai/soa1/config.yaml` | Model and service configuration |

### Finance Agent
| File | Purpose |
|------|---------|
| `home-ai/finance-agent/src/storage.py` | SQLite operations for all tables |
| `home-ai/finance-agent/src/parser.py` | FinanceStatementParser for PDF extraction |
| `home-ai/finance-agent/src/models.py` | Finance-specific LLM calls |

### WebUI
| File | Purpose |
|------|---------|
| `soa-webui/main.py` | FastAPI dashboard, analysis pipeline |
| `soa-webui/reports.py` | Consolidated reports API |
| `soa-webui/templates/index.html` | Chat interface |
| `soa-webui/templates/consolidated_dashboard.html` | Finance dashboard |

---

## Database Schema (SQLite)

**File**: `/home/ryzen/projects/home-ai/finance-agent/data/finance.db`

### Tables

```sql
-- Document uploads
documents (
  document_id TEXT PRIMARY KEY,
  filename TEXT,
  pages INTEGER,
  bytes INTEGER,
  upload_ts TEXT
)

-- Analysis job tracking
analysis_jobs (
  job_id TEXT PRIMARY KEY,
  doc_id TEXT UNIQUE,
  status TEXT,           -- pending, running, completed, failed
  started_at TEXT,
  completed_at TEXT,
  error TEXT,
  consent_given INTEGER, -- 0 or 1
  confirmed_specialist TEXT,
  phinance_raw_response TEXT,
  phinance_sanitized TEXT
)

-- Extracted transactions
transactions (
  id INTEGER PRIMARY KEY,
  user_id TEXT,
  doc_id TEXT,           -- Links to document
  date TEXT,
  description TEXT,
  amount REAL,
  category TEXT,
  merchant TEXT,
  raw_merchant TEXT,
  created_at TIMESTAMP
)

-- Chat history persistence
chat_history (
  id INTEGER PRIMARY KEY,
  session_id TEXT,
  user_id TEXT,
  role TEXT,             -- user or assistant
  content TEXT,
  created_at TIMESTAMP
)
```

---

## Logging

### Log Locations
- SOA1 logs: `/home/ryzen/projects/home-ai/soa1/logs/`
- WebUI logs: `/home/ryzen/projects/soa-webui/logs/`
- Model call logs: `logs/model_calls.jsonl`
- Runtime logs: `/tmp/soa1.log`, `/tmp/webui.log`

### Model Call Logging (JSONL)

Structured logging for all LLM interactions in `logs/model_calls.jsonl`:

| Field | Description |
|-------|-------------|
| `timestamp_utc` | ISO 8601 timestamp |
| `correlation_id` | Unique ID linking request/response pairs (e.g., `req-33a290ddd07b`) |
| `attempt` | Retry attempt number (1-based, for retry scenarios) |
| `model_name` | Model identifier (e.g., `NemoAgent:latest`, `phinance-json:latest`) |
| `prompt_source` | Source identifier (`nemoagent`, `phinance`) |
| `prompt_type` | `request`, `response`, or `error` |
| `latency_ms` | Response time in milliseconds |
| `prompt_preview` | Truncated prompt (redacted by default) |
| `prompt_hash` | SHA-256 hash for correlation without exposing content |

### What Gets Logged

| Event | Level | Content |
|-------|-------|---------|
| API requests | INFO | Client IP, endpoint, method |
| Model calls | INFO | Model name, latency, correlation_id, attempt |
| [INVOKE] detection | INFO | "Detected [INVOKE:phinance] signal - routing to phinance" |
| Memory operations | INFO/WARN | Search results, write failures |
| PDF processing | INFO | Pages processed, transaction count |
| Errors | ERROR | Full stack traces |

### Sensitive Data Redaction

The `RedactingFormatter` in `logging_utils.py` automatically masks:
- Credit card numbers: `1234-5678-9012-3456` → `****3456`
- SSNs: `123-45-6789` → `***-**-6789`
- Emails: `user@example.com` → `u***r@example.com`

---

## Fail-Safes & Error Handling

### Consent Enforcement
- `orchestrator.py` tracks consent state
- Specialists cannot be invoked without `consent_given=1` in database
- Upload does NOT grant consent
- Silence does NOT grant consent

### Memory Graceful Degradation
```python
# In agent.py
try:
    memories = self.memory.search_memory(query)
except Exception as e:
    logger.warning(f"Memory search failed (continuing without): {e}")
    memories = []  # Continue without memory
```

### Model Call Retries
- `call_phinance()` supports retry with validation feedback
- Max 3 attempts by default
- Validation errors provide feedback prompt for retry

### Database Error Handling
- `CREATE TABLE IF NOT EXISTS` for idempotent schema creation
- `INSERT OR REPLACE` for upserts
- Connection context managers ensure cleanup

### Service Isolation
- Each service runs independently
- Health endpoints for status checking
- Service failures don't cascade

---

## Configuration

### SOA1 Config (`home-ai/soa1/config.yaml`)
```yaml
model:
  provider: "ollama"
  base_url: "http://localhost:11434"
  model_name: "NemoAgent:latest"
  temperature: 0.3
  max_tokens: 512
  num_ctx: 32768

specialists:
  finance:
    enabled: true
    model_name: "phinance-json:latest"
    temperature: 0.05
```

### WebUI Config (`soa-webui/config.yaml`)
```yaml
services:
  api: "http://localhost:8001"
  memlayer: "http://localhost:8000"

tailscale:
  enabled: true
  allowed_ips:
    - "100.64.0.0/10"
```

---

## Commands Reference

### Start Services
```bash
# SOA1 API
cd /home/ryzen/projects/home-ai/soa1
PYTHONPATH=/home/ryzen/projects nohup python3 api.py > /tmp/soa1.log 2>&1 &

# WebUI
cd /home/ryzen/projects/soa-webui
nohup python3 main.py > /tmp/webui.log 2>&1 &
```

### Check Status
```bash
curl http://localhost:8001/health  # SOA1 API
curl http://localhost:8080/health  # WebUI
ollama ps                          # Loaded models
```

### Test Chat
```bash
curl -X POST http://localhost:8001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "hello"}'
```

### View Logs
```bash
tail -100 /tmp/soa1.log
tail -f /home/ryzen/projects/soa-webui/logs/soa-webui.log
```

---

## Current Status (January 1, 2026)

### ✅ Working
- PDF upload and document tracking
- Chat interface with progressive engagement
- Consent-gated analysis flow
- [INVOKE:phinance] tag detection and routing
- Transaction extraction pipeline
- Consolidated finance dashboard
- LLM response validation with retry
- Chat history persistence
- Cross-document comparison
- Merchant normalization (40+ patterns)
- Security hardening (XSS, path traversal)

### ⚠️ Known Issues
- Existing transactions need `doc_id` migration (fixed Jan 1, 2026)
- MemLayer connection may fail (graceful degradation in place)

### 🔜 Planned
- Budgeting specialist
- Knowledge specialist  
- Scheduler specialist
- Voice interface (TTS)
- Mobile companion app

---

## Related Documentation

- `RemAssist/IMPLEMENTATION_GUIDE.md` - Core invariants, consent rules
- `RemAssist/History.md` - Session history, changes made
- `RemAssist/NEXT_TASKS.md` - Task queue
- `RemAssist/errors.md` - Error tracking log
- `home-ai/ARCHITECTURE.md` - Detailed system architecture
- `AGENTS.md` - AI agent guidelines

---

*This document reflects the current project state. Update after significant changes.*
