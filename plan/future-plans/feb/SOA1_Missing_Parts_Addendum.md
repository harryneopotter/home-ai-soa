# SOA1 / Modular Agent Plan — Missing System Pieces Addendum
*(What’s missing, why it matters, and exactly where it plugs into `MODULAR_AGENT_IMPLEMENTATION_PLAN.md`)*

## 0) Context: what this addendum is (and isn’t)

Your current **Modular Agent Implementation Plan** fixes the “agent-core plumbing”:
- agent registry
- per-agent configs
- orchestrator-first entry
- specialist routing + consent gating
- unified model loading
- multi-tenant kernel context
- removal of hardcoded `[INVOKE:phinance]` hacks

That’s necessary.

This addendum covers the **system pieces that make the platform trustworthy, scalable, and productizable**:
1. **Execution Contract** (how LLM plans become deterministic tool actions safely)
2. **Knowledge & Retrieval layer** (RAG + provenance, distinct from “memory”)
3. **Observability + Evaluation** (logs/metrics/traces + regression harness)
4. **Deployment shape** (pods, services, data boundaries, upgrades)
5. **Deterministic persistence + privacy** (consent enforcement at storage level)

Each section includes: **what to build**, **interfaces**, and **integration points into your existing plan**.

---

## 1) Execution Contract & Tool Runtime (the “Execution Layer” made real)

### 1.1 Why this is missing
Right now, the modular plan defines *routing* and *consent*, but not the **formal contract** between:
- Orchestrator (JSON-only planner)
- Execution Layer (Python/SQL deterministic actions)
- Persistence/Audit (what is allowed to be stored, and when)

Without a contract:
- “Schema-safe” becomes “best-effort”
- tool calls become brittle and hard to validate
- debugging becomes archaeology

### 1.2 What to build
**A. Action Schema (Orchestrator → Executor)**
A strict JSON schema that represents a plan as **a list of typed actions**.

Minimal structure (example):
```json
{
  "job_id": "…",
  "stage": "READY|NEEDS_CONSENT|RUNNING|DONE|ERROR",
  "intent": "report_generation|merchant_fix|query|…",
  "consent": {
    "required": true,
    "granted": false,
    "scope": "persist_transactions|update_mappings|…"
  },
  "actions": [
    {
      "type": "PARSE_PDFS",
      "input": {"pdf_paths": ["…"]},
      "idempotency_key": "sha256(…)"
    },
    {
      "type": "NORMALIZE_MERCHANTS",
      "input": {"strategy": "stable_id_sha256"},
      "depends_on": ["PARSE_PDFS"]
    }
  ]
}
```

**B. Tool Registry (Executor knows what actions exist)**
- A registry mapping `action.type` → `callable`
- Each callable has:
  - **pydantic input model**
  - **pydantic output model**
  - flags: `requires_consent_scope`, `writes_db`, `writes_files`

**C. Deterministic Executor**
- Runs actions sequentially (or DAG), enforcing:
  - consent scopes
  - per-user scoping
  - idempotency
  - transactional DB writes
  - structured errors

**D. Validation & Fail-Closed**
- Orchestrator output validated via JSON Schema + pydantic
- If invalid: return `LLM_OUTPUT_VALIDATION_FAILED` and re-ask orchestrator

### 1.3 Integration points with the Modular Agent Plan
Tie directly into the existing items:

- **Plan item #4 (Orchestrator as Entry Point):**
  - orchestrator returns *only* the Action Schema above
  - API/CLI calls `ExecutionDispatcher.execute(plan)`

- **Plan item #8 (Progressive Flow + Consent Alignment):**
  - executor blocks any action with `writes_db=true` unless consent scope granted
  - background extraction runs as `writes_db=false` (in-memory / job sandbox)

- **Plan item #9 (Verification & Safety):**
  Add verification tests for:
  - no `writes_db` actions run without consent
  - all actions include `user_scope` enforced by kernel context
  - idempotency keys prevent duplicate writes on retries

### 1.4 Recommended file layout
```
home-ai/
  soa1/
    execution/
      action_schema.py          # jsonschema + pydantic models
      tool_registry.py          # action type -> handler
      executor.py               # deterministic runner
      dispatcher.py             # orchestrator output -> executor input
      policies.py               # consent + scope enforcement
```

---

## 2) Knowledge & Retrieval Architecture (RAG with provenance, not “memory”)

### 2.1 Why this is missing
Your plan fixes **memory scoping** (good), but you also need a **knowledge layer**:
- for PDFs, notes, manuals, policies, prior reports
- for “explain why” answers with citations
- for multi-pod reuse later

If you blur “memory” and “knowledge”, you will:
- contaminate user profiles with document content
- lose provenance (where did this come from?)
- create retrieval leakage across tenants/users

### 2.2 What to build
**A. 4-store model (clear separation)**
1. **Job Artifacts Store**: raw uploads + extracted JSON (scoped to job)
2. **User Memory Store**: preferences, stable facts (proposal/commit)
3. **Knowledge Base Store**: documents intentionally ingested (RAG)
4. **Vector Index**: embeddings pointing back to KB chunks (not raw memory)

**B. Ingestion Pipeline**
- extract text (PDF → text per page)
- chunking rules (by heading / sentence windows)
- metadata: `doc_id`, `page`, `hash`, `user_id/profile_id`, `pod_id`
- embedding + write to vector store

**C. Retrieval Policy**
Retrieval should be a **tool** the orchestrator can request:
- `RETRIEVE_CONTEXT(query, k, filters)`
- filters always include tenant/user/pod scope
- return chunks with provenance

**D. Citations / provenance**
Every retrieved chunk includes:
- `doc_id`, `page_range`, `chunk_id`, `content_hash`
Conversation layer renders citations (your report UI can also hyperlink to sources).

### 2.3 Integration points with the Modular Agent Plan
- **Per-agent config** gains:
  - `retrieval.enabled`
  - `retrieval.allowed_sources` (job artifacts only vs KB vs both)
  - `retrieval.max_k`, `retrieval.min_score`

- **Unified model loading** is unchanged; retrieval is a *tool* action.
  Orchestrator plans:
  - `RETRIEVE_CONTEXT` → `ANSWER_WITH_CONTEXT`

- **Kernel context** defines retrieval namespaces:
  - `tenant_id / user_id / profile_id / pod_id` filters applied automatically

### 2.4 Recommended file layout
```
home-ai/
  soa1/
    knowledge/
      ingest.py
      chunking.py
      embeddings.py
      vector_store.py
      retrieval.py
      provenance.py
```

---

## 3) Observability, Monitoring, and Evaluation (so you can ship without superstition)

### 3.1 Why this is missing
Your modular plan adds checks, but you still need:
- **event logs** (audit trail)
- **metrics** (health + performance)
- **traces** (where time goes)
- **evaluation** (routing and safety regression)

Otherwise, every change becomes “it feels slower / seems wrong” debugging.

### 3.2 What to build
**A. Event Log (append-only JSONL)**
Standard event types (examples):
- `JOB_CREATED`, `UPLOAD_RECEIVED`, `STAGE_CHANGED`
- `LLM_REQUEST_SENT`, `LLM_RESPONSE_RECEIVED`
- `LLM_OUTPUT_VALIDATION_FAILED`
- `ACTION_STARTED`, `ACTION_FINISHED`, `ACTION_FAILED`
- `CONSENT_REQUIRED`, `CONSENT_GRANTED`, `CONSENT_BLOCKED_WRITE`
- `EXPORT_WRITTEN`, `PUBLISH_COMPLETED`, `PIPELINE_ERROR`

Each event includes:
- `job_id`, `user_id`, `profile_id`, `pod_id`
- `stage`, `agent_id`, `action_type`
- timestamps + duration
- file refs (prompt/response paths)

**B. Metrics**
Expose `/metrics` (Prometheus format) with:
- action durations, failures
- parse success rate
- consent-blocked write count
- routing distribution by agent
- token usage by agent/model

**C. Tracing**
Add OpenTelemetry spans around:
- orchestrator call
- each action execution
- DB transactions

**D. Evaluation Harness**
Two layers:
1. **Contract tests**: orchestrator outputs valid schema for a corpus of prompts
2. **Scenario regression**: end-to-end runs over fixed PDF sets (sanitized) checking:
   - no writes before consent
   - stable aggregates unchanged across refactors
   - no cross-user access

### 3.3 Integration points
- Wrap **orchestrator** and **executor** with the same EventLogger + trace context.
- Plug metrics into API server.
- Run evaluations in CI or as a local command:
  - `python -m soa1.eval.run --suite finance_core`

### 3.4 Recommended file layout
```
home-ai/
  soa1/
    observability/
      event_logger.py
      metrics.py
      tracing.py
    eval/
      suites/
      run.py
      fixtures/
```

---

## 4) Deployment Shape: Pods, Services, Data Boundaries

### 4.1 Why this is missing
Your original vision is “pods” (finance, family, health, etc.).
The modular plan is still scoped to one codebase; it doesn’t specify:
- which processes run where
- how models are hosted
- how pods are isolated
- how upgrades and migrations work

### 4.2 What to build
**A. Reference deployment (single machine)**
Services (containers or processes):
- `api` (FastAPI gateway + auth)
- `orchestrator` (can be inside api initially)
- `executor-worker` (Python tools / pipeline)
- `db` (Postgres preferred; SQLite for dev)
- `vector` (Qdrant/FAISS depending on scale)
- `model-runtime` (ollama / llama.cpp server)
- `report-server` (static HTML + JSON artifacts)

**B. Pod boundary**
A pod is a config + data namespace:
- `pod_id` defines:
  - allowed agents
  - allowed tools
  - allowed storage roots
  - model list
  - retrieval sources
  - retention policies

**C. Data directory convention**
```
/data/
  tenants/<tenant_id>/
    pods/<pod_id>/
      users/<user_id>/profiles/<profile_id>/
        jobs/<job_id>/
          uploads/
          extracted/
          logs/
          report/
```

**D. Upgrade / migration strategy**
- DB migrations (alembic)
- config migration versioning (`config_version`)
- artifact format versioning (`report_data_version`)

### 4.3 Integration points
- **Kernel / Multi-tenant context** becomes the router for:
  - DB schema namespace (or row-level scope)
  - file paths
  - vector namespace
- **Agent registry** can be pod-scoped:
  - global registry + pod allowlist

---

## 5) Deterministic Persistence, Consent, Privacy (enforced at storage layer)

### 5.1 Why this is missing
The modular plan says “don’t persist before consent.”
But unless persistence is centralized and guarded, someone will accidentally write early.
This must be enforced as a *system invariant*, not a developer promise.

### 5.2 What to build
**A. Consent Manager**
- tracks required scopes per job
- stores consent events
- exposes `can_write(scope)` to the executor

**B. Persistence Gateway**
All DB writes go through a single module that:
- checks consent scopes
- writes audit events
- attaches `job_id`, `model_version`, `action_id`
- rejects writes that lack required context

**C. PII hygiene**
- scrubber runs before persistence
- allowlist-based persistence: only allowed fields are stored
- raw PDFs retained only per policy (default: delete after extraction unless user opts-in)

**D. Reproducibility**
Store with each artifact:
- model name + version/hash
- prompt template version
- pipeline version
So reports can be re-generated and compared later.

### 5.3 Integration points
- **Plan item #8 (Progressive Flow + Consent Alignment)** becomes enforceable:
  executor calls `PersistenceGateway.*` only after `ConsentManager.can_write()`.

- **Plan item #7 (Kernel / Multi-Tenant Context)**:
  user scope is mandatory input to PersistenceGateway and enforced in queries.

---

## 6) How to integrate this into your existing plan (concrete “merge plan”)

### 6.1 Extend the existing “Next Steps (Suggested Order)”
Your current order is good; append these phases after step 4.

**Existing Steps (keep):**
1. Define agent registry + per-agent config schema.
2. Update model loading to honor per-agent configs and enforce Phinance `num_ctx=4096`.
3. Wire orchestrator into entry points and remove auto-invoke in `SOA1Agent`.
4. Fix specialist discovery and routing through consent manager.
5. Add kernel context + multi-tenant scoping.
6. Replace remaining hardcoded user-facing strings with LLM responses.

**Addendum Steps (add):**
7. Implement **Action Schema + Deterministic Executor** (Execution Contract).
8. Add **PersistenceGateway + ConsentManager** (fail-closed writes).
9. Add **EventLogger + Metrics + Tracing** (observability baseline).
10. Add **KnowledgeService** (ingest + retrieval tool + provenance).
11. Define **Pod packaging** (compose profiles, namespaces, upgrade path).
12. Add **Evaluation harness** (contract + scenario regression) and gate merges.

### 6.2 Minimal “MVP-compatible” cut (fastest path without breaking vision)
If you want the smallest set that still makes the system safe:
- #7 Action Schema + Executor
- #8 PersistenceGateway + ConsentManager
- #9 EventLogger (metrics/tracing can be light)
Everything else can follow.

### 6.3 Config additions (what new keys you need)
Add these to per-agent configs (or pod config):
```yaml
retrieval:
  enabled: true
  allowed_sources: ["job_artifacts", "kb"]
  max_k: 8
  min_score: 0.25

observability:
  events_enabled: true
  metrics_enabled: true
  tracing_enabled: false

privacy:
  retain_uploads_days: 0
  pii_allowlist: ["date", "amount", "merchant_norm", "category", "merchant_stable_id"]

execution:
  allow_parallel: false
  max_action_retries: 1
```

---

## 7) Success criteria (so “done” is measurable)

**Correctness & Safety**
- 0 DB writes before consent in regression suite
- 0 cross-user data access in tests
- Orchestrator output schema validity ≥ 99% across test prompts

**Reliability**
- Parse failure rate tracked + alertable
- Idempotency prevents duplicate writes on retries

**Debuggability**
- Every job has a complete event trail + action-level timings
- Any report is reproducible with stored versions/hashes

---

## Appendix A: Suggested first action types (finance MVP)
- `PARSE_PDFS`
- `EXTRACT_TRANSACTIONS`
- `NORMALIZE_MERCHANTS`
- `CATEGORIZE_TRANSACTIONS`
- `DETECT_HIDDEN_DRAINS`
- `GENERATE_REPORT_DATA`
- `EXPORT_REPORT_HTML`
- `PUBLISH_REPORT`
- `UPSERT_MERCHANT_MAPPING` *(requires consent scope: update_mappings)*
- `RECOMPUTE_AGGREGATES` *(requires consent scope: persist_updates)*

