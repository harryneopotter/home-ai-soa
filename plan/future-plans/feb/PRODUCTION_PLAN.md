# SOA1 Production Framework: Implementation Plan
**Version:** 1.0 (Production Migration)
**Target Architecture:** Kernel-First / Multi-Tenant Isolation

---

## 1. Executive Summary
Transition SOA1 from an MVP (Single-User, Hardcoded) to a Production-Grade framework designed for commercialization as an **Appliance (Hardware + Software)**. The core of this transition is the **SOA1 Kernel**, which manages dynamic identity (Self-Awareness) and isolated user vaults (Social Intelligence), allowing for configurable user traits and onboarding.

## 2. Phase 1: Infrastructure & Core Logic (UPDATED)
- [x] **Create `WHOAMI.json`**: Define entity nature, hardware specs, and user placeholders.
- [x] **Implement `soa1/kernel.py`**: Central context manager with **User Profile Management** (registration, trait updates, persistence).
- [x] **Refactor `soa1/memory.py`**: Multi-tenant memory access via the Kernel.

## 3. Phase 2: Orchestrator & Appliance Onboarding
### 3.1 Orchestrator Refactor (`soa1/orchestrator.py`)
...
### 3.2 Appliance Onboarding Flow
- **Action:** Create a setup utility or API route to initialize the `primary` user and register family members.
- **Logic:** Use `kernel.update_user_profile()` to set custom traits (e.g., ADHD, interests) during first boot.
- **Action:** Modify the main message handler to extract `user_id` from the inbound event (Telegram/Voice).
- **Logic:**
  ```python
  from soa1.kernel import kernel
  def handle_message(user_id, text):
      kernel.set_user_context(user_id)
      identity = kernel.get_identity_prompt()
      # Pass identity as system prompt to Ollama
  ```
- **Goal:** Ensure every turn begins with a fresh context switch.

### 3.2 Specialist Client Refactor
- **Target:** `soa1/batch_processor.py` and `soa1/doc_router.py`.
- **Action:** Ensure any file writes or database reads use `kernel.get_scoped_db_path()` instead of static file names.

## 4. Phase 3: Data Isolation & Persistence
### 4.1 Database Scoping (`finance.db`)
- **Action:** Review all SQL queries. Ensure every `SELECT` and `INSERT` includes the `user_id` from `kernel.active_user.user_id`.
- **Alternative:** Implement "One File Per User" strategy using `kernel.get_scoped_db_path("finance.sqlite")` to create physical isolation between vaults.

### 4.2 File System Vaults
- **Action:** Move all user-uploaded documents to `vaults/{user_id}/documents/`.
- **Logic:** Use the `base_vault_dir` defined in the Kernel.

## 5. Phase 4: Dynamic Identity & Hardware Awareness
### 5.1 Hardware Monitoring Integration
- **Action:** Add a utility to `kernel.py` that queries `nvidia-smi` or `ollama ps`.
- **Goal:** Update the `identity_prompt` in real-time with current VRAM usage, ensuring the agent is aware of its operational limits.

## 6. Phase 5: Verification (Chaos Testing)
- **Tool:** Use the `chaos-tester` agent from the Gym.
- **Test Scenarios:**
    - **Isolation Breach:** Attempt to query User B's transactions while authenticated as User A.
    - **Identity Consistency:** Verify the agent correctly identifies as a "Local Assistant" even when pushed by adversarial prompts.
    - **Missing Vault:** Verify graceful handling when a new family member speaks to the system for the first time.

## 7. Migration Notes for Dev Server
1.  Move `WHOAMI.json` to the project root.
2.  Deploy `soa1/kernel.py`.
3.  Apply the `soa1/memory.py` refactor.
4.  **Restart Ollama** to ensure the Planner model (70B) and Executor models (16B) are assigned to separate GPUs as per the architecture design.

---
**Status:** Infrastructure Ready. Pending Phase 2 deployment.
