

Final SOA1 modular system plan

1. Fixed architecture decisions

These are locked unless there is a very good reason to reopen them.

Core roles

Conversation LLM

only visible/user-facing layer

handles dialogue, clarifications, explanations, final wording

never writes directly to DB or files


Orchestrator

hidden planner

JSON-only outputs

decides intent, stage, consent needs, routing, action plan

enforces policy through planning, but does not execute tools itself


Specialists

silent callable modules only

return structured outputs only

no user-facing chat

no direct user interaction


Execution Layer

deterministic Python/SQL/action runtime

validates plan against policy

runs actions

returns structured results only


Persistence Gateway

only write path to DB/files for persistent state

consent-aware, scope-aware, audit-logged


Knowledge/RAG layer

retrieval only when intent allows it

scoped by user/profile/pod/job

always provenance-aware



2. Hard rules

These are not suggestions.

CONTROL enforcement

Every action must be checked against:

current CONTROL.stage

current CONTROL.allowed_actions

consent scope requirements

user/profile/pod scope


If not allowed, it fails closed.

LLM-driven responses

All final visible text comes from the Conversation LLM only.

That means:

executor returns structured data, not prose

persistence gateway returns statuses, not prose

specialists return structured data, not prose

orchestrator returns JSON plan, not prose


Silent specialists

Specialists are tools, not assistants.

Phinance consent ruling

No pre-consent Phinance invocation.

Pre-consent upload stage may use:

doc_router

deterministic parsing

metadata extraction

non-persistent inspection summaries


But not Phinance.

Retrieval gating

RAG retrieval is allowed only when:

current intent requires it

CONTROL.allowed_actions permits it

scope filters are applied

doc class is allowed


doc_router role

doc_router is advisory only. It classifies and provides domain hints. It never invokes specialists directly.

Flow: input → doc_router → orchestrator → CONTROL-compliant plan → executor → structured results → conversation LLM


---

3. Final system flow

A. Ingestion / first contact

1. User uploads docs or asks a question


2. doc_router classifies:

finance

medical

general

mixed/uncertain



3. Deterministic ingest extracts safe non-persistent metadata


4. Orchestrator receives:

user message

doc_router tags

ingest summary

current CONTROL state



5. Orchestrator returns JSON:

intent

stage

consent state

action plan

response mode



6. If execution not needed:

conversation LLM replies directly



7. If execution needed:

executor validates plan

executor runs allowed actions

executor returns structured result bundle

conversation LLM renders final visible response




B. Post-consent working flow

1. User grants required consent


2. CONTROL state updates


3. Orchestrator can now plan:

specialist invocation

retrieval

write actions

report generation



4. Executor runs those actions


5. Persistence gateway allows writes only when scope matches


6. Conversation LLM explains results




---

4. Data model separation

This matters a lot. Do not blur these.

1. Job artifacts

uploaded files

extracted JSON

intermediate outputs

report assets

scoped to job


2. User memory

stable user preferences/facts

proposal/commit model

not for document content dumping


3. Knowledge base

intentionally ingested documents

reusable retrieval source

provenance attached


4. Vector index

embeddings pointing to KB chunks

not a replacement for memory

not a dumping ground for everything



---

5. Main implementation components

A. Orchestrator contract

Orchestrator outputs strict JSON with:

intent

stage

consent

control

actions[]

response_mode


B. Execution contract

Every action has:

type

typed input schema

typed output schema

required control action

required consent scope

write flags

idempotency key


C. Tool registry

Registry maps action types to handlers.

Handlers declare:

requires_control_action

requires_consent_scope

writes_db

writes_files

silent_module_only


D. Persistence gateway

Centralized write layer enforcing:

scope

consent

audit trail

model/pipeline version logging

no user-facing text


E. Knowledge service

Handles:

ingest

chunking

embeddings

retrieval

provenance

doc-class filters


F. Observability

Need:

append-only event logs

metrics

traces

eval suites

regression harness



---

6. Recommended execution order

This is the order I would actually follow.

Phase 1 — lock the core boundaries

1. Finalize role definitions:

conversation LLM visible

orchestrator hidden

specialists silent

executor deterministic



2. Clean wording across all docs so these boundaries are consistent


3. Rename conflicting action concepts:

registry-level capability_actions

runtime CONTROL.allowed_actions




Phase 2 — build the execution spine

4. Define action schema


5. Build tool registry


6. Build executor


7. Add CONTROL validation inside executor


8. Add structured result bundle contract


9. Add response contract for conversation LLM rendering



Phase 3 — enforce consent and persistence

10. Build Consent Manager


11. Build Persistence Gateway


12. Route all writes through gateway


13. Add fail-closed behavior for non-consented writes


14. Add audit trail for every write and rejection



Phase 4 — route correctly before getting fancy

15. Integrate doc_router properly


16. Make doc_router output explicit:



domain_tags

confidence

doc_class

requires_user_confirmation


17. Feed that into orchestrator input


18. Keep specialist routing dependent on CONTROL, not doc_router directly



Phase 5 — wire user-facing response flow

19. Ensure orchestrator returns JSON-only


20. Ensure executor returns structured result bundle only


21. Ensure conversation LLM renders all final visible responses


22. Remove any remaining hardcoded user-visible strings from non-LLM layers



Phase 6 — add knowledge safely

23. Implement artifact store / KB / memory / vector separation


24. Build retrieval tool


25. Add intent-gated retrieval


26. Add doc-class filters


27. Add provenance/citation metadata



Phase 7 — add observability before scale

28. Event logger


29. Metrics


30. Tracing


31. Control-violation logging


32. Consent-block logging


33. Routing telemetry


34. Retrieval telemetry



Phase 8 — evaluation and regression

35. Contract tests for orchestrator JSON


36. CONTROL enforcement tests


37. Specialist silence tests


38. No-pre-consent-write tests


39. No-pre-consent-Phinance tests


40. Retrieval gating tests


41. Cross-user isolation tests


42. End-to-end finance workflow regression suite



Phase 9 — pod-ready deployment

43. Define pod config boundaries


44. Namespace storage by tenant/pod/user/profile/job


45. Package services:



API

orchestrator

executor worker

db

vector

model runtime

report server


46. Add config versioning + migration rules




---

7. Minimal MVP-safe cut

If you want the shortest path that is still architecturally sane, do this first:

1. role boundary cleanup


2. action schema


3. executor with CONTROL validation


4. consent manager


5. persistence gateway


6. doc_router integration


7. LLM-only response rendering


8. event logging



That gets you:

safe flow

modular routing base

no policy nonsense

auditability

future pod expansion without rewriting the spine



---

8. Success criteria

The plan is only “done” when these are true:

Safety

0 DB writes before consent

0 specialist invocation before allowed stage

0 direct specialist-user interaction paths

0 executor-generated final user messages


Correctness

orchestrator JSON validity >= 99%

routing follows CONTROL every time

Phinance never runs pre-consent

retrieval never runs outside intent/doc-class policy


Isolation

0 cross-user/profile leaks

retrieval namespace always scoped

memory writes never bypass proposal/commit flow


Debuggability

every job has a full event trail

every failed action has structured reason

every report can be traced to model/pipeline versions



---

9. Final practical recommendation

Do not start with RAG, fancy pod packaging, or multi-domain expansion first.

Start with this backbone:

planner/executor split

CONTROL enforcement

consent-aware persistence

LLM-only visible responses

doc_router-informed routing

audit logs


That is the actual skeleton.

Everything else is armor, weapons, and dramatic cape physics.

10. Final one-line summary

Build SOA1 as a policy-validated planner/executor system where doc_router informs routing, CONTROL governs actions, specialists stay silent, persistence is consent-gated, and only the conversation LLM speaks to the user.