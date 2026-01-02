# AGENTS.md — Project Guidelines for AI Agents

## 🔒 Constitutional Documents (MUST READ FIRST)

Before making ANY changes to the `home-ai/` project, agents MUST read and follow:

1. **`RemAssist/IMPLEMENTATION_GUIDE.md`** — Core invariants and consent-first rules
   - User agency is paramount
   - NO specialist invocation without explicit consent
   - Silence ≠ consent, Upload ≠ consent
   - Forbidden language patterns (no "I'll proceed...", "I'll go ahead...")

2. **`RemAssist/FILE_CHECKLISTS.md`** — Implementation order and file responsibilities
   - One file per iteration
   - Implementation order is mandatory
   - Each file has strict boundaries (must contain / must not do)

3. **`RemAssist/LLM_DRIVEN_RESPONSES.md`** — User-facing communication principle
   - ALL user-facing text MUST come from LLM, not hardcoded strings
   - Upload responses, errors, status updates → route through agent
   - Frontend displays API response as-is, no fallback strings
   - Prevents communication fragmentation across codebase

**If there is ANY conflict: `IMPLEMENTATION_GUIDE.md` overrides everything.**

---

## 📐 Architecture Reference Documents

- **`RemAssist/PROGRESSIVE_BATCH_ARCHITECTURE.md`** — Next major feature: 5-phase batch upload pipeline
  - Parallel processing, background analysis, output pre-generation
  - Security layer with PII redaction and AES-256 encryption
  - Implementation roadmap and code examples
  
- **`home-ai/ARCHITECTURE.md`** — Current system architecture
- **`RemAssist/PROJECT_STATE.md`** — Comprehensive project state snapshot
- **`RemAssist/HARDWARE_SPECS.md`** — System hardware specs and resource limits
  - **MUST CHECK** before adding models or GPU-intensive features
  - Contains VRAM budget, model size limits, resource planning matrix

---

## ⚠️ Critical Design Decisions

### Orchestrator = Model-Agnostic (NO Modelfile)

**DO NOT create `.modelfile` for the orchestrator (NemoAgent or any replacement).**

- User will swap orchestrator models frequently for testing
- System prompt must be **model-agnostic** and loaded at runtime
- Store orchestrator prompt at: `home-ai/soa1/prompts/orchestrator.md`
- Pass prompt via Ollama API `system` parameter, not baked into model

**phinance-json DOES use a Modelfile** (it's a fixed specialist, not swappable).

### LLM-Driven Responses (NO Hardcoded User Messages)

**DO NOT add hardcoded user-facing strings in frontend or backend.**

- All responses displayed to user must originate from `SOA1Agent.ask()`
- API endpoints return `agent_response` field with LLM-generated text
- Frontend displays `data.agent_response` directly
- See `RemAssist/LLM_DRIVEN_RESPONSES.md` for full explanation and anti-patterns

---

## 📋 Session Documentation Requirements

After every **compact action** (context compaction/session summary), agents MUST update:

1. **`RemAssist/History.md`** — Append a dated entry summarizing:
   - What was accomplished
   - Key decisions made
   - Files created/modified

2. **`RemAssist/NEXT_TASKS.md`** — Update with:
   - Mark completed tasks as done
   - Add any new tasks discovered
   - Reprioritize if needed

This ensures continuity across sessions and prevents knowledge loss during context compaction.

---

## 🐛 Error Tracking Ritual (MANDATORY)

When encountering errors during development, agents MUST:

1. **Log the error** in `RemAssist/errors.md`:
   - Date and brief title
   - Exact error message/traceback
   - Context of what was being attempted
   - Initial assessment of root cause

2. **After fixing**, update the same entry with:
   - Confirmed root cause
   - What was changed to fix it
   - Status: ✅ RESOLVED

3. **Template** (copy from `RemAssist/errors.md`):
   ```markdown
   ### YYYY-MM-DD: Brief Error Title
   **Error:** `exact error message`
   **Context:** What operation was being performed
   **Root Cause:** Technical explanation
   **Fix Applied:** Changes made
   **Status:** ✅ RESOLVED | 🔄 IN PROGRESS | ❌ BLOCKED
   ```

This creates an institutional memory of issues and solutions for future sessions.

---

## 🚫 Hard Rules

- **Respect user agency over speed**
- **Prefer waiting over guessing**
- **Prefer asking over acting**
- **If uncertain: ASK**
- Do NOT invent new intents
- Do NOT auto-trigger specialists
- Do NOT optimize away consent

- **MUST check `RemAssist/HARDWARE_SPECS.md`** before proposing new models or GPU-intensive features
