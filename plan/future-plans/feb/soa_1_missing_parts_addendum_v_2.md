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
6. **Compliance hooks** (CONTROL header enforcement, silent specialists, LLM-driven responses, doc_router routing)

Each section includes: **what to build**, **interfaces**, and **integration points into your existing plan**.

---

## 1) Compliance Hooks (hard rules that the executor must enforce)

This section exists because these are **not architecture preferences**. They are system rules.

### 1.1 CONTROL header enforcement is mandatory
The Execution Layer must validate every planned action against the active `CONTROL` header before anything runs.

At minimum, executor validation must enforce:
- `CONTROL.stage` gating
- `CONTROL.allowed_actions` allowlist
- specialist invocation only when explicitly permitted by `allowed_actions`
- no action type outside current stage policy
- no write-capable action before consent-required scopes are satisfied

**Fail-closed rule:**  
If a planned action is not explicitly allowed by the current `CONTROL` header, the executor must reject it and emit a control-violation event. No fallback. No “best effort.”

### 1.2 Specialists are silent modules
Specialists are **callable modules only**. They:
- do analysis
- return structured outputs
- do not generate user-facing chat
- do not ask the user questions directly
- do not bypass orchestrator / conversation model boundaries

They are not “mini assistants.” They are more like scoped analytic engines with typed outputs.

### 1.3 LLM-driven responses rule
All user-facing text must come from the LLM response layer.

Therefore:
- the executor must not emit final user strings
- the PersistenceGateway must not emit final user strings
- tool handlers may return structured statuses, codes, warnings, and recommended response fields
- the final visible response is rendered by the conversation LLM from structured execution results

The only permissible non-LLM visible strings from system layers are:
- machine-readable error codes
- log/event names
- internal status constants

### 1.4 Phinance consent ambiguity — decision
This must be resolved explicitly.

**Decision:** `Phinance` is **not invoked pre-consent**.

Pre-consent upload-time work is limited to:
- `doc_router`
- deterministic file inspection / metadata extraction
- header or lightweight structural parsing
- orchestrator reasoning over non-persistent summaries

That means:
- no hidden Phinance specialist call on upload
- no Phinance analysis until the system reaches the correct stage and `invoke_specialist` is allowed by the active CONTROL header
- any earlier “read-only specialist analysis on upload” language should be treated as superseded by this rule

This keeps enforcement consistent with stage gating and avoids policy drift.

### 1.5 Retrieval must also obey intent gating
Knowledge retrieval is not free-floating.

Retrieval is allowed only when:
- the orchestrator determines it is required for the current intent
- the relevant retrieval action is present in `CONTROL.allowed_actions`
- scope filters derived from kernel context are applied

So the Knowledge/RAG layer must obey the same gating model as specialist invocation.

### 1.6 doc_router is advisory, not sovereign
`doc_router` classifies input and proposes domain hints like:
- general
- finance
- medical
- mixed / ambiguous

But `doc_router` does not directly invoke specialists. It informs orchestrator routing decisions.

Flow:
`doc_router -> domain tags -> orchestrator -> CONTROL-compliant action plan -> executor`

---

## 2) User-Facing Response Flow (to satisfy LLM-driven responses cleanly)

The system needs a clear answer to this question:

> If the orchestrator returns JSON-only action plans, where does the visible text come from?

### 2.1 Recommended model
Use a **two-step plan-then-respond flow**.

#### Step A: Orchestrator (hidden)
Returns **JSON only**, including:
- intent
- consent requirements
- action plan
- response mode hint

Example:
```json
{
  "intent": "merchant_fix",
  "stage": "READY",
  "actions": [...],
  "response_mode": "llm_render_after_execution"
}
```

#### Step B: Executor (deterministic)
Runs the action plan and returns a **structured result bundle**, e.g.:
```json
{
  "status": "success",
  "result_type": "merchant_mapping_updated",
  "changed_rows": 23,
  "warnings": [],
  "user_visible_facts": {
    "merchant_name": "Chintu Communication",
    "new_category": "Utilities"
  }
}
```

#### Step C: Conversation LLM (visible layer)
Takes:
- prior user message
- structured result bundle
- current context / memory policy

Then produces the **final user-facing reply**.

This keeps:
- orchestration machine-readable
- execution deterministic
- visible text LLM-driven

### 2.2 Non-execution turns
If no execution is needed:
- orchestrator may return `actions: []`
- conversation LLM responds directly

### 2.3 Why this is the correct split
This preserves all three requirements:
- strict JSON orchestration
- silent specialists
- LLM-driven user-facing language

---

## 3) Execution Contract & Tool Runtime (the “Execution Layer” made real)

### 3.1 Why this is missing
Right now, the modular plan defines *routing* and *consent*, but not the **formal contract** between:
- Orchestrator (JSON-only planner)
- Execution Layer (Python/SQL deterministic actions)
- Persistence/Audit (what is allowed to be stored, and when)
- Conversation layer (which alone turns structured outcomes into visible text)

Without a contract:
- “schema-safe” becomes “best-effort”
- tool calls become brittle and hard to validate
- debugging becomes archaeology

### 3.2 What to build
**A. Action Schema (Orchestrator -> Executor)**  
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
  "control": {
    "stage": "READY",
    "allowed_actions": ["invoke_specialist", "retrieve_context", "ask_user_question"]
  },
  "actions": [
    {
      "type": "RETRIEVE_CONTEXT",
      "input": {"query": "…"},
      "idempotency_key": "sha256(…)"
    },
    {
      "type": "INVOKE_SPECIALIST",
      "input": {"specialist_id": "phinance"},
      "depends_on": ["RETRIEVE_CONTEXT"]
    }
  ],
  "response_mode": "llm_render_after_execution"
}
```

**B. Tool Registry (Executor knows what actions exist)**  
A registry mapping `action.type` -> `callable`.

Each callable has:
- **pydantic input model**
- **pydantic output model**
- flags:
  - `requires_control_action`
  - `requires_consent_scope`
  - `writes_db`
  - `writes_files`
  - `silent_module_only`

**C. Deterministic Executor**  
Runs actions sequentially (or DAG), enforcing:
- CONTROL stage + `allowed_actions`
- consent scopes
- per-user scoping
- idempotency
- transactional DB writes
- structured errors
- silent specialist rule

**D. Validation & Fail-Closed**
- Orchestrator output validated via JSON Schema + pydantic
- Executor cross-checks every action against CONTROL header
- If invalid: reject plan, emit `CONTROL_VIOLATION` or `LLM_OUTPUT_VALIDATION_FAILED`

### 3.3 Specialists are silent modules (enforced here, not just documented)
The tool registry must explicitly encode whether a callable is a specialist module.

For specialists:
- `silent_module_only = true`
- outputs are structured only
- no direct user interaction API is exposed
- no response templates are stored in the specialist itself

### 3.4 Integration points with the Modular Agent Plan
Tie directly into the existing items:

- **Plan item #4 (Orchestrator as Entry Point):**
  - orchestrator returns *only* the Action Schema above
  - API/CLI calls `ExecutionDispatcher.execute(plan)`

- **Plan item #8 (Progressive Flow + Consent Alignment):**
  - executor blocks any action with `writes_db=true` unless consent scope granted
  - pre-consent upload flow limited to doc_router + deterministic inspection
  - no Phinance invocation during upload triage

- **Plan item #9 (Verification & Safety):**
  Add verification tests for:
  - no action runs unless permitted by `CONTROL.allowed_actions`
  - specialist invocation only when stage and allowed actions permit it
  - no `writes_db` actions run without consent
  - all actions include `user_scope` enforced by kernel context
  - idempotency keys prevent duplicate writes on retries

### 3.5 Recommended file layout
```text
home-ai/
  soa1/
    execution/
      action_schema.py
      tool_registry.py
      executor.py
      dispatcher.py
      policies.py
      control_validation.py
      response_contract.py
```

---

## 4) Knowledge & Retrieval Architecture (RAG with provenance, not “memory”)

### 4.1 Why this is missing
Your plan fixes **memory scoping** (good), but you also need a **knowledge layer**:
- for PDFs, notes, manuals, policies, prior reports
- for “explain why” answers with citations
- for multi-pod reuse later

If you blur “memory” and “knowledge”, you will:
- contaminate user profiles with document content
- lose provenance
- create retrieval leakage across tenants/users
- bypass intent gating and retrieve when the user never asked for it

### 4.2 What to build
**A. 4-store model (clear separation)**
1. **Job Artifacts Store**: raw uploads + extracted JSON (scoped to job)
2. **User Memory Store**: preferences, stable facts (proposal/commit)
3. **Knowledge Base Store**: documents intentionally ingested (RAG)
4. **Vector Index**: embeddings pointing back to KB chunks (not raw memory)

**B. Ingestion Pipeline**
- extract text (PDF -> text per page)
- chunking rules (by heading / sentence windows)
- metadata: `doc_id`, `page`, `hash`, `user_id/profile_id`, `pod_id`, `doc_class`
- embedding + write to vector store

**C. Retrieval Policy**
Retrieval should be a **tool** the orchestrator can request:
- `RETRIEVE_CONTEXT(query, k, filters)`
- filters always include tenant/user/pod scope
- retrieval action must be CONTROL-allowed
- retrieval must be justified by the active intent

**D. doc classification + intent gating**
Retrieval must respect both:
- **doc classification** (what kind of source is this? finance/medical/general/etc.)
- **intent gating** (why are we retrieving right now?)

This prevents “retrieve first, justify later” behavior.

### 4.3 Integration points with the Modular Agent Plan
- **Per-agent config** gains:
  - `retrieval.enabled`
  - `retrieval.allowed_sources`
  - `retrieval.allowed_doc_classes`
  - `retrieval.max_k`
  - `retrieval.min_score`

- **Unified model loading** is unchanged; retrieval is a *tool* action.
- **Kernel context** defines retrieval namespaces.
- **doc_router** contributes domain tags that help the orchestrator decide whether finance/medical/general retrieval is appropriate.

### 4.4 Recommended file layout
```text
home-ai/
  soa1/
    knowledge/
      ingest.py
      chunking.py
      embeddings.py
      vector_store.py
      retrieval.py
      provenance.py
      doc_router_bridge.py
```

---

## 5) Observability, Monitoring, and Evaluation (so you can ship without superstition)

### 5.1 Why this is missing
Your modular plan adds checks, but you still need:
- **event logs**
- **metrics**
- **traces**
- **evaluation**

Otherwise, every change becomes “it feels slower / seems wrong” debugging.

### 5.2 What to build
**A. Event Log (append-only JSONL)**
Standard event types (examples):
- `JOB_CREATED`, `UPLOAD_RECEIVED`, `STAGE_CHANGED`
- `DOC_ROUTER_CLASSIFIED`
- `CONTROL_HEADER_APPLIED`
- `LLM_REQUEST_SENT`, `LLM_RESPONSE_RECEIVED`
- `LLM_OUTPUT_VALIDATION_FAILED`
- `CONTROL_VIOLATION`
- `ACTION_STARTED`, `ACTION_FINISHED`, `ACTION_FAILED`
- `CONSENT_REQUIRED`, `CONSENT_GRANTED`, `CONSENT_BLOCKED_WRITE`
- `EXPORT_WRITTEN`, `PUBLISH_COMPLETED`, `PIPELINE_ERROR`

Each event includes:
- `job_id`, `user_id`, `profile_id`, `pod_id`
- `stage`, `agent_id`, `action_type`
- timestamps + duration
- file refs (prompt/response paths)

**B. Metrics**
Expose `/metrics` with:
- action durations, failures
- parse success rate
- consent-blocked write count
- routing distribution by agent
- token usage by agent/model
- control violations by type
- doc_router classification distribution

**C. Tracing**
Add OpenTelemetry spans around:
- doc_router classification
- orchestrator call
- each action execution
- DB transactions

**D. Evaluation Harness**
Two layers:
1. **Contract tests**: orchestrator outputs valid schema and respects CONTROL policies
2. **Scenario regression**: end-to-end runs over fixed PDF sets checking:
   - no writes before consent
   - no specialist invocation before allowed stage
   - no retrieval outside allowed intent
   - stable aggregates unchanged across refactors
   - no cross-user access

### 5.3 Integration points
- Wrap **doc_router**, **orchestrator**, and **executor** with same trace + event context.
- Plug metrics into API server.
- Run evaluations in CI or local command:
  - `python -m soa1.eval.run --suite finance_core`

### 5.4 Recommended file layout
```text
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

## 6) Deployment Shape: Pods, Services, Data Boundaries

### 6.1 Why this is missing
Your original vision is “pods” (finance, family, health, etc.).
The modular plan is still scoped to one codebase; it doesn’t specify:
- which processes run where
- how models are hosted
- how pods are isolated
- how upgrades and migrations work

### 6.2 What to build
**A. Reference deployment (single machine)**
Services:
- `api` (FastAPI gateway + auth)
- `orchestrator`
- `executor-worker`
- `db`
- `vector`
- `model-runtime`
- `report-server`

**B. Pod boundary**
A pod is a config + data namespace:
- `pod_id` defines:
  - allowed agents
  - allowed tools
  - allowed storage roots
  - model list
  - retrieval sources
  - retention policies

**C. doc_router placement**
`doc_router` should sit near ingestion / orchestration boundary:
- file enters system
- doc_router classifies
- classification stored in job metadata
- orchestrator uses this as advisory input
- final routing still obeys CONTROL policy

**D. Data directory convention**
```text
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

### 6.3 Integration points
- **Kernel / Multi-tenant context** becomes the router for:
  - DB scope
  - file paths
  - vector namespace
- **Agent registry** can be pod-scoped.
- **doc_router** becomes part of the modular routing story instead of an implicit side system.

---

## 7) Deterministic Persistence, Consent, Privacy (enforced at storage layer)

### 7.1 Why this is missing
The modular plan says “don’t persist before consent.”
But unless persistence is centralized and guarded, someone will accidentally write early.

This must be a *system invariant*.

### 7.2 What to build
**A. Consent Manager**
- tracks required scopes per job
- stores consent events
- exposes `can_write(scope)` to the executor

**B. Persistence Gateway**
All DB writes go through a single module that:
- checks consent scopes
- checks CONTROL-compliant context
- writes audit events
- attaches `job_id`, `model_version`, `action_id`
- rejects writes that lack required context
- returns structured result objects only, never final user text

**C. PII hygiene**
- scrubber runs before persistence
- allowlist-based persistence
- raw PDFs retained only per policy

**D. Reproducibility**
Store with each artifact:
- model name + version/hash
- prompt template version
- pipeline version

### 7.3 Integration points
- **Plan item #8 (Progressive Flow + Consent Alignment)** becomes enforceable:
  executor calls `PersistenceGateway.*` only after `ConsentManager.can_write()` and CONTROL validation.
- **Plan item #7 (Kernel / Multi-Tenant Context):**
  user scope is mandatory input to PersistenceGateway and enforced in queries.
- **LLM-driven response rule:** PersistenceGateway must never contain user-visible templates.

---

## 8) How to integrate this into your existing plan (concrete merge plan)

### 8.1 Extend the existing “Next Steps (Suggested Order)”
Keep your current order, then append:

**Existing Steps (keep):**
1. Define agent registry + per-agent config schema.
2. Update model loading to honor per-agent configs and enforce Phinance `num_ctx=4096`.
3. Wire orchestrator into entry points and remove auto-invoke in `SOA1Agent`.
4. Fix specialist discovery and routing through consent manager.
5. Add kernel context + multi-tenant scoping.
6. Replace remaining hardcoded user-facing strings with LLM responses.

**Addendum Steps (add):**
7. Implement **Action Schema + Deterministic Executor** with CONTROL validation.
8. Add **PersistenceGateway + ConsentManager** with fail-closed writes.
9. Add **doc_router integration** into orchestrator routing path.
10. Add **EventLogger + Metrics + Tracing**.
11. Add **KnowledgeService** with intent-gated retrieval + provenance.
12. Define **Pod packaging**.
13. Add **Evaluation harness** and gate merges on CONTROL / consent / routing compliance.

### 8.2 Minimal MVP-safe cut
Smallest safe set:
- #7 Action Schema + Executor + CONTROL validation
- #8 PersistenceGateway + ConsentManager
- #9 doc_router routing integration
- #10 EventLogger

### 8.3 Config additions
```yaml
retrieval:
  enabled: true
  allowed_sources: ["job_artifacts", "kb"]
  allowed_doc_classes: ["finance", "general"]
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
  enforce_control_headers: true
  silent_specialists_only: true
```

---

## 9) Success criteria (so “done” is measurable)

**Correctness & Safety**
- 0 DB writes before consent in regression suite
- 0 specialist invocations before CONTROL-allowed stage
- 0 retrievals outside allowed intent/doc-class scope
- 0 cross-user data access in tests
- Orchestrator output schema validity >= 99% across test prompts

**Reliability**
- Parse failure rate tracked + alertable
- Idempotency prevents duplicate writes on retries

**Debuggability**
- Every job has complete event trail + action-level timings
- Any report is reproducible with stored versions/hashes

**Architecture compliance**
- 0 executor-generated user-facing messages
- 0 specialist direct interaction paths exposed

---

## Appendix A: Suggested first action types (finance MVP)
- `DOC_ROUTER_CLASSIFY`
- `PARSE_PDFS`
- `EXTRACT_TRANSACTIONS`
- `RETRIEVE_CONTEXT`
- `INVOKE_SPECIALIST`
- `NORMALIZE_MERCHANTS`
- `CATEGORIZE_TRANSACTIONS`
- `DETECT_HIDDEN_DRAINS`
- `GENERATE_REPORT_DATA`
- `EXPORT_REPORT_HTML`
- `PUBLISH_REPORT`
- `UPSERT_MERCHANT_MAPPING`
- `RECOMPUTE_AGGREGATES`

