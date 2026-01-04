# AGENTS.md — Project Guidelines for AI Agents

## Quick Reference: When to Read What

| If your task involves... | Read this FIRST |
|--------------------------|-----------------|
| **Any code change** | `RemAssist/IMPLEMENTATION_GUIDE.md` (consent rules) |
| **Batch upload / file upload / analysis** | `RemAssist/PROGRESSIVE_FLOW.md` ⭐ CANONICAL |
| **User-facing text / responses** | `RemAssist/LLM_DRIVEN_RESPONSES.md` |
| **Adding models / GPU features** | `RemAssist/HARDWARE_SPECS.md` (VRAM limits) |
| **Security / PII / encryption** | `RemAssist/PROGRESSIVE_BATCH_ARCHITECTURE.md` (security section) |
| **Understanding current state** | `RemAssist/PROJECT_STATE.md` |
| **What to work on next** | `RemAssist/NEXT_TASKS.md` |

---

## 🔒 Constitutional Documents (MUST READ)

**If there is ANY conflict: `IMPLEMENTATION_GUIDE.md` overrides everything.**

1. **`RemAssist/IMPLEMENTATION_GUIDE.md`** — Core invariants
   - User agency is paramount
   - NO specialist invocation without explicit consent
   - Silence ≠ consent, Upload ≠ consent

2. **`RemAssist/LLM_DRIVEN_RESPONSES.md`** — Communication principle
   - ALL user-facing text comes from LLM, never hardcoded

3. **`RemAssist/PROGRESSIVE_FLOW.md`** — Upload/batch/analysis flow ⭐ CANONICAL
   - 4-phase progressive pipeline with background processing
   - Transactions extracted by Python regex, NOT LLM
   - Transactions saved to DB ONLY after consent
   - Pre-generate outputs while user reads
   - **READ THIS FIRST** before touching upload, batch, or analysis code

---

## 📐 Architecture References

| Document | Purpose |
|----------|---------|
| `RemAssist/PROJECT_STATE.md` | Current system state, services, ports, data flow |
| `RemAssist/PROGRESSIVE_BATCH_ARCHITECTURE.md` | Full technical spec for batch pipeline + security |
| `RemAssist/HARDWARE_SPECS.md` | VRAM budget, model limits — **check before adding models** |
| `home-ai/ARCHITECTURE.md` | System architecture diagrams |

---

## ⚠️ Critical Design Decisions

### Orchestrator = Model-Agnostic
- **NO `.modelfile`** for orchestrator (NemoAgent)
- System prompt at: `home-ai/soa1/prompts/orchestrator.md`
- Pass via Ollama API `system` parameter at runtime

### LLM-Driven Responses
- **NO hardcoded user-facing strings**
- All responses via `SOA1Agent.ask()` → `agent_response` field
- See `RemAssist/LLM_DRIVEN_RESPONSES.md`

### Batch Upload Flow
- **Return immediately, process in background, poll for status**
- See `RemAssist/PROGRESSIVE_FLOW.md` for the 4-phase pipeline
- Key: Python regex extracts transactions, LLM provides insights only

---

## 📋 Session Documentation

After every session/compaction, update:

1. **`RemAssist/History.md`** — What was accomplished, decisions made
2. **`RemAssist/NEXT_TASKS.md`** — Mark done, add new tasks

---

## 🐛 Error Tracking

Log errors to `RemAssist/errors.md`:

```markdown
### YYYY-MM-DD: Brief Title
**Error:** `exact message`
**Context:** What was attempted
**Root Cause:** Explanation
**Fix Applied:** Changes made
**Status:** ✅ RESOLVED | 🔄 IN PROGRESS | ❌ BLOCKED
```

---

## 🚫 Hard Rules

- Respect user agency over speed
- Prefer waiting over guessing
- Prefer asking over acting
- If uncertain: ASK
- Do NOT invent new intents
- Do NOT auto-trigger specialists
- Do NOT optimize away consent
- **MUST check `HARDWARE_SPECS.md`** before adding models/GPU features
