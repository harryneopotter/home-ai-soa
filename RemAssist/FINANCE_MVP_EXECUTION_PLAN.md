# Finance MVP Execution Plan

**Date:** December 25, 2025
**Status:** Updated with dashboard output and architecture changes
**Hardware:** Intel X670 + 2x RTX 5060 Ti 16GB (32GB VRAM)
**Models:** NemoAgent (GPU 0) + phinance-json (GPU 1)

---

## Authoritative References

| Document | Purpose |
|----------|---------|
| `RemAssist/IMPLEMENTATION_GUIDE.md` | Constitutional guardrails (consent-first, banned language, USD-only, model roles) |
| `RemAssist/NEXT_TASKS.md` | Single source of truth for priorities and status |

---

## Current State

### ✅ Complete
- GPU migration and Ollama fix (models now use GPU, VRAM allocation verified)
- Model keep_alive and config fixes
- Dashboard output requirements validated
- Conversion utility planned (separate file)
- NemoAgent architecture clarified
- Unnecessary models unloaded

### ⚠️ Pending
- Implement dashboard JSON conversion utility (`utils/dashboard_json.py`)
- Integrate NemoAgent for anomaly/edge case handling in conversion
- Finalize architecture documentation and system prompt for NemoAgent
- Verify logging for all model actions, reasoning, tool calls (with timestamp)

---

## Execution Steps

### Step 1: Dashboard JSON Conversion Utility
- Write utility to convert phinance output to dashboard format
- Handle anomalies/edge cases using NemoAgent
- Validate output against dashboard requirements

### Step 2: Architecture Documentation & System Prompt
- Document SOA1 architecture (NemoAgent as orchestrator)
- Create comprehensive system prompt for NemoAgent

### Step 3: Logging Verification
- Ensure all model actions, reasoning, tool calls are logged with timestamp
- Audit logs for completeness and debugging

---
