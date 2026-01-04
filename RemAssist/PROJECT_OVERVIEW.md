# Home AI Project — Comprehensive Overview

**Document Version**: 1.0  
**Last Updated**: January 3, 2026  
**Author**: System-generated from project documentation

---

## Table of Contents

1. [Vision & Goals](#1-vision--goals)
2. [Current State](#2-current-state)
3. [What We've Built](#3-what-weve-built)
4. [How It Works](#4-how-it-works)
5. [What's Next](#5-whats-next)
6. [Hardware & Infrastructure](#6-hardware--infrastructure)
7. [Key Design Decisions](#7-key-design-decisions)
8. [Session History](#8-session-history)

---

## 1. Vision & Goals

### The Core Vision

**SOA1 (Son of Anton)** is a **local-first, privacy-focused home AI assistant** that runs entirely on consumer hardware with zero cloud dependencies. The system is designed to be a personal AI that:

- **Knows you** — Learns preferences, patterns, and context over time
- **Respects you** — Never acts without explicit consent
- **Helps you** — Provides intelligent assistance across multiple domains
- **Protects you** — All data stays local, encrypted, under your control

### Core Principles

| Principle | Description |
|-----------|-------------|
| **Privacy-First** | 100% local processing, no cloud APIs, no data leaving your machine |
| **Consent-Based** | No specialist actions without explicit user confirmation |
| **User Agency** | Silence ≠ consent; user always controls what happens |
| **LLM-Driven Communication** | All user-facing responses come from LLM, never hardcoded |

### Long-Term Vision

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    FUTURE STATE: MULTI-AGENT HOME AI                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  User ←→ Orchestrator (NemoAgent) ←→ Specialist Agents                  │
│                 ↕                                                        │
│            Shared Memory (Graph + Vector)                                │
│                 ↕                                                        │
│        Night Audit System (Self-Correcting)                             │
│                                                                          │
│  Specialists:                                                            │
│  ├─ Finance Agent (phinance) ✅ BUILT                                   │
│  ├─ Calendar Agent          🔜 PLANNED                                  │
│  ├─ Research Agent          🔜 PLANNED                                  │
│  ├─ Budgeting Agent         🔜 PLANNED                                  │
│  ├─ Knowledge Agent         🔜 PLANNED                                  │
│  └─ Home Automation Agent   🔜 PLANNED                                  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Current State

### System Status (January 3, 2026)

| Component | Status | Port | Purpose |
|-----------|--------|------|---------|
| SOA1 API | ✅ Running | 8001 | Main API, chat, PDF upload |
| WebUI | ✅ Running | 8080 | User interface dashboard |
| MemLayer | ✅ Running | 8000 | Long-term memory (vector store) |
| Ollama | ✅ Running | 11434 | LLM inference |
| Service Monitor | ✅ Running | 8003 | Health monitoring |

### Loaded Models

| Model | GPU | VRAM | Purpose |
|-------|-----|------|---------|
| NemoAgent | GPU 0 | ~10.7 GB | Orchestrator (conversation, intent, consent) |
| phinance-json | GPU 1 | ~10.8 GB | Finance specialist (transaction analysis) |

### What's Working

- ✅ PDF upload and document tracking
- ✅ Chat interface with progressive engagement
- ✅ Consent-gated specialist invocation
- ✅ Transaction extraction pipeline
- ✅ Hybrid calculation (Python math + LLM insights)
- ✅ Consolidated finance dashboard
- ✅ Batch upload with 5-phase pipeline
- ✅ Full batch persistence (gzip compressed)
- ✅ Chat history persistence
- ✅ Merchant normalization (40+ patterns)
- ✅ Rate limiting on all endpoints
- ✅ Security hardening (XSS, path traversal)

### Known Issues

- ⚠️ MemLayer connection may fail (graceful degradation in place)
- ⚠️ Memory architecture needs upgrade (flat vector → graph)

---

## 3. What We've Built

### 3.1 Finance Analysis Pipeline

The first complete specialist domain — PDF statement analysis with transaction extraction and insights.

```
User uploads PDF
       ↓
┌──────────────────────────────────────────────────────────────┐
│ Phase 1: Upload & Parse (< 30ms response)                     │
│ - File saved to uploads/                                      │
│ - Metadata extracted (pages, size, institution)              │
│ - LLM generates contextual acknowledgment                     │
└──────────────────────────────────────────────────────────────┘
       ↓
┌──────────────────────────────────────────────────────────────┐
│ Phase 2: Intent Confirmation                                  │
│ - NemoAgent asks what user wants                             │
│ - Options presented (analyze, summarize, specific question)  │
│ - User must explicitly confirm                                │
└──────────────────────────────────────────────────────────────┘
       ↓
┌──────────────────────────────────────────────────────────────┐
│ Phase 3: Consent Gate                                         │
│ - [INVOKE:phinance] tag detected in response                 │
│ - Consent recorded in database                                │
│ - Only then does specialist activate                          │
└──────────────────────────────────────────────────────────────┘
       ↓
┌──────────────────────────────────────────────────────────────┐
│ Phase 4: Hybrid Analysis                                      │
│ - Python calculates: totals, categories, merchants (0.05ms)  │
│ - LLM generates: insights, patterns, recommendations (5-6s)  │
│ - Combined: 100% accurate math + quality narrative           │
└──────────────────────────────────────────────────────────────┘
       ↓
┌──────────────────────────────────────────────────────────────┐
│ Phase 5: Output Delivery                                      │
│ - Dashboard view (interactive charts)                         │
│ - PDF report (downloadable)                                   │
│ - Infographic (visual summary)                               │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 Batch Upload System

Multi-file upload with progressive processing and persistence.

**Key Features**:
- Upload multiple PDFs in one request
- Background processing with status polling
- Compressed text storage (~98% compression ratio)
- Startup recovery (hydrates incomplete batches from DB)
- Session-based batch tracking for page refresh recovery

**Database Schema** (SQLite):
```sql
batches (batch_id, session_id, status, created_at, completed_at)
documents (document_id, filename, pages, bytes, upload_ts)
transactions (id, user_id, doc_id, date, description, amount, category, merchant)
analysis_jobs (job_id, doc_id, status, phinance_raw_response, phinance_sanitized)
chat_history (id, session_id, user_id, role, content, created_at)
```

### 3.3 Security & Rate Limiting

| Endpoint | Limit | Purpose |
|----------|-------|---------|
| `/upload-batch`, `/upload-pdf` | 10/min | Prevent upload abuse |
| `/ask-with-tts` | 20/min | Protect TTS resources |
| All other endpoints | 100/min | General API protection |

**Input Validation**:
- Max message length: 10,000 chars
- Max file size: 10 MB
- Max batch_id length: 100 chars

### 3.4 Logging & Observability

**Model Call Logging** (JSONL format):
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

**Sensitive Data Redaction**:
- Credit card numbers: `1234-5678-9012-3456` → `****3456`
- SSNs: `123-45-6789` → `***-**-6789`
- Emails: `user@example.com` → `u***r@example.com`

---

## 4. How It Works

### 4.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                               │
│  WebUI (8080) ──────────────────────────────────────────────────────│
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         SOA1 API (8001)                              │
│  FastAPI server with session tracking and consent enforcement       │
│  Endpoints: /upload-pdf, /api/chat, /api/consent, /health          │
└─────────────────────────────────────────────────────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│ SOA1 Agent      │  │ MemLayer (8000)     │  │ SQLite Database     │
│ (agent.py)      │  │ Long-term memory    │  │ finance.db          │
│                 │  │ Vector search       │  │ - documents         │
│ - Query handler │  └─────────────────────┘  │ - transactions      │
│ - Memory search │                           │ - analysis_jobs     │
│ - [INVOKE] tag  │                           │ - chat_history      │
│   detection     │                           └─────────────────────┘
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         OLLAMA (11434)                               │
│  ┌─────────────────────────┐  ┌─────────────────────────────────┐   │
│  │ NemoAgent (GPU 0)       │  │ phinance-json (GPU 1)           │   │
│  │ Orchestrator model      │  │ Finance specialist               │   │
│  │ - Conversation          │  │ - Transaction analysis           │   │
│  │ - Intent classification │  │ - Spending insights              │   │
│  │ - Consent enforcement   │  │ - JSON output                    │   │
│  └─────────────────────────┘  └─────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Key Files

| File | Purpose |
|------|---------|
| `home-ai/soa1/api.py` | FastAPI server, all HTTP endpoints |
| `home-ai/soa1/agent.py` | SOA1Agent class, [INVOKE:phinance] detection |
| `home-ai/soa1/models.py` | Phinance model calls with validation |
| `home-ai/soa1/orchestrator.py` | Consent state management |
| `home-ai/soa1/prompts/orchestrator.md` | System prompt (model-agnostic) |
| `home-ai/soa1/utils/financial_calculator.py` | Python calculation utilities |
| `home-ai/finance-agent/src/storage.py` | SQLite operations |
| `home-ai/finance-agent/src/parser.py` | PDF extraction |
| `soa-webui/main.py` | FastAPI dashboard |
| `soa-webui/templates/index.html` | Chat interface |

### 4.3 Data Flow Example: "Analyze my spending"

```
1. User: "analyze my spending"
        ↓
2. POST /api/chat → SOA1Agent.ask()
        ↓
3. Memory search for context (documents, history)
        ↓
4. NemoAgent response: "I can analyze your transactions... 
   Do you want me to proceed?"
        ↓
5. User: "yes"
        ↓
6. NemoAgent response includes: [INVOKE:phinance]
        ↓
7. agent.py detects tag → _invoke_phinance() called
        ↓
8. Python calculates totals, categories, merchants (0.05ms)
        ↓
9. qwen2.5 generates insights (5-6s)
        ↓
10. Combined response delivered to user
```

### 4.4 Hybrid Calculation Architecture

**Why Hybrid?** LLMs can't do math reliably. They process tokens, not numbers.

| Component | Role | Speed | Accuracy |
|-----------|------|-------|----------|
| Python | Calculate totals, categories, top merchants | 0.05ms | 100% |
| qwen2.5:7b | Generate insights, patterns, recommendations | 5-6s | Qualitative |

**Result**: 6.3s total, accurate numbers + quality narrative.

---

## 5. What's Next

### 5.1 Immediate Priority: Memory Architecture Upgrade

**Current State**: MemLayer (flat vector search)
- Stores facts as single vectors
- Simple similarity search
- No relationships between concepts

**Target State**: Graph-based memory (MyCelium-style)
- Entities + relationships in a graph (NetworkX)
- Vector embeddings for similarity
- Hybrid retrieval (BFS + vector)
- LLM-based entity extraction

**Why This Matters**:
- Better context retrieval ("Where do I shop for food?" → traverses grocery merchants)
- Cross-agent knowledge sharing
- Foundation for night audits (review entity/relation quality)
- Richer answers to relational queries

**Plan Created**: `/home/ryzen/projects/plan/memory/mycelium-local-adaptation.md`

### 5.2 Self-Correcting Night Audit System

**Concept**: Use idle system resources to review and improve decisions.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DAYTIME OPERATIONS (Fast 7B models)               │
│  All agent actions logged with confidence scores                     │
└─────────────────────────────────────────────────────────────────────┘
                          ↓ (when system idle)
┌─────────────────────────────────────────────────────────────────────┐
│               NIGHTTIME AUDIT (Thorough 14-32B models)               │
│  Review day's decisions, find errors, update RAG, prune logs        │
└─────────────────────────────────────────────────────────────────────┘
```

**Key Features**:
- Resource monitoring (CPU, GPU, RAM every 5 mins)
- Learn quiet hours pattern over time
- Only wake up big models when system truly idle
- Three-tier audit: 14B → 32B → Human review
- Automatic correction + RAG updates

**Plan Created**: `/home/ryzen/projects/plan/future-plans/self-correcting-mechanism.md`

### 5.3 Quick Win: Slim Prompt + Dynamic Injection

**Problem**: Orchestrator doesn't know system state well enough.

**Solution**:
1. Reduce base system prompt to essentials
2. Dynamically inject context at query time:
   - Currently loaded models
   - Available specialists
   - User's recent activity
   - Relevant memories

**Benefit**: Agent is context-aware without stuffing the prompt.

### 5.4 Additional Specialists (Future)

| Specialist | Purpose | Priority |
|------------|---------|----------|
| Budgeting Agent | Monthly budgets, goals, tracking | High |
| Calendar Agent | Scheduling, reminders, conflicts | Medium |
| Research Agent | Web search, document analysis | Medium |
| Knowledge Agent | Facts, trivia, explanations | Low |
| Home Automation | Lights, thermostats, devices | Low |

---

## 6. Hardware & Infrastructure

### System Specs

| Component | Specification |
|-----------|---------------|
| **CPU** | Intel Core i5-12600K (10 cores, 16 threads) |
| **RAM** | 128 GB DDR5 |
| **GPU 0** | NVIDIA RTX 5060 Ti (16 GB VRAM) |
| **GPU 1** | NVIDIA RTX 5060 Ti (16 GB VRAM) |
| **Storage** | 2x 1TB WD BLACK SN770 NVMe |
| **OS** | Ubuntu 22.04.5 LTS |

### Resource Budget

| Resource | Total | Used | Available |
|----------|-------|------|-----------|
| CPU | 16 threads | ~2 | 14 |
| RAM | 128 GB | ~5 GB | 119 GB |
| GPU 0 VRAM | 16 GB | 10.7 GB | 5.3 GB |
| GPU 1 VRAM | 16 GB | 10.8 GB | 5.2 GB |

### Model Size Limits

```
< 3 GB        ✅ Fits easily on either GPU
3-5 GB        ✅ Yes, but choose GPU carefully
5-8 GB        ⚠️ May need to evict a model
8-16 GB       ⚠️ Requires dedicated GPU
16-32 GB      ❌ Needs both GPUs
> 32 GB       ❌ Cannot fit
```

---

## 7. Key Design Decisions

### 7.1 Orchestrator is Model-Agnostic

- **NO `.modelfile`** for orchestrator (NemoAgent)
- System prompt lives at: `home-ai/soa1/prompts/orchestrator.md`
- Passed via Ollama API `system` parameter at runtime
- Allows swapping models without rebuilding

### 7.2 LLM-Driven Responses

- **NO hardcoded user-facing strings**
- All responses via `SOA1Agent.ask()` → `agent_response` field
- Ensures consistent, natural communication
- Works for all clients (web, mobile, CLI)

### 7.3 Consent Enforcement

- Upload does NOT grant consent
- Silence does NOT grant consent
- User must explicitly confirm before specialist activation
- Consent tracked in database per session

### 7.4 Hybrid Calculation

- Python handles all arithmetic (100% accurate)
- LLM handles qualitative insights only
- Prevents hallucinated numbers while keeping narrative quality

---

## 8. Session History

### Recent Sessions (January 2026)

| Session | Date | Focus | Key Accomplishments |
|---------|------|-------|---------------------|
| 26 | Jan 3 | Memory Architecture | KV cache research (not viable), MyCelium plan created |
| 25 | Jan 3 | Batch Persistence | Full persistence with gzip compression, startup hydration |
| 24 | Jan 3 | Batch Persistence | Session-based batch tracking, proxy fix |
| 23 | Jan 2 | Hybrid Calculation | Python math + LLM insights architecture |
| 22 | Jan 2 | Documentation | HARDWARE_SPECS.md created |
| 21 | Jan 2 | Bug Fixes | Tuple unpacking fix, input validation |
| 20 | Jan 2 | Security | Rate limiting implemented |

### Earlier Sessions (December 2025)

| Session | Focus |
|---------|-------|
| 13 | Chat history persistence, merchant normalization |
| 12 | Parallel batch processing, transaction caching |
| 11 | XSS fixes, path traversal protection |
| 10 | Consolidated dashboard, Pydantic validation |
| 9 | GPU eviction fix, batch testing |

---

## Quick Reference

### Start Services
```bash
cd /home/ryzen/projects/home-ai/soa1
PYTHONPATH=/home/ryzen/projects nohup python3 api.py > /tmp/soa1.log 2>&1 &

cd /home/ryzen/projects/soa-webui
nohup python3 main.py > /tmp/webui.log 2>&1 &
```

### Check Status
```bash
curl http://localhost:8001/health  # SOA1 API
curl http://localhost:8080/health  # WebUI
ollama ps                          # Loaded models
nvidia-smi                         # GPU status
```

### Key Documents

| Document | Purpose |
|----------|---------|
| `RemAssist/PROJECT_STATE.md` | Current system state |
| `RemAssist/NEXT_TASKS.md` | Task queue |
| `RemAssist/IMPLEMENTATION_GUIDE.md` | Core invariants |
| `RemAssist/BATCH_FLOW.md` | 5-phase pipeline |
| `RemAssist/HARDWARE_SPECS.md` | Hardware limits |
| `plan/memory/mycelium-local-adaptation.md` | Memory upgrade plan |

---

*This document provides a comprehensive overview of the Home AI project. For detailed technical specifications, see the individual documents in `RemAssist/` and `plan/`.*
