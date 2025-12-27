# Keep-Alive Remediation Plan

## Summary
During the Ollama migration and verification work we discovered inconsistent usage of Ollama endpoints across the codebase. Some modules call Ollama's native endpoints (`/api/*`) and include `keep_alive` in the payload to pin models, while others use OpenAI-compatible (`/v1/*`) endpoints. The OpenAI-compat endpoints do not propagate the `keep_alive` field (there are confirmed Ollama issues and code paths that omit keep_alive when mapping /v1 requests), causing models to be potentially unloaded between requests (cold starts and higher latency).

This plan documents findings and provides a concrete remediation roadmap to standardize model interactions so model pinning (keep_alive semantics) works reliably.

## Findings (evidence)
- `home-ai/soa1/model.py` (ModelClient) uses native `/api/chat` and sets `"keep_alive": -1` → models are pinned. Confirmed by `ollama ps` showing `UNTIL: Forever` for NemoAgent and phinance-json.
- `soa-webui/model_manager.py` uses `/api/generate` and sets `"keep_alive": -1` for load_model calls.
- `home-ai/soa1/models.py` and `home-ai/finance-agent/src/models.py` use `/v1/chat/completions` (OpenAI-compatible) and *may* include `keep_alive` in the payload which the /v1 compatibility layer does not forward into the runtime. This is a documented Ollama behavior and tracked in RemAssist/OLLAMA_MIGRATION_GUIDE.md and SOA1_ISSUES_AND_FINDINGS.md.
- `src/rag/components/embedders/ollama_embedder/ollama_embedder.py` calls `/api/embeddings` but doesn't set `keep_alive` (embedding workloads may benefit from pinned models during batch operations).

## Goals
1. Ensure model pinning is reliable where needed (analysis endpoints, specialist models, and any high-latency flows).
2. Standardize endpoints and test coverage so keep_alive semantics are verified by unit tests and continuous checks.
3. Reduce duplication and document a clear policy for using either native `/api/*` endpoints or a transparent shim when `/v1` compatibility is needed.

## Remediation Roadmap (concrete steps)

### Phase 1 — Quick safety fixes (1–2 days)
- Audit and convert the following files to use native Ollama endpoints and include `keep_alive: -1` where model pinning matters:
  - `home-ai/soa1/models.py` — replace `/v1/chat/completions` calls with `/api/chat` POSTs and adjust response parsing accordingly.
  - `home-ai/finance-agent/src/models.py` — same audit and conversion (preserve async behavior if using aiohttp).
- Add unit tests (fast) asserting the HTTP call target and payload include `keep_alive: -1`:
  - `test_tests/tests/test_model_keepalive.py` (exists) — ensure it runs in CI.
  - `test_tests/tests/test_soa1_models_keepalive.py` — new test for soa1/models.py.
  - `home-ai/finance-agent/tests/test_models_keepalive.py` — new test for finance-agent variant.
- Add a smoke script for local developers (e.g., `scripts/check_soa1_models_keepalive.py`) which can be run without pytest.

### Phase 2 — Consolidation & safety net (2–4 days)
- Add integration test that loads models via code paths and verifies `ollama ps` shows pinned (UNTIL: Forever). Run it conditionally if Ollama is present in CI or as a manual test step.
- Add linter/CI check that ensures `keep_alive` is present in payloads for functions that call `/api*/generate|/api/chat` when config indicates pinning required.
- Update documentation (RemAssist/OLLAMA_MIGRATION_GUIDE.md and KEEPALIVE_REMEDIATION_PLAN.md) with explicit guidance: "Use `/api/*` when you need `keep_alive` behavior; `/v1` may ignore keep_alive."

### Phase 3 — Optional compatibility shim & batching (phase-2)
- Design a small local shim service that accepts `/v1` and forwards to `/api` preserving `keep_alive` when present. Secure with loopback binding and optional token auth. Document trade-offs.
- For batch jobs (embeddings, bulk inference), add optional `keep_alive` handling to embedding code paths and long-running tasks.

## Rollout Plan (safe, one-file-at-a-time)
Follow the repo's one-file-per-iteration rule. For each conversion:
1. Create test(s) that assert intended behavior (target URL and payload include keep_alive).
2. Modify the file to use `/api` and `keep_alive: -1` (preserve behavior & signatures; minimal change).
3. Run lsp_diagnostics on the modified file and run the new test(s). Do not commit until tests pass locally or CI passes.
4. Record the change in `RemAssist/History.md` with evidence (unit test output & `ollama ps` showing pinned model).

## Risk & Rollback Plan
- Risk: Behavior change could break response parsing if the native Ollama response shape differs. Mitigation: ModelClient already contains robust parsing and fallback logic. Tests will include both native and OpenAI-compatible shapes.
- Rollback: Revert to previous version of the file (one-file change) and re-run tests. Ensure the previously passing test remains in place prior to commit.

## Who should review
- Owner: (You) — final signoff before committing PRs that change model endpoints.
- Reviewer: A backend engineer familiar with Ollama runtime and the finance pipeline.

## Next immediate actions (this session)
1. Update `RemAssist/NEXT_TASKS.md` with the remediation tasks (Phase 1 items as high priority).
2. Convert `home-ai/soa1/models.py` to use `/api/chat` and include `keep_alive: -1` (one-file, minimal patch), add unit test, add smoke-check script, run lsp diagnostics and tests locally.
3. If successful, plan and convert `home-ai/finance-agent/src/models.py` (iteration #2).


---

*Created by Sisyphus to document keep_alive remediation work and provide a safe rollout plan.*
