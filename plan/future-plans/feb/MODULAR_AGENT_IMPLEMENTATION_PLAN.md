# Modular Agent Implementation Plan

This document merges the base modular plan with the missing-parts addendum
(`soa_1_missing_parts_addendum_v_2.md`) so there is a single authoritative
implementation plan.

## Current Implementation (Summary)

- Entry points use `SOA1Agent` directly. `Orchestrator` exists but is not wired into `home-ai/soa1/api.py` or `home-ai/soa1/cli.py`.
- Specialist invocation is hard-coded to Phinance via `[INVOKE:phinance]` in `home-ai/soa1/agent.py`, including a keyword-based fallback.
- Two model stacks exist:
  - `home-ai/soa1/model.py` uses `home-ai/soa1/config.yaml` with `num_ctx: 32768`.
  - `home-ai/soa1/models.py` forces `num_ctx=4096` for **all** endpoints in `_build_chat_payload`.
- Specialist discovery is inconsistent:
  - `home-ai/soa1/specialist/registry.py` scans `home-ai/soa1/specialists/` (does not exist).
  - Specialists/adapters live under `home-ai/agents/` but are not registered.
- Memory is single-user: `home-ai/soa1/memory/client.py` uses fixed `user_id`/`profile_id` from `home-ai/soa1/config.yaml`.
- Consent rules exist in `RemAssist/IMPLEMENTATION_GUIDE.md`, but current flow can auto-invoke Phinance and may persist transactions before explicit consent.
- LLM-driven responses are required by `RemAssist/LLM_DRIVEN_RESPONSES.md`, yet there are still hardcoded user-facing strings in `home-ai/soa1/agent.py` and `home-ai/soa1/orchestrator.py`.

## Design Direction (Per-Agent Config)

Per-agent configuration is the right approach. It cleanly supports:
- Per-agent `num_ctx` (Phinance stays at 4096; other agents can be larger).
- Per-agent model lists and fallback models.
- Per-agent system prompts and tool permissions.
- Per-agent consent requirements and allowed actions.

Use a single registry to list agents + config paths, and separate config files for each agent’s runtime settings.

## Required Changes (What and Why)

### 1) Agent Registry (Source of Truth)

**Why:** There is no single registry defining which agents exist, what they do, and how they are routed.

**Change:**
- Add a registry file (`home-ai/agents/registry.yaml` or extend `WHOAMI.json`) with:
  - `id`, `description`, `capabilities`
  - `required_capabilities`, `allowed_actions`
  - `config_path`, `enabled`, `role` (specialist vs core)

### 2) Per-Agent Config Files

**Why:** Current settings are mixed across `config.yaml`, `models.py`, and `model.py`. Phinance’s context limit is hard-coded globally instead of being scoped to its model.

**Change:**
- Add per-agent config files (e.g., `home-ai/agents/configs/<agent_id>.yaml`).
- Include: `model_name`, `base_url`, `temperature`, `max_tokens`, `num_ctx`, `system_prompt_path`, optional `fallback_models`.

**Constraint:**
- Phinance must remain at `num_ctx=4096` only for the Phinance agent. This should be enforced in its config (and validated in code), not globally.

### 3) Specialist Discovery and Routing

**Why:** The current registry scans a non-existent directory and no wiring exists to load `home-ai/agents/`.

**Change:**
- Update `home-ai/soa1/specialist/registry.py` to load from `home-ai/agents/` or the registry file.
- Replace ad-hoc `[INVOKE:phinance]` logic in `home-ai/soa1/agent.py` with the specialist router.
- Keep all specialist code under `home-ai/agents/` per `RemAssist/IMPLEMENTATION_GUIDE.md`.

### 4) Orchestrator as the Entry Point (Consent-First)

**Why:** Specialist invocation must be gated by explicit consent. The current `SOA1Agent` bypasses consent rules.

**Change:**
- Wire `home-ai/soa1/orchestrator.py` into `home-ai/soa1/api.py` and `home-ai/soa1/cli.py`.
- Ensure `user_action_confirmed` and `allowed_actions` are required before any specialist call.
- Remove keyword-based auto-invoke logic in `home-ai/soa1/agent.py`.

### 5) Unified Model Loading

**Why:** Two model clients + inconsistent context sizes create drift and violate the Phinance constraint.

**Change:**
- Introduce a shared model config loader that reads per-agent configs.
- In `home-ai/soa1/models.py`, set `num_ctx` per endpoint (Phinance stays 4096).
- In `home-ai/soa1/model.py`, source orchestrator settings from the orchestrator agent config.

### 6) LLM-Driven Responses Everywhere

**Why:** Hardcoded user-facing strings violate `RemAssist/LLM_DRIVEN_RESPONSES.md`.

**Change:**
- Replace hardcoded response text in `home-ai/soa1/agent.py` and `home-ai/soa1/orchestrator.py` with LLM-generated messages.
- Ensure upload responses are produced by the LLM using `prompts/orchestrator.md`.

### 7) Kernel / Multi-Tenant Context (From Feb Plan)

**Why:** Modular agents require per-user isolation and identity context.

**Change:**
- Implement kernel (context switch + identity prompt + vault scoping).
- Update `home-ai/soa1/memory/client.py` to read `user_id`/`profile_id` from kernel context.
- Scope file storage and DB access by user.

### 8) Progressive Flow + Consent Alignment

**Why:** `RemAssist/PROGRESSIVE_FLOW.md` requires no persistence or specialist invocation without explicit consent.

**Change:**
- Ensure transactions are not persisted until consent is granted.
- Keep background extraction and Python calculations in memory only.
- Specialist call starts only after explicit consent, not just upload.

### 9) Verification & Safety

**Why:** Modular routing adds new failure modes.

**Change:**
- Add checks for:
  - Phinance `num_ctx=4096`
  - Specialist blocked when consent missing
  - No cross-user data access
  - Registry correctly loads enabled agents

## Next Steps (Suggested Order)

1. Define agent registry + per-agent config schema.
2. Update model loading to honor per-agent configs and enforce Phinance `num_ctx=4096`.
3. Wire orchestrator into entry points and remove auto-invoke in `SOA1Agent`.
4. Fix specialist discovery and routing through consent manager.
5. Add kernel context + multi-tenant scoping.
6. Replace remaining hardcoded user-facing strings with LLM responses.

## Addendum: Missing System Pieces (Merged)

This section is additive to the base plan and brings in execution contract,
retrieval, observability, deployment, and persistence enforcement.

### 1) Compliance Hooks (Hard Rules the Executor Must Enforce)

#### 1.1 CONTROL header enforcement is mandatory
- Validate every planned action against the active CONTROL header.
- Enforce `CONTROL.stage` gating and `CONTROL.allowed_actions` allowlist.
- Block specialist invocation unless explicitly permitted by allowed actions.
- Block any write-capable action without required consent scopes.
- Fail-closed with a control-violation event.

#### 1.2 Specialists are silent modules
- Specialists return structured outputs only.
- No user-facing text, no questions, no orchestration logic.
- Orchestrator remains the only user-facing layer.

#### 1.3 LLM-driven responses rule
- Executor and persistence layers never emit user-facing text.
- Conversation LLM renders the final user response from structured results.

#### 1.4 Phinance consent decision
- Phinance is not invoked pre-consent.
- Pre-consent flow is limited to doc_router + deterministic inspection.
- `invoke_specialist` only when CONTROL allows and consent is granted.

#### 1.5 Retrieval must obey intent gating
- Retrieval requires correct intent + CONTROL allowlist + kernel scope filters.

#### 1.6 doc_router is advisory, not sovereign
- doc_router informs domain hints but never triggers specialists directly.

### 2) User-Facing Response Flow (Plan → Execute → Respond)

To satisfy LLM-driven responses while using JSON-only planning:

1) Planner returns JSON-only action plan.
2) Executor runs actions and returns a structured result bundle.
3) Conversation LLM renders the final user-facing reply.

If no execution is needed, the conversation LLM responds directly.

### 3) Execution Contract & Tool Runtime

#### 3.1 Action Schema
Define a strict JSON schema for action plans including:
- `intent`, `stage`, `consent`, `control`, and ordered `actions`.

#### 3.2 Tool Registry
- Map `action.type` to handler.
- Each handler uses pydantic input/output models.
- Flags include:
  - `requires_control_action`
  - `requires_consent_scope`
  - `writes_db`
  - `writes_files`
  - `silent_module_only`

#### 3.3 Deterministic Executor
- Enforce CONTROL header, consent scopes, user scoping, idempotency.
- Fail-closed on invalid plans or violations.

#### 3.4 Integration points
- Orchestrator returns only the action plan JSON.
- API/CLI executes via `ExecutionDispatcher.execute(plan)`.

### 4) Knowledge & Retrieval Architecture (RAG with provenance)

#### 4.1 4-store model
1) Job Artifacts Store
2) User Memory Store
3) Knowledge Base Store
4) Vector Index

#### 4.2 Ingestion pipeline
- Extract text, chunk, attach metadata, embed, store.

#### 4.3 Retrieval policy
- Retrieval is a tool action and must be CONTROL-allowed + intent-gated.
- Apply kernel scope filters on every retrieval.

#### 4.4 doc_router + intent gating
- doc_router provides domain tags that inform whether retrieval is appropriate.

### 5) Observability, Monitoring, Evaluation

#### 5.1 Event log
Append-only JSONL events with job/user/pod context.

#### 5.2 Metrics
Expose `/metrics` for action timing, failures, routing distribution, violations.

#### 5.3 Tracing
Add OpenTelemetry spans for routing, actions, DB transactions.

#### 5.4 Evaluation harness
Contract tests + scenario regression suites for consent, routing, and isolation.

### 6) Deployment Shape: Pods, Services, Data Boundaries

#### 6.1 Reference deployment
- api, orchestrator, executor-worker, db, vector, model-runtime, report-server.

#### 6.2 Pod boundary
- Pod-scoped agents, tools, storage roots, model lists, retention policies.

#### 6.3 doc_router placement
- doc_router classifies at ingestion and feeds orchestrator routing decisions.

### 7) Deterministic Persistence, Consent, Privacy

#### 7.1 Consent Manager
- Tracks consent scopes per job and exposes `can_write`.

#### 7.2 Persistence Gateway
- All writes go through a single module enforcing consent + CONTROL context.
- Emits audit events and returns structured results only.

#### 7.3 PII hygiene and reproducibility
- Allowlist persistence, retention policies, and stored pipeline versions.

### 8) Extended Next Steps (Addendum)

7. Implement Action Schema + Deterministic Executor with CONTROL validation.
8. Add PersistenceGateway + ConsentManager with fail-closed writes.
9. Add doc_router integration into orchestrator routing path.
10. Add EventLogger + Metrics + Tracing.
11. Add KnowledgeService with intent-gated retrieval + provenance.
12. Define Pod packaging.
13. Add Evaluation harness and gate merges on compliance.
