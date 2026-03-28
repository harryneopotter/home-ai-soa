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
   - SOA Orchestrator (`home-ai/soa1`) MUST NOT invoke specialists without explicit consent (see `IMPLEMENTATION_GUIDE.md`)
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

### Phinance Context Window — DO NOT CHANGE
- **`num_ctx`: 4096** (set in `home-ai/soa1/models.py` line ~549)
- Prompt sends **aggregated summaries only**, not raw transactions
- Typical usage: ~1000 tokens (system + user + response)
- Analyzed Jan 6, 2026: 4K provides 3K+ headroom, 32K was massive overkill
- **DO NOT increase** — wastes VRAM, no benefit

---

## 📋 Session Documentation

After every session/compaction, update:

1. **`RemAssist/History.md`** — What was accomplished, decisions made
2. **`RemAssist/NEXT_TASKS.md`** — Mark done, add new tasks

### Update Frequency Rule (Mandatory)

- ALWAYS update `RemAssist/History.md` and `RemAssist/NEXT_TASKS.md` after every **2–3 completed tasks**, even if the session is not “done” yet.
- If a task is blocked or deferred, record it immediately in `RemAssist/NEXT_TASKS.md` (do not wait for the end of the session).

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
- Do NOT relax enforcement for "UX smoothness"
- **MUST check `HARDWARE_SPECS.md`** before adding models/GPU features

---

## 📍 Current Status (2026-03-28)

- Planning consolidated under `plan/future-plans/feb/` (merged modular plan + addenda + critique).
- Roadmap for “robust chat agent + two tools (finance + medical)” captured in `plan/future-plans/feb/ROBUST_CHAT_AGENT_TWO_TOOLS_PLAN.md` and `plan/future-plans/feb/NEXT_IMPLEMENTATION_ROADMAP.md`.
- Specialist routing scaffold exists under `home-ai/soa1/specialist/` (not fully wired into the main chat path yet).
