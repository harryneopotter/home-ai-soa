# Robust Chat Agent (Two Tools) Plan

Goal: main chat agent is system-aware, user/family-aware, and can safely
invoke two tools (Finance + Medical) without breaking consent/CONTROL rules.

## File-by-File Task List

- `home-ai/soa1/kernel.py`
  - Implement/finalize kernel: load `WHOAMI.json`, manage `user_id`, build identity prompt (system + user/family traits).

- `home-ai/soa1/api.py`
  - Extract `user_id` from request, call `kernel.set_user_context(user_id)` before any LLM call.

- `home-ai/soa1/agent.py`
  - Use `kernel.get_identity_prompt()` as system prompt.
  - Remove hardcoded `[INVOKE:phinance]` auto-invoke and backup trigger.
  - Route specialist calls only through the router and CONTROL checks.

- `home-ai/soa1/orchestrator.py`
  - Ensure CONTROL allowlist and consent gating for any specialist invocation.
  - No direct specialist calls.

- `home-ai/soa1/specialist/registry.py`
  - Load specialists from `home-ai/agents/` or a registry file.

- `home-ai/soa1/specialist/router.py`
  - Enforce CONTROL stage + allowed actions + consent before routing.

- `home-ai/soa1/memory/client.py`
  - Remove hardcoded `user_id`/`profile_id` from config; read from kernel context.

- `home-ai/agents/medical_summarizer.py`
  - New specialist: read-only, structured output only, no persistence.

- `home-ai/agents/registry.yaml`
  - Register `finance_specialist` + `medical_summarizer` with configs.

- `home-ai/agents/configs/finance.yaml`
  - Set Phinance model + `num_ctx=4096`.

- `home-ai/agents/configs/medical.yaml`
  - Set medical model + context size (can be larger).

- `home-ai/soa1/models.py`
  - Load per-agent configs; enforce 4096 only for Phinance.

- `home-ai/soa1/model.py`
  - Use orchestrator agent config instead of global `config.yaml`.

## Minimal Safe Patch Set (Phases 1–3 Only)

This set delivers a robust main agent plus Finance + Medical tools with
consent/CONTROL enforced.

1. Kernel wiring
   - `home-ai/soa1/kernel.py`
   - `home-ai/soa1/api.py`
   - `home-ai/soa1/agent.py`
   - `home-ai/soa1/memory/client.py`

2. CONTROL-gated specialist routing
   - `home-ai/soa1/orchestrator.py`
   - `home-ai/soa1/specialist/router.py`
   - `home-ai/soa1/specialist/registry.py`

3. Second tool (medical, read-only)
   - `home-ai/agents/medical_summarizer.py`
   - `home-ai/agents/registry.yaml`

4. Phinance guardrail
   - `home-ai/soa1/models.py` (Phinance stays `num_ctx=4096`)

## Detailed Step-by-Step Plan

1) Kernel + identity awareness
- Add/confirm `home-ai/soa1/kernel.py` and load `WHOAMI.json`.
- Define `set_user_context()` and `get_identity_prompt()`.
- Ensure kernel exposes vault/db scoping helpers.

2) API entrypoint wiring
- In `home-ai/soa1/api.py`, extract `user_id` from request and call `kernel.set_user_context(user_id)` before any LLM call.
- Pass `user_id` through upload and chat handlers consistently.

3) Agent prompt injection
- In `home-ai/soa1/agent.py`, use `kernel.get_identity_prompt()` as the system prompt.
- Ensure user/family traits from `WHOAMI.json` are reflected.

4) Remove auto-invoke and direct specialist calls
- Delete `[INVOKE:phinance]` backup trigger in `home-ai/soa1/agent.py`.
- Stop direct Phinance calls outside the specialist router path.

5) CONTROL-gated routing
- In `home-ai/soa1/orchestrator.py`, enforce CONTROL allowlist + consent gating before any specialist call.
- Ensure `invoke_specialist` is only allowed when stage is READY and consent is confirmed.

6) Specialist registry alignment
- Update `home-ai/soa1/specialist/registry.py` to load specialists from `home-ai/agents/` or `home-ai/agents/registry.yaml`.
- Ensure the registry only exposes silent, structured-output specialists.

7) Specialist router enforcement
- In `home-ai/soa1/specialist/router.py`, check:
  - CONTROL stage == READY
  - `invoke_specialist` in allowed actions
  - consent scopes satisfied
- Fail closed if any rule is violated.

8) Add medical specialist (read-only)
- Create `home-ai/agents/medical_summarizer.py` as a silent tool.
- Output structured JSON only (no user text).
- Register it in `home-ai/agents/registry.yaml`.

9) Per-agent configs
- Add `home-ai/agents/configs/finance.yaml` with `num_ctx=4096`.
- Add `home-ai/agents/configs/medical.yaml` with its own model settings.
- Ensure orchestrator config is separate from specialist configs.

10) Model loader cleanup
- Update `home-ai/soa1/models.py` to load per-agent configs and only enforce 4096 for Phinance.
- Update `home-ai/soa1/model.py` to read the orchestrator agent config.

11) Memory scoping
- Update `home-ai/soa1/memory/client.py` to read user/profile from kernel context.
- Block memory calls if no active user.

12) Smoke verification
- Upload finance doc → no Phinance until consent + CONTROL allow.
- Upload medical doc → medical summarizer runs only when requested and allowed.
- Ask “who am I / who are you” → system + user/family identity reflected.
