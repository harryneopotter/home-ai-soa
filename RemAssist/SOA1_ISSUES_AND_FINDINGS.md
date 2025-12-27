# SOA1 — Issues, Actions & Findings (2025-12-25)

Purpose
- Record the critical issues discovered during the GPU migration & E2E verification session, the exact actions taken, observed evidence (E2E runs & timings), and recommended next steps. This is a short, actionable reference for Phase 1 decisions.

Scope
- Services: SOA1 API (home-ai/soa1), WebUI (soa-webui), Ollama models (NemoAgent, phinance-json), Finance agent (home-ai/finance-agent)
- Timeframe: Dec 25, 2025 — post-GPU migration verification

Critical issues discovered
1. keep_alive parameter ignored when using OpenAI-compat endpoint (`/v1/chat/completions`) on Ollama
   - Symptom: `keep_alive: -1` silently ignored → models can be unloaded between requests → cold-start latency
   - Impact: Higher response latency; unpredictable VRAM usage
2. Inconsistent Ollama endpoint usage across modules
   - Some modules call `/v1/chat/completions`, others use `/api/generate` or `/api/chat` → inconsistent behavior and feature support
3. Various operational bugs discovered and fixed during the session
   - Timer bug in tests (return inside Timer context caused 0.0s durations) — fixed in `soa-webui/test_finance_pipeline.py`
   - WebUI static/templates path issue when started from a non-CWD — fixed in `soa-webui/main.py`
   - Duplicate POST in `soa-webui/model_manager.py` — removed

Actions taken (what we changed)
- Switched SOA1 ModelClient to use Ollama native `/api/chat` endpoint so `keep_alive` is honored
  - File: `home-ai/soa1/model.py`
  - Added robust parsing to accept native Ollama shapes (data["message"]["content"]) and fall back to OpenAI-compatible shapes (choices[0].message.content) and other common shapes
  - Added optional response id logging for observability
- Validated model preload and GPU allocation
  - Ensured `num_gpu` use where appropriate (model manager changes earlier)
  - Verified via `ollama ps` that models show `Forever` TTL after the change
- Fixed test & web issues
  - Fixed Timer return bug in `soa-webui/test_finance_pipeline.py`
  - Fixed static/templates path handling in `soa-webui/main.py`
  - Removed duplicate POST in `soa-webui/model_manager.py`
- Cleared caches & duplicate uploads where necessary and restarted services to ensure fresh state

Evidence & E2E results
- E2E userflow run (script: `test_scripts/userflow_test.py`) produced JSONL log:
  - `test_logs/userflow_20251225-215105.jsonl`
- Key E2E timings (single successful run)
  - Run start: 2025-12-25T21:50:15.508063Z
  - Run completed: 2025-12-25T21:51:05.009824Z
  - Total TAT: 49.502s
  - Per-step breakdown:
    - upload: 0.005s (0.0%)
    - stage_ab (structure preview): 8.434s (17.0%)
    - analyze_confirm (analysis polling + processing): 34.573s (69.8%)  ← dominant
    - check_reports: 0.000s (0.0%)
    - chat_followup: 6.488s (13.1%)
- Observations
  - The analysis step (`_run_phinance_analysis`) is the dominant contributor to TAT (extraction + phinance insights LLM call).
  - After switching to `/api/chat`, `ollama ps` shows models with `UNTIL: Forever` (pinned) and no observed TTL regressions during the test run.

Findings & implications
- Switching ModelClient to Ollama native `/api/chat` is low-risk and high-impact: it fixes the `keep_alive` behavior with a small change and no public API change (ModelClient.chat still returns a string).
- Standardizing endpoint usage (prefer Ollama `/api/*` for local runtimes) avoids surprises later and keeps keep_alive semantics consistent.
- The analysis pipeline needs better instrumentation: identity, summary, extraction, phinance call, and saving should each have fine-grained timings logged for future performance work.

Recommendations (next steps, suggested priorities)
1. High priority
   - Add unit/integration tests that assert ModelClient includes `keep_alive` in payload and that payload uses `/api/chat` (or that the compatibility shim is respected). Also add tests to mock response shapes (native & OpenAI). (Effort: ~30–60m)
   - Add an E2E smoke check that asserts total TAT < 90s (or a threshold that makes sense for the MVP). (Effort: ~30–60m)
2. Medium priority
   - Instrument `_run_phinance_analysis` with fine-grained timers (identity, summary, extraction, phinance_insights, save) and log them to the analysis job record. (Effort: 1–2 hrs)
   - Consider pre-warming / preloading strategies (run `analyze-stage-ab` on upload or add a pre-warm endpoint) to reduce first-run overhead where appropriate. (Effort: 1–2 hrs)
3. Low priority (phase-2)
   - Implement a small OpenAI-compat shim/proxy that exposes `/v1/chat/completions` and internally calls `/api/chat` while preserving `keep_alive` so frameworks like LlamaFarm can work unchanged. Bind to localhost or add simple access control. (Effort: 1–3 hrs)

Artifacts / Files touched in this session (working tree — not committed)
- Modified
  - `home-ai/soa1/model.py` — switched to `/api/chat`, robust parsing, resp id logging
  - `soa-webui/model_manager.py` — `num_gpu` change & duplicate POST removal (from earlier changes during the session)
  - `soa-webui/test_finance_pipeline.py` — test Timer fix
  - `soa-webui/main.py` — static/templates path fix, analysis job background behavior
  - `RemAssist/History.md` — updated (session note)
- New
  - `RemAssist/SOA1_ISSUES_AND_FINDINGS.md` (this document)
- Evidence logs
  - `test_logs/userflow_20251225-215105.jsonl` (E2E run with per-step durations)

Notes / Constraints
- No commits were made to git in this session (per project rules). If you want a commit + PR for these doc & code changes, tell me and I will prepare a commit message and stage the changes.
- The OpenAI-compat shim is intentionally deferred to Phase 2 when LlamaFarm integration is underway.

If you'd like, I can:
- Add the recommended tests (keep_alive assertion and E2E TAT threshold) now, or
- Instrument `_run_phinance_analysis` timers and re-run E2E to produce more granular timings, or
- Start a small design doc for the Phase-2 OpenAI compatibility shim (security & API surface).

---
Generated: 2025-12-25 by Sisyphus (assistant) — file created in working tree (not committed)
