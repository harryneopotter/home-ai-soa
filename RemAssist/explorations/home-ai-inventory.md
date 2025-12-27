# home-ai Directory Inventory

## Overview
The `home-ai` directory contains the SOA1 orchestrator, agent implementations, finance specialist adapters, memory integrations, and utility code. It's the primary home for the SOA1 service and its internal components (agents, models, PDF processing, and monitoring tools).

## Document Files

- **home-ai/ARCHITECTURE.md** — High-level architecture for SOA1: orchestrator, specialists, memory, model clients, and web UI.
- **home-ai/GEMINI.md** — Notes and experiments with Gemini models (research-only)
- **home-ai/PDF_DEMO_TESTING.md** — Guide for PDF processing and API endpoint testing (staging)

## Code Files

- **home-ai/soa1/agent.py**
  - Purpose: Core SOA1Agent class that orchestrates user queries, integrates memory, and calls ModelClient for inference.
  - Public classes/functions: `SOA1Agent` with `__init__`, `handle_message`, `_format_memory_context`, `_load_system_prompt`.
  - Key API calls: ModelClient.chat (synchronous, requests), MemLayer client calls to memory service, log_model_call.
  - Imports: requests, typing, yaml, logging, os, local utils (utils.model_logging)

- **home-ai/soa1/orchestrator.py**
  - Purpose: Manages conversation state machine, consent enforcement, and the mapping from user intents to actions (documents upload, specialist invocation).
  - Public classes/functions: `ConversationState`, `UserIntent`, `ConsentState`, `Orchestrator`, `handle_upload`, `handle_user_message`, `can_invoke_specialist`, `require_consent`.
  - Key features: Consent gating for specialist calls, minimal prompt drafting for confirmation, enforcement of the 'no automatic specialist calls'.

- **home-ai/soa1/model.py**
  - Purpose: `ModelClient` wrapper for Ollama / API usage with retry logic, logging, and robust response parsing for both native and OpenAI-compatible shapes.
  - Functions: `__init__`, `chat`, `_log_request`, `_log_response`.
  - Calls: requests.post to `{base_url}/api/chat`, structured log_model_call calls to model_calls.jsonl.
  - Important details: Adds `keep_alive: -1` in payload to pin models.

- **home-ai/agents/phinance_adapter.py**
  - Purpose: Build structured JSON payloads for the Phinance specialist and sanitize inputs (enforce USD, valid JSON), plus helper functions for financial report generation.
  - Functions: `build_phinance_payload`, `validate_phinance_payload`, `format_phinance_response`.

- **home-ai/soa1/pdf_processor.py**
  - Purpose: Simple PDF parsing utilities with page limits and text extraction using `pdfplumber`.
  - Functions: `extract_text`, `count_pages`.

- **home-ai/soa1/memory.py**
  - Purpose: Memory client integration with MemLayer - write/read functions and search with retry logic.
  - Functions: `write_memory`, `search_memory`, `delete_memory`.

- **home-ai/soa1/tts_service.py**
  - Purpose: Local TTS integration using Microsoft VibeVoice-Realtime-0.5B model. `VibeVoiceTTS` class with `synthesize_to_file` function.

- **home-ai/soa1/cli.py**
  - Purpose: CLI wrapper around the SOA1Agent (interactive and one-off modes).

- **home-ai/soa1/web_interface.py**
  - Purpose: FastAPI web interface providing home page, chat endpoint, upload endpoints, and health/status endpoints.
  - Endpoints: `/chat`, `/upload`, `/health`, `/analysis-events/{doc_id}` (SSE), `/analysis-timing/{doc_id}`.

- **home-ai/soa1/service_monitor.py**
  - Purpose: Service monitoring logic that aggregates service statuses, Ollama status, GPU usage, and exposes monitoring endpoints used by the WebUI.

- **home-ai/soa1/intents.py**
  - Purpose: Intent inference and confirmation extraction methods used by orchestrator to determine if consent is required.

- **home-ai/soa1/models.py**
  - Purpose: Model wrappers for Nemotron (orchestrator) and Phinance specialist. Uses OpenAI-compatible /v1 endpoint in some functions.
  - Key functions: `call_nemotron`, `call_phinance` (some calls use `/v1/chat/completions`), `_build_chat_payload`, `_dispatch_request`.

- **home-ai/soa1/doc_router.py**
  - Purpose: Classify document types and recommend intents (advisory only).

- **home-ai/soa1/parser.py**
  - Purpose: Staged parsing pipeline for PDFs. Emits events (METADATA_READY, HEADERS_READY, DOC_TEXT_READY) for orchestrator.

- **home-ai/soa1/report_builder.py**
  - Purpose: Build report payload formats (web, pdf, infographic) from analyzer output.

- **home-ai/soa1/utils/**
  - Files: `logger.py`, `errors.py`, `logging_utils.py`, `file_utils.py`, `rate_limiter.py`
  - Purpose: Centralized logging, error classes, rotating handlers, file tail utilities, rate-limiting middleware.

## Config Files

- **home-ai/soa1/config.yaml**
  - Keys: `server.host`, `server.port`, `memlayer.base_url`, `memlayer.user_id`, `model.provider`, `model.base_url`, `model.model_name`, `orchestrator.model_name`, `specialists.finance.model_name`, `tts.enabled`, `tts.model`, etc.

## Scripts

- `scripts/check_keepalive.py` — Smoke-check script for ModelClient.chat
- `scripts/start-soa1.sh`, `scripts/stop-soa1.sh` — start/stop SOA1 API

## Other Files

- **agents/** — placeholder agents (budgeting_agent, knowledge_agent, scheduler_agent) - empty stubs
- **finance-agent/** — standalone finance agent package with storage, models, parser; includes an on-disk `data/` directory with `finance.db`, `uploads/`, and `reports/`
- **memlayer/**, **memori/**, **cognee/** — supporting services for memory and ingestion (some with `main.py` and app servers)

## Issues & Duplication

- **Endpoint inconsistency**: Some model wrappers use native `/api/*` endpoints (ModelClient) and others use OpenAI-compatible `/v1` endpoints (home-ai/soa1/models.py, finance-agent), leading to inconsistent `keep_alive` behavior.
- **Multiple memory implementations**: There are different memory-related modules (memlayer, memori) with overlapping responsibilities; a single source-of-truth would reduce confusion.
- **Empty placeholder files**: Several `agents/*` files are placeholders which might be better documented or removed until implemented.
- **Doc & test spread**: Tests and utilities are scattered across directories (test_scripts, test_tests, soa-webui tests), making it harder to find the canonical test location.

## Next Steps
- Audit `home-ai/soa1/models.py` and finance-agent `models.py` for `/v1` vs `/api` use and standardize as needed.
- Consolidate memory client usage (prefer MemLayer) and document intended primary memory service.
- Move integration test scripts into `tests/integration/` and add fixtures for shared functionality.
- Consider renaming duplicate templates and consolidating `services.html` and `status.html` into a single authoritative copy.
