# M1 — Modular Orchestrator Implementation Plan

## Decisions (Locked for This Plan)

1. **Consent scope:** **Per-batch** (not global, not per-session).
2. **Registration:** Prefer **auto-discovery** of specialists.
3. **Invocation API:** Specialists use **async** invocation.
4. **Persistence:** Consent records go to a **separate SQLite DB** (not finance.db).

---

## Executive Summary

**Goal:** Decouple specialist logic (starting with finance/phinance) so adding new specialists requires **no changes** to core orchestrator logic.

**Current pain points:**
- `agent.py` has hardcoded `[INVOKE:phinance]` detection and direct `_invoke_phinance()` logic.
- Orchestrator intent inference has finance-specific keywords.
- Consent is primarily in-memory and not modeled as a reusable tool-brokering system.

**Target state:**
- Specialists implement a common interface and register via an auto-discovery mechanism.
- A generic router detects and routes `[INVOKE:<specialist>]` tags.
- Consent is enforced via capability checks and **persisted per batch**.
- Prompt instructions are dynamically injected based on available specialists.

---

## Design Notes / Tradeoffs

### Auto-discovery (Preferred) — Tradeoffs

**Benefits**
- Zero central wiring: dropping a new specialist module makes it show up automatically.
- Avoids orchestrator churn: fewer merge conflicts and less “registry editing”.
- Supports plugin-like architecture for future specialists.

**Costs / Risks**
- Import-time side effects: careless specialist modules can do work at import time.
- Startup failures: a broken specialist import can crash discovery if not isolated.
- Debuggability: can be harder to see “what got registered and why” without logs.

**Mitigations**
- Require specialists to be import-safe: no I/O, no network calls in module import.
- Discovery should be defensive: catch exceptions per module, log failures, continue.
- On startup, log a structured list of discovered specialists and their capabilities.

### Async-only invocation — Tradeoffs

**Benefits**
- Aligns with concurrent workflows (background analysis, streaming responses).
- Enables non-blocking specialist invocations (especially long-running).
- Consistent interface for all specialists.

**Costs / Risks**
- Slightly more complexity for simple specialists (“need async even if sync”).
- Requires careful bridging where existing code is sync (thread / executor / wrapper).

**Mitigations**
- Provide an internal utility wrapper for running sync functions in async context.
- For early migration, allow FinanceSpecialist.invoke() to delegate to existing sync paths while returning async-compatible results.

---

## Section C — Guardrails / Non-negotiables

These rules are explicitly required to stay compatible with the frozen Kernel Contract v0.1.

1. **Router gating = CONTROL.allowed_actions + stage (MUST)**
   - Router must validate **`stage == READY`** *and* **`invoke_specialist ∈ CONTROL.allowed_actions`**.
   - **Stage/status checks alone are not sufficient.** Do not rely on batch status strings (e.g. `state.status == "ready"`) as the sole gate.

2. **Per-batch consent must NOT gate implicit upload capabilities (MUST)**
   - Upload implies `READ_UPLOADS` and whatever capabilities have been defined as implicitly granted on upload (currently `READ_UPLOADS` + `ANALYZE_DETERMINISTIC`).
   - This must work **without** reading/writing ConsentManager.
   - ConsentManager is only for **explicit grants / side-effect capabilities**.

3. **Keep “specialist invocation approval” distinct from capability grants (MUST)**
   - Capability grants answer: **“Is this action type allowed?”** (e.g. `WRITE_PERSISTENT`).
   - Invocation approval answers: **“Is invoking specialist X allowed now?”** (per batch).
   - **Do not merge these into one boolean**, or you’ll create bypasses and confusing edge cases.

4. **No keyword-based synthetic invocation (MUST)**
   - No auto “forced invoke” based on trigger words.
   - Specialist invocation must come from explicit orchestrator output (`[INVOKE:x]` or equivalent structured tag) and still pass **router + consent + CONTROL** checks.

---

## Implementation Phases

### Phase 1 — Foundation (Days 1–3)

#### 1. Create `home-ai/soa1/specialist/base.py`
**Deliverable:** A minimal but stable specialist interface.

**Core types:**
- `SpecialistContext` (session_id, batch_id, document_context, capabilities)
- `SpecialistResult` (success, response_text, analysis/artifacts, polling hints)
- `BaseSpecialist` ABC: `name`, `display_name`, `required_capabilities`, `trigger_keywords`, `can_handle()`, `invoke()` (async)

**Success criteria:**
- Specialists can be invoked uniformly without “phinance special casing”.

#### 2. Create `home-ai/soa1/specialist/registry.py`
**Deliverable:** `SpecialistRegistry` singleton.

**Responsibilities:**
- Register specialists by unique `name`
- Lookup and enumerate specialists
- Expose aggregated trigger keywords for intent inference

#### 3. Create `home-ai/soa1/specialist/consent_manager.py`
**Deliverable:** DB-backed capability consent store.

**Key requirement:** consent is **per batch**.

**MUST:** ConsentManager must NOT gate implicit upload capabilities. Upload implies `READ_UPLOADS` (+ other implicitly granted capabilities) without needing ConsentManager. ConsentManager is only for explicit grants / side-effect capabilities.

**API:**

Capabilities (answer: “Is this action type allowed?”)
- `grant_capability(batch_id, specialist, capability, scope='batch')`
- `revoke_capability(batch_id, specialist, capability)`
- `has_capability_consent(batch_id, specialist, capability)`
- `list_capability_consents(batch_id)`

Invocation approval (answer: “Is invoking specialist X allowed now?”)
- `approve_invocation(batch_id, specialist, scope='batch')`
- `revoke_invocation(batch_id, specialist)`
- `is_invocation_approved(batch_id, specialist)`
- `list_invocation_approvals(batch_id)`

**MUST:** Keep invocation approval distinct from capability grants. Do not merge into one boolean.

#### 4. Create a new SQLite DB for SOA1 kernel state
**Deliverable:** A separate `soa1.db` (or similarly named) used by ConsentManager.

**Schema:**
- `consent_capability_records` (batch_id, specialist, capability, granted_at, expires_at, scope)
- `specialist_invocation_approvals` (batch_id, specialist, approved_at, scope)

#### 5. Create `home-ai/soa1/specialists/finance/__init__.py`
**Deliverable:** `FinanceSpecialist` wrapper around the existing phinance path.

**Approach:**
- In the first pass, `FinanceSpecialist.invoke()` may delegate to existing functions in `agent.py` (or extracted helpers) to avoid large refactors.
- Later phases migrate the logic fully into the specialist.

#### 6. Unit tests
**Deliverables:**
- Registry: add/get/error conditions
- ConsentManager: grant/has/revoke for batch scope
- FinanceSpecialist: `required_capabilities`, `trigger_keywords`, basic `can_handle()`

---

### Phase 2 — Router (Days 4–6)

#### 1. Create `home-ai/soa1/specialist/router.py`
**Deliverable:** Generic router for tags like `[INVOKE:<name>]`.

**Responsibilities:**
- Detect invocation tag
- Strip tag from LLM response
- Resolve specialist via registry
- Enforce CONTROL gating (MUST validate `stage == READY` AND `invoke_specialist ∈ CONTROL.allowed_actions`; stage/status alone is insufficient)
- Enforce invocation approval (per batch) and capability consent (explicit/side-effect only)
- **MUST NOT:** synthesize/force invocation based on trigger keywords (no keyword-based synthetic invocation)

#### 2. Add feature flag: `USE_SPECIALIST_ROUTER`
**Deliverable:** Safe rollout path.

#### 3. Wire router into `SOA1Agent.ask()`
**Deliverable:** Replace `INVOKE_PATTERN` usage with router when flag is enabled.

#### 4. Integration tests
**Deliverables:**
- Invokes known specialist successfully
- Unknown specialist handled gracefully
- Missing consent/capability blocks invocation

---

### Phase 3 — Dynamic Prompts (Days 7–9)

#### 1. Add prompt fragments directory
**Deliverable:** `home-ai/soa1/prompts/fragments/`.

#### 2. Add `finance.md` fragment
**Deliverable:** `home-ai/soa1/prompts/fragments/finance.md` with finance-specific usage and invocation guidance.

#### 3. Update `home-ai/soa1/prompts/orchestrator.md`
**Deliverable:** Add placeholder `{{SPECIALIST_INSTRUCTIONS}}`.

#### 4. Update prompt loader
**Deliverable:** `_load_system_prompt()` injects all fragments based on discovered specialists.

#### 5. Remove hardcoded finance keywords
**Deliverable:** Rewrite intent inference to consult registry trigger keywords.

---

### Phase 4 — Cleanup (Days 10–12)

#### 1. Remove old phinance-specific codepaths
**Deliverables:**
- Remove hardcoded `INVOKE_PATTERN` in `agent.py`
- Remove/retire `_invoke_phinance()` and related helpers once migrated
- Remove feature flag and make router default

#### 2. Full test suite + E2E verification
**Deliverables:**
- All tests passing
- E2E upload → ready → analysis invoke → output selection still works

---

## File/Module Deliverables (Planned)

### New
- `home-ai/soa1/specialist/base.py`
- `home-ai/soa1/specialist/registry.py`
- `home-ai/soa1/specialist/consent_manager.py`
- `home-ai/soa1/specialist/router.py`
- `home-ai/soa1/specialists/finance/__init__.py`
- `home-ai/soa1/prompts/fragments/finance.md`
- `home-ai/soa1/tests/test_specialist_base.py`
- `home-ai/soa1/tests/test_router.py`

### Modified
- `home-ai/soa1/agent.py`
- `home-ai/soa1/orchestrator.py`
- `home-ai/soa1/prompts/orchestrator.md`
- `home-ai/soa1/intents.py`

---

## Acceptance Criteria

1. **Adding a new specialist** requires only:
   - New module under `home-ai/soa1/specialists/<name>/` that exports a specialist instance
   - Optional prompt fragment under `prompts/fragments/<name>.md`

2. **No finance special casing** remains in routing logic.

3. **Consent enforcement** is auditable and **per batch** via the kernel DB.

4. CONTROL header invariant remains true:
   - `invoke_specialist` is only allowed when `stage=READY`.

---

## Open Items (For Implementation Time)

- Exact name/path for the kernel DB (recommendation: `home-ai/soa1/data/soa1.db` or similar)
- Migration strategy for existing consent endpoints (`soa1/consent.py`) to use ConsentManager
- Whether consent should include expiration timestamps (even if batch-scoped)
