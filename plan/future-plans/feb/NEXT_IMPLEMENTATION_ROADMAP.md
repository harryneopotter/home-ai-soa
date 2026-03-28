# Next Implementation Roadmap (Robust Chat Agent + Two Tools)

**Branch target:** `feature/robust-chat-two-tools` (do not push until the first working slice is complete).

## Goal
Ship a robust main chat agent that:
- is aware of the system, its role, and its capabilities
- is aware of the active user and family members (identity + traits)
- can safely use at least two tools:
  - **Finance** (Phinance): consent-gated and CONTROL-gated
  - **Medical summarizer**: read-only, structured output only, CONTROL-gated

## Non-Negotiable Guardrails
- **CONTROL enforcement**: no specialist invocation unless `stage=READY` and `invoke_specialist` is in `CONTROL.allowed_actions`.
- **Consent**: no Phinance invocation pre-consent; no persistence without explicit consent scopes.
- **LLM-driven responses**: no user-facing text emitted by specialists/executor/persistence layers.
- **Phinance context**: `num_ctx=4096` for Phinance only; other agents may differ.

## Milestones (Do in Order)

### Milestone 1: Kernel identity + user context wired
**Outcome:** every request has an active `user_id` context and the main prompt reflects system + user/family info.
- Implement/finish kernel module (WHOAMI-backed identity).
- Wire `user_id` into API entrypoints and call `kernel.set_user_context(user_id)`.
- Inject `kernel.get_identity_prompt()` into the conversation LLM system prompt.
- Update memory client to be kernel-scoped (no config-hardcoded user).

### Milestone 2: Remove auto-invoke and enforce CONTROL-gated routing
**Outcome:** no hidden specialist calls; routing is fail-closed.
- Remove hardcoded `[INVOKE:phinance]` regex routing and keyword-based fallback in `agent.py`.
- Ensure specialist routing happens only via a router that checks:
  - CONTROL stage
  - CONTROL allowed_actions
  - required capabilities/consent

### Milestone 3: Add Medical tool (read-only specialist)
**Outcome:** second tool works end-to-end without persistence.
- Add a medical summarizer specialist under `home-ai/agents/` (silent; structured output only).
- Register it so the orchestrator can route to it.
- Confirm no database writes occur in this tool path.

### Milestone 4: Per-agent configs + unified model settings
**Outcome:** model + context settings are per-agent.
- Add per-agent configs for Finance and Medical (and Orchestrator).
- Ensure Phinance is pinned to `num_ctx=4096` and cannot be raised via config.

### Milestone 5: Smoke verification
**Outcome:** basic flows work and invariants hold.
- Upload finance docs → no Phinance until explicit consent + CONTROL allow.
- Upload medical docs → medical summarizer only runs when requested and allowed.
- Ask “who are you / who am I” → response reflects system + user/family identity.

## Definition of Done (for first “working slice”)
- Main chat agent responds with identity + capability awareness.
- Finance specialist invocation is blocked unless consent + CONTROL allow.
- Medical specialist returns structured summary and never writes to persistent storage.
- No hardcoded user-facing text leaks from non-LLM layers.
