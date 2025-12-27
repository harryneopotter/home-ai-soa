# Finance Uploads, Consent & Persistence — Design Notes

Purpose
- Capture the agreed behavior for the upload → parsing → consent → persistence → analysis flow for the Finance MVP.
- Consolidates guardrails, required files, API shapes, DB persistence rules, and operational guidance so future sessions have a single source-of-truth.

Scope & Assumptions
- Local-first deployment (single machine / local network). "Server" and "client" run on the same PC in the household; components communicate over local HTTP or in-process events.
- The assistant SHOULD have full parsed data (transactions, metadata) available as soon as parsing completes and must persist it to the database for future reference (no need to re-parse PDFs).
- Specialist (Phinance) invocation requires explicit user confirmation per RemAssist/IMPLEMENTATION_GUIDE.md.
- Merchant name cleaning utilities exist (home-ai/finance-agent/src/sanitizer.py) and must be applied as part of the persistence and categorization pipeline.

Key Guardrails (summary from IMPLEMENTATION_GUIDE.md)
- Hard rule: The assistant MUST NOT initiate a specialist action unless the user explicitly requests or confirms it. (Upload ≠ consent)
- Allowed without consent: file ingestion, metadata extraction, header/first-page parsing, structural reading, indexing, preparing options (not executing them).
- On upload, the assistant must immediately acknowledge with the canonical message template (see the Implementation Guide).
- The orchestrator (home-ai/soa1) is the single source of truth for user intent and consent state.

End-to-end flow (high level)
1. Upload
   - User selects PDFs and clicks Upload.
   - Endpoint accepts file(s), writes original PDF copy to documents storage, returns job_id immediately to the UI.
   - Background parse job begins (staged parsing, see below).

2. Staged parsing (internal only)
   - STAGE A (METADATA_READY): file names, sizes, page counts.
   - STAGE B (HEADERS_READY): first-page headers, inferred doc types (advisory only).
   - STAGE C (PAGE CHUNKS / DOC_TEXT_READY): per-page or chunk text extraction.
   - STAGE D (TRANSACTIONS_READY): full transactions JSON (parsed & cleaned).

3. Agent engagement & consent
   - As soon as STAGE B is available, the orchestrator may ask an *intent* question using consent language (e.g., "I see some bank statements — do you want a financial analysis of these? If so, I can prepare a full report.").
   - The agent must not claim certainty before STAGE D is available, and must not call Phinance until consent is explicitly recorded.
   - User choices are recorded in the orchestrator's ConsentState (user_action_confirmed, confirmed_intent, confirmed_specialists).

4. Persistence (required)
   - As soon as transactions are parsed (STAGE D), persist *all* transaction objects to the `transactions` table in the finance DB (data/database/finance.db). Store both raw and cleaned forms:
     - transaction_id (uuid)
     - user_id
     - document_id
     - date
     - merchant_raw
     - merchant_clean (apply clean_merchant_name)
     - merchant_normalized (after categorizer / merchant dictionary lookup)
     - amount
     - category (nullable)
     - subcategory (nullable)
     - confidence (float 0..1)
     - parsing_method ("regex" | "llm")
     - source_text (snippet or original raw line)
     - created_at
   - Persist document metadata in `documents` table (filename, owner, pages, upload_ts, ocr_confidence).
   - Persist phinance_raw_response & sanitized structured analysis when Phinance completes in `analysis` or `reports` table.

5. Specialist invocation (Phinance)
   - When user confirms specialist analysis: orchestrator uses persisted transaction records to build a Phinance payload via `home-ai/soa1/phinance_adapter.py` (method: build_phinance_payload).
   - Phinance is called with a structured JSON payload (currency locked to USD). Keep `keep_alive` and other model options configured to avoid cold starts.
   - The system must log a record of the invocation (who asked, when, payload hash) for auditability.

6. While Phinance runs
   - The orchestrator can use Nemotron (Qwen) on the persisted transactions to generate *preliminary insights* (short, non-specialist observations) that keep the user engaged.
   - If user explicitly requested preliminary findings in their consent, agent may reveal short items (e.g., "top spending category so far: Travel"). If user opted out, only show progress updates.

7. Deliverables
   - After Phinance completes, persist the structured results and generate the requested deliverables (dashboard JSON, PDF export, infographic prompt). Deliverables are gated by consent.

Event & API model (recommended)
- Upload endpoints (existing):
  - WebUI: POST /upload (returns redirect with doc_id)
  - SOA1 API: POST /upload-pdf (returns JSON payload with doc_id and job_id) — *recommend keeping both but unify behaviors*.
- Job & events:
  - Orchestrator creates a job_id for the upload and emits events: METADATA_READY, HEADERS_READY, PREVIEW_READY, TRANSACTIONS_READY, CONSENT_REQUEST, ANALYSIS_STARTED, ANALYSIS_COMPLETE, ERROR.
  - Event delivery options: SSE endpoint /events/{job_id} or WebSocket. Pollable alternative: /analysis-status/{doc_id} (already exists).
- Consent endpoints:
  - POST /analyze-confirm (already in soa-webui/main.py) — accepts doc_id and immediately returns "started" and spawns background _run_phinance_analysis(job, pdf_path).
  - POST /analysis-actions/{job_id} - enum: {confirm, cancel, deliverable_select}

Data Model (summary)
- `documents` (document_id PK, user_id, filename, pages, bytes, upload_ts, ocr_confidence)
- `transactions` (transaction_id PK, user_id, document_id, date, merchant_raw, merchant_clean, merchant_normalized, amount, category, subcategory, confidence, parsing_method, source_text, created_at)
- `merchant_dictionary` (merchant_raw PK, merchant_normalized, preferred_category, subcategory, transaction_type, last_seen_user_id, notes)
- `analysis_jobs` (job_id PK, doc_id, user_id, status, started_at, completed_at, error, phinance_raw_response, sanitized_analysis)

Merchant cleaning & categorization
- Use existing utilities in `home-ai/finance-agent/src/sanitizer.py` (clean_merchant_name, categorize_merchant) as the canonical cleaning step before saving `merchant_clean`.
- Normalization (merchant_normalized) and automated category suggestions should be produced by TransactionCategorizer (two-stage: Qwen normalization → Phinance refinement when confidence low).
- High-confidence category mappings (>0.85) are written back to `merchant_dictionary` for future use (user-scoped by default).

Consent & Orchestrator responsibilities (file-level)
- Implement per `FILE_CHECKLISTS.md`:
  - `home-ai/soa1/orchestrator.py` - central state machine (ConversationState, UserIntent, ConsentState), `handle_upload`, `handle_user_message`, `can_invoke_specialist`, `require_consent` (must raise/forbid if no consent).
  - `home-ai/soa1/parser.py` - staged parsing with generator/callback event emission: METADATA_READY, HEADERS_READY, DOC_TEXT_READY, TRANSACTIONS_READY.
  - `home-ai/soa1/doc_router.py` - advisory classification (document type & recommended intents) only.
  - `home-ai/agents/phinance_adapter.py` - build Phinance payload; strict input validation & USD lock.
  - `home-ai/soa1/report_builder.py` - build deliverable payloads (web JSON, PDF, infographic prompt).
  - `src/storage.py` or `home-ai/finance-agent/src/storage.py` - implement SQLite schema and DAO functions used by the orchestrator and parser (save_transaction, get_transactions_for_doc, get_user_transactions, save_analysis_job).

Testing & Acceptance Criteria
- Parser unit tests: staged parsing events emitted for sample PDFs (STAGE A..D).
- Orchestrator tests: explicit consent required; attempts to call Phinance without consent raise and are logged.
- Persistence tests: parsed transactions saved with all required fields and retrievable (no re-parse required).
- Integration test: Upload → Stage B event → agent consent request → confirm → Phinance invoked → analysis saved → deliverable generated.
- E2E performance target: per practical MVP target, typical single-document analysis end-to-end should be under a configurable threshold (default 90s); instrument per-step timing for CPU/Ops visibility.

Operational notes & recommendations
- Use `keep_alive: -1` and model pre-warm where possible to avoid cold starts for Nemotron & Phinance.
- Avoid exposing raw transactions to external networks; persist locally and apply file-system permissions by default.
- Consider an optional encrypted DB for households that request additional protection.
- Add a household settings toggle for "Allow preliminary agent insights while Phinance runs" (defaults to true for single-user installations, but must be explicit in multi-user households).

References
- RemAssist/IMPLEMENTATION_GUIDE.md (consent & staged parsing rules)
- RemAssist/FILE_CHECKLISTS.md (per-file responsibilities)
- FINANCE_MVP_PLAN_V2.md (architecture, data models & DB schema)
- home-ai/finance-agent/src/parser.py (parsing code)
- home-ai/finance-agent/src/sanitizer.py (merchant cleaning utilities)

Notes / Open items
- I looked for `FINANCE_MVP_PLAN_V3.md` in the repository but did not find it; we used `FINANCE_MVP_PLAN_V2.md` + `finance-mvp-implementation-guide.md` as canonical references for this doc.

Next steps (implementation suggestions - immediate)

1. Implement `home-ai/soa1/orchestrator.py` (state machine + consent enforcement) — MUST implement first (see FILE_CHECKLISTS.md).
2. Implement `home-ai/soa1/parser.py` to emit staged parsing events and persist METADATA/HEADERS immediately.
3. Implement `home-ai/finance-agent/src/storage.py` with `save_transaction()` and `save_analysis_job()` helpers and DB schema migration script.
4. Add an SSE / WebSocket endpoint to stream events to the UI (or implement a strong polling alternative) and update UI to show canonical acknowledgement + consent prompt.
5. Add unit and integration tests described in Testing & Acceptance Criteria.

Model management & startup (required)

- NemoAgent is the canonical orchestrator and is the ONLY model allowed to directly interface with the client (UI). All user-facing messages must be generated by NemoAgent (alias: `NemoAgent:latest`), not by specialist models.
- The WebUI must verify Ollama is running and that the configured models are available and loaded on startup. Use `soa-webui/model_manager.py` (ModelInitializer) via `initialize_on_startup()` to:
  - Check Ollama service health.
  - Verify available models include the configured orchestrator (`NemoAgent`) and the finance specialist (`phinance-json`). Support both bare names and `:latest` aliases.
  - If a required model is not already loaded, attempt to load it (respect `use_modelfile` semantics — see Phinance notes). Loading must set `keep_alive: -1` and appropriate options (e.g., `num_ctx`, `num_gpu`) so models remain resident.
- If initialization fails, the WebUI must display a clear status message and log the error. Model initialization failures are operational blocking issues for the test flow.

Phinance model (special handling)

- The Phinance model is expected to be packaged with a Modelfile (system prompt baked in). It should be referenced as `phinance-json` (or `phinance-json:latest`) in `home-ai/soa1/config.yaml` and finance-agent config.
- When `use_modelfile: true` is set for a model, the loader should NOT override the system prompt at load time (do not push a different system prompt into the model). Instead, call the model using the model's native API shape (Ollama: `/api/generate` with `prompt`) and rely on the Modelfile to provide the authoritative system prompt.
- Phinance calls should use the `format: 'json'` convention (where supported) and always sanitize the raw response via `sanitize_phinance_response()` before persisting or presenting it to NemoAgent.

Model call logging (audit & debug)

- Every model call must be logged in a structured, JSONL format (append-only) with the following minimum fields:
  - timestamp_utc
  - model_name (resolved alias, e.g. `NemoAgent:latest`)
  - resolved_model (exact name returned by Ollama)
  - endpoint (e.g., `/api/chat`, `/api/generate`)
  - prompt_source (one of: `user`, `api`, `nemoagent`, `phinance_adapter`, `system`, `internal`) — who 'owns' the prompt
  - prompt_type (e.g., `system`, `user`, `assistant`, `model`)
  - prompt_text (truncated to configurable length, e.g., 2000 chars)
  - prompt_hash (sha256 of prompt_text) — for correlation without storing full PII
  - options (num_ctx, num_predict, num_gpu, keep_alive)
  - response_id (if provided by model)
  - response_text (truncated, optional full response saved to secure location)
  - latency_ms
  - status (`success` | `failure`)
  - error (if any)
- Store logs locally under `logs/model_calls.jsonl` with file permissions restricted. For privacy, add a config toggle to redact or omit sensitive tokens/PII from logs (default: redact).
- Implement a helper `home-ai/soa1/utils/model_logging.py::log_model_call(...)` and ensure all LLM wrappers (ModelClient, finance-agent/models, etc.) call it for every interaction.

Security & retention notes for logs

- Keep logs local only (no external transmission). Set restrictive file permissions (owner-only read). Consider short retention (30–90 days) by default, configurable.
- For debugging, optionally persist full responses to a secure `logs/model_responses/` directory (owner-only). The JSONL index should reference the file path (not duplicate full content) when responses are too large.

Assistant session persistence (developer note - 'Sisyphus will remember this')

- These decisions are recorded here and in `RemAssist/History.md`. For the human-maintainer / assistant workflow, Sisyphus (the assistant) will:
  - Append a clear, dated entry to `RemAssist/History.md` whenever this file is changed.
  - Treat this document as the canonical source for model & logging behavior.
  - Respect "working assumptions" listed here (NemoAgent=orchestrator, NemoAgent is the only UI-facing model, phinance modelfile semantics, model call logging).
- If you want persistent machine-parseable assistant assumptions, we can add `RemAssist/ASSISTANT_ASSUMPTIONS.json` (optional). Say the word and I will create it and keep it updated automatically.

Acceptance Criteria (for the WebUI→SOA1 test)

- On WebUI startup, `initialize_on_startup()` executes and returns success: NemoAgent and phinance-json are available and loaded (resolved to `*:latest`) and show `keep_alive` semantics in `ollama ps` (TTL: Forever).
- NemoAgent is the only model that produces direct UI-facing replies. Any direct specialist output is only used internally (persisted/sanitized) and never sent to the client without NemoAgent mediation.
- All calls to models produce a model_call JSON entry in `logs/model_calls.jsonl` with the required fields; at least one sample entry exists for NemoAgent and Phinance in the logs after a successful run.
- Phinance outputs are sanitized via `sanitize_phinance_response()` before being persisted.

Implementation checklist (small, testable items)

- [ ] Add `use_modelfile` flag to `home-ai/soa1/config.yaml` for specialist model configs (default: false; phinance: true).
- [ ] Update `soa-webui/model_manager.py` to respect `use_modelfile` (do not override system prompt when set).
- [ ] Add `home-ai/soa1/utils/model_logging.py::log_model_call` (JSONL writer + helper to redact PII when configured).
- [ ] Instrument all model wrappers: `home-ai/soa1/model.py` (ModelClient), `home-ai/finance-agent/src/models.py`, `soa-webui/model_manager.py` to call `log_model_call` for every request/response.
- [ ] Ensure webui startup runs `initialize_on_startup()` and surfaces any initialization failures in UI and logs (it already does — verify and add acceptance test).
- [ ] Add a small startup rehydration check in SOA1 that loads persisted `analysis_jobs` or scans `FINANCE_REPORTS_DIR` and rebuilds `_analysis_jobs` (so context survives a restart).
- [ ] Add an integration test that: loads WebUI, verifies models are loaded, uploads 12 sample PDFs, performs Stage A/B for each, confirms consent, waits for analysis, validates `transactions.json` and `analysis.json` exist for each doc, restarts SOA1, and verifies `api/chat` uses latest analysis context.

Document updated: 2025-12-25 — I recorded these changes in RemAssist/History.md for traceability.

