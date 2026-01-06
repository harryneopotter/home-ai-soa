# Master Issues & Fixes Plan

**Date**: January 6, 2026
**Status**: Consolidated Action Plan
**Source Documents**:
- `CRITICAL_REVIEW_20260106.md`
- `IMPROVEMENT_RECOMMENDATIONS.md`
- `VISION_GAP_ANALYSIS.md`
- `USER_FLOW_REVIEW.md`

---

## 🚨 Priority 1: Critical Stability (Data Loss & Hangs)

### 1. Analysis Persistence Failure
*   **The Issue**: `save_batch_phinance_analysis` (SQLite UPDATE) fails silently if the batch record is missing, causing analysis data loss.
*   **Safe Fix Strategy**:
    *   **Action**: Modify `home-ai/finance-agent/src/storage.py`.
    *   **Logic**: Check `cursor.rowcount` after the UPDATE.
    *   **Fallback**: If rowcount is 0, execute an `INSERT` statement to create the record.
    *   **Safety**: This is purely additive logic inside the function; existing callers won't know the difference, but data will be saved.

### 2. WebUI Event Loop Blocking
*   **The Issue**: `soa-webui/main.py` uses synchronous `requests.post` inside `async def` route handlers. Large uploads freeze the entire UI for all users.
*   **Safe Fix Strategy**:
    *   **Action**: Introduce `httpx` or `aiohttp` in `main.py`.
    *   **Logic**: Replace `requests.post` with `await client.post` in the `/api/proxy/upload` and `/api/proxy/upload-batch` endpoints.
    *   **Safety**: Only affects the implementation detail of the proxy function. The API contract remains identical.

### 3. "Zombie" Parsing Tasks
*   **The Issue**: Background tasks (extraction/analysis) can crash or hang, leaving the batch status as "parsing" forever. Frontend polls infinitely.
*   **Safe Fix Strategy**:
    *   **Action**: Update `batch_processor.py`.
    *   **Logic**: Add a timestamp check. When `get_batch_status` is called, if status is "parsing" and `started_at` > 10 minutes ago, auto-transition to "failed".
    *   **Safety**: Self-correcting read logic. Does not interfere with active tasks unless they stall unreasonably long.

---

## 🛠️ Priority 2: Architecture & Visibility

### 4. Missing Logging Endpoint (404)
*   **The Issue**: `/api/log/analysis/{doc_id}` is referenced by the UI plan but missing in code.
*   **Safe Fix Strategy**:
    *   **Action**: Add the endpoint to `home-ai/soa1/api.py`.
    *   **Logic**: Read lines from `logs/model_calls.jsonl`, filter by `doc_id` (if present in logs) or return the last N lines.
    *   **Safety**: New endpoint; no risk to existing flows.

### 5. Brittle Dynamic Imports
*   **The Issue**: `agent.py` imports `storage` inside methods, masking dependency errors.
*   **Safe Fix Strategy**:
    *   **Action**: Refactor `agent.py` imports.
    *   **Logic**: Move imports to the top level. Use a `try/except ImportError` block at the module level to set a global `STORAGE_AVAILABLE` flag, similar to how `api.py` handles it.
    *   **Safety**: Makes failures explicit at startup rather than runtime.

### 6. Merchant Logic Duplication
*   **The Issue**: `batch_processor.py` has a hardcoded regex dict that ignores the DB-backed `merchant_mappings`.
*   **Safe Fix Strategy**:
    *   **Action**: Create `home-ai/soa1/services/merchant_service.py`.
    *   **Logic**: Implement a class that encapsulates: DB Lookup -> Regex Normalizer -> LLM Fallback.
    *   **Integration**: Update `batch_processor.py` to use this service *if available*, falling back to the hardcoded dict only if the service fails.
    *   **Safety**: "Strategy Pattern" allows gradual migration.

---

## 🚦 Priority 3: User Experience

### 7. Infinite Frontend Polling
*   **The Issue**: `index.html` polls forever if status doesn't change.
*   **Safe Fix Strategy**:
    *   **Action**: Update `index.html` JS.
    *   **Logic**: Add a counter `pollAttempts`. If > 300 (10 minutes), stop polling and show "Request Timed Out".
    *   **Safety**: Client-side change only.

### 8. Double-Submission Race Condition
*   **The Issue**: User can click "Process" or send "Yes" multiple times while the backend is thinking.
*   **Safe Fix Strategy**:
    *   **Action**: Update `index.html`.
    *   **Logic**: Disable input/buttons immediately upon submission. Re-enable only on error or completion response.
    *   **Safety**: Standard UI best practice.

---

## 🔭 Priority 4: Strategic Modularization

### 9. Service Layer Extraction
*   **The Issue**: `agent.py` is a "God Object".
*   **Safe Fix Strategy**:
    *   **Action**: Create `home-ai/soa1/services/` directory.
    *   **Logic**: Move `_spawn_phinance_background` and `_invoke_phinance` logic into a `FinanceService` class.
    *   **Integration**: Inject `FinanceService` into `SOA1Agent`.
    *   **Safety**: Refactoring move. Can be done incrementally.

### 10. Containerization
*   **The Issue**: Manual `nohup` deployment.
*   **Safe Fix Strategy**:
    *   **Action**: Create `docker-compose.yml` in root.
    *   **Logic**: Define services for `soa1-api`, `webui`, `ollama` (if not external).
    *   **Safety**: Parallel deployment option. Does not break existing manual scripts.

---

## Execution Order

1.  **Immediate**: Fix Persistence (#1) and WebUI Async (#2).
2.  **Next**: Add Logging Endpoint (#4) and Timeout Logic (#3, #7).
3.  **Then**: Refactor Imports (#5) and Merchant Service (#6).
4.  **Finally**: Modularize (#9) and Dockerize (#10).
