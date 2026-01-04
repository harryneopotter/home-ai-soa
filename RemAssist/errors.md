# 🐛 Error Tracking Log

This file tracks errors encountered during development, their root causes, and fixes applied.
Agents MUST update this file when encountering and resolving errors.

---

## Error Log

### 2026-01-03: Phases 2 & 3 Collapsed - Full Analysis Returned on Consent

**Error:**
```
User: "yes, analyze"
Response: [ENTIRE analysis with categories, merchants, drains, insights, AND output format prompt]
Expected: Immediate acknowledgment with interesting_findings, then poll for completion
```

**Context:** Testing progressive flow after Apple Card parser fix. When user consented to analysis, they received the complete analysis immediately instead of progressive engagement.

**Root Cause:**
In `agent.py` lines 563-578, when `[INVOKE:phinance]` was detected:
```python
phinance_result = self._invoke_phinance(document_context)  # BLOCKS!
answer = f"{answer_without_tag}\n\n{phinance_result}"      # Returns everything
```
This ran synchronously and returned the full analysis, collapsing Phases 2 and 3 into one response.

**Additional Issue:** Duplicate output format prompts appeared because both `_run_hybrid_analysis()` and `_format_analysis_response()` added "How would you like the report?" sections.

**Fix Applied:**
1. `agent.py`: When `[INVOKE:phinance]` detected with batch `status="ready"`:
   - Return `interesting_findings` immediately with engagement message
   - Return `trigger_phinance_background: batch_id` signal
   - Don't call `_invoke_phinance()` synchronously

2. `api.py`: Added `_run_phinance_background()` async function:
   - Triggered by chat endpoint when `trigger_phinance_background` present
   - Runs `agent._invoke_phinance()` in background via `asyncio.to_thread()`
   - Sets `state.status = "complete"` when done
   - Triggers output pre-generation

3. `api.py`: Enhanced `/api/batch/status/{batch_id}`:
   - When `status="complete"`, includes `analysis_summary` and `completion_message`
   - Frontend can poll and display completion message

4. `agent.py`: Removed duplicate output prompt from `_run_hybrid_analysis()`

**Status:** ✅ RESOLVED

---

### 2026-01-01: Upload Response Returns Hardcoded String Instead of LLM Response

**Error:**
```
User uploads PDFs → Response: "Received: Apple Card Statement - September 2025.pdf. Analysis ready."
Expected: Rich contextual response with document details and user options
```

**Context:** After Session 14 removed `consent_request` from upload API response (to fix specialist language exposure), the frontend fell back to a hardcoded string.

**Root Cause:**
- `soa-webui/templates/index.html` line 287 has:
  ```javascript
  const msg = `Received: ${file.name}. ${data.consent_request ? data.consent_request.message : 'Analysis ready.'}`;
  ```
- When `consent_request` is undefined (as intended after Session 14 fix), it falls back to "Analysis ready."
- The correct architecture: upload response should come from LLM, not hardcoded frontend strings

**Fix Applied:**
1. Modified `/upload-pdf` endpoint in `home-ai/soa1/api.py` to call `SOA1Agent.ask()` with document context after successful upload
2. API now returns `agent_response` field with LLM-generated text
3. Updated `soa-webui/templates/index.html` to display `data.agent_response` directly

**Verified Result:**
```json
{
  "status": "UPLOADED",
  "doc_id": "finance-20260101-195110-e96226",
  "filename": "Apple Card Statement - April 2025.pdf",
  "pages": 6,
  "agent_response": "I've received **Apple Card Statement - April 2025.pdf**.\n\nFrom the first page, I can see:\n- A minimum payment of **$25.00**\n- A warning about interest charges if only minimum payments are made\n\nYou can:\n• Ask me a specific question about this statement\n• Get a quick summary of the transactions\n• Extract key details like dates, amounts, or merchants\n• Request a spending analysis (categories, patterns, etc.)\n\nNothing happens unless you say so. What would you like to do?"
}
```

**Reference:** See `RemAssist/LLM_DRIVEN_RESPONSES.md` for full architectural explanation.

**Status:** ✅ RESOLVED

---

### 2026-01-01: Chat Flow Bugs - Upload Response and [INVOKE:phinance] Handling

**Error 1:** Upload response violates protocol
```
Received: "I can involve the Finance Specialist for deeper insights. Do you want me to proceed?"
Expected: Simple acknowledgment with options, no specialist mention
```

**Error 2:** [INVOKE:phinance] tag returned verbatim to user
```
User: yes
Agent: [INVOKE:phinance]
Starting the financial analysis for your Apple Card statements...
```

**Error 3:** Agent exposes internal architecture
```
"I can involve the Finance Specialist" - exposes internal sub-agents
```

**Context:** User tested chat flow and found the upload response included a consent_request with specialist language, and the [INVOKE:phinance] tag was not intercepted.

**Root Cause:**
1. `api.py` lines 529-534 hardcoded `consent_request` with specialist language in upload response
2. `agent.py` had NO code to detect/handle `[INVOKE:phinance]` - LLM response returned verbatim
3. `orchestrator.md` prompt contained multiple references to "specialist", "finance specialist", "phinance"

**Fix Applied:**
1. `api.py`: Removed consent_request block from upload response (lines 520-549), kept simple upload confirmation
2. `agent.py`: Added `INVOKE_PATTERN` regex, `_invoke_phinance()` method, and detection in `ask()` method
3. `orchestrator.md`: Completely rewrote to remove ALL specialist mentions - agent now speaks as unified entity

**Verification:**
- Upload response now returns clean JSON: `{"status":"UPLOADED","doc_id":"...","filename":"..."}`
- Chat response for "analyze my spending": No specialist mention, proper consent flow
- [INVOKE:phinance] tag is intercepted and routed (log shows "Detected [INVOKE:phinance] signal - routing to phinance")

**Status:** ✅ RESOLVED

---

### 2026-01-01: Database Schema Mismatch - Missing doc_id Column

**Error:**
```
no such column: doc_id
```

**Context:** When user confirmed analysis ("yes"), the [INVOKE:phinance] handler tried to load transactions from SQLite but the `doc_id` column didn't exist in the transactions table.

**Root Cause:**
- `storage.py` schema definition includes `doc_id TEXT` in the transactions table (line 64)
- SQLite's `CREATE TABLE IF NOT EXISTS` does NOT alter existing tables
- The database was created before Dec 26, 2025 when `doc_id` was added to the schema
- Result: Code expected column that didn't exist in the actual database

**Fix Applied:**
```sql
ALTER TABLE transactions ADD COLUMN doc_id TEXT;
```

**Verification:**
```python
# Before fix
COLUMNS: ['id', 'user_id', 'date', 'description', 'amount', 'category', 'merchant', 'raw_merchant', 'created_at']

# After fix
COLUMNS: ['id', 'user_id', 'date', 'description', 'amount', 'category', 'merchant', 'raw_merchant', 'created_at', 'doc_id']
```

**Prevention:**
- Consider adding migration scripts for schema changes
- Or drop and recreate database after schema changes (acceptable for development)

**Status:** ✅ RESOLVED

---

### 2026-01-03: Batch Upload UX Broken — Two Responses + "0 Transactions" Shown Before Consent

**Error:**
```
User uploads 4 PDFs → Gets TWO separate responses:

[Response 1]: "I've received 4 Apple Card statements..."
              "Nothing happens unless you say so."

[Response 2]: "I've processed 4 documents and found 0 transactions."
              "Would you like me to run a detailed analysis?"

Expected (per BATCH_FLOW.md):
- Single acknowledgment with consent question
- No transaction count shown until AFTER consent + analysis
- Preliminary insights shown during processing
```

**Context:** User testing finance MVP demo. Uploaded 4 Apple Card statements via WebUI. The UX violates the 5-phase progressive pipeline defined in `BATCH_FLOW.md` and `complete-workflow-architecture.md`.

**Root Cause (Multiple Issues):**

1. **Two LLM responses instead of one** — The system is making two separate calls to NemoAgent, producing fragmented responses instead of a single cohesive acknowledgment.

2. **Transaction extraction runs BEFORE consent** — The system attempts to extract transactions immediately on upload, but either fails or returns 0. This count is then shown to the user prematurely.

3. **"0 transactions" exposed before analysis** — Per BATCH_FLOW.md Phase 3, transaction counts should only be shown AFTER user grants consent and Phase 2 background analysis completes. Currently shown in Phase 1.

4. **No background analysis (Phase 2 broken)** — The `phinance_prompt` should be pre-built during Phase 2 while user reads the acknowledgment. This doesn't appear to be happening.

5. **Missing status endpoint** — `GET /api/batch/status/{batch_id}` is documented as MISSING in BATCH_FLOW.md. Frontend cannot poll for batch state transitions.

6. **No preliminary insights** — Phase 3 should show preliminary insights ("📊 847 transactions found, 💰 Highest category: Dining") immediately on consent, but nothing is displayed.

**Expected Behavior (BATCH_FLOW.md):**

```
Phase 1 (T+0 to T+3s):
  User uploads → Single response:
  "I've received 4 Apple Card statements (May, March, June, July 2025).
   Would you like me to analyze your spending patterns?"

Phase 2 (Background):
  - Parse all PDF text
  - Extract transactions
  - Build phinance_prompt (cached)
  - Update batch status to "ready"

Phase 3 (After user says "yes"):
  Immediate response with preliminary insights:
  "Analyzing now! Here's what I noticed:
   📊 847 transactions found
   💰 Highest category: Dining $2,340"

Phase 4-5:
  Full analysis + output options
```

**Fix Required:**

| Issue | Fix Location | Action |
|-------|--------------|--------|
| Two responses | `api.py` upload handler | Single LLM call for acknowledgment |
| "0 transactions" shown early | `api.py` or `agent.py` | Don't show count until Phase 3 |
| Phase 2 not running | `batch_processor.py` | Verify background_analyze() executes |
| Missing status endpoint | `api.py` | Add `GET /api/batch/status/{batch_id}` |
| No preliminary insights | `agent.py` | Return cached insights on consent |

**Related Documents:**
- `RemAssist/BATCH_FLOW.md` — Defines the 5-phase pipeline
- `plan/current-plan/complete-workflow-architecture.md` — Full technical spec
- `RemAssist/IMPLEMENTATION_GUIDE.md` — Consent-first rules

**Partial Fix Applied (2026-01-03):**

The **second hardcoded message** has been removed. Root cause was in `soa-webui/templates/index.html`:

| Removed Lines | What They Did |
|---------------|---------------|
| 331-339 (old) | When `status === 'ready'`, constructed hardcoded message with transaction count |
| 348 (old) | When `status === 'complete'`, hardcoded "Analysis complete" message |

**Changes Made:**
- `pollBatchStatus()` no longer calls `appendMessage()` for status updates
- Only the status bar is updated (no chat messages)
- ALL chat messages must now come from LLM via the upload/chat endpoints

**Remaining Issues (still need fixing):**
- The **first response** also needs review — ensure it asks for consent properly
- Phase 2 background analysis may not be running
- Missing batch status endpoint

**Status:** ✅ PARTIAL FIX (hardcoded messages removed)

---

## Template for New Entries

```markdown
### YYYY-MM-DD: Brief Error Title

**Error:**
\`\`\`
Exact error message or traceback
\`\`\`

**Context:** What operation was being performed when error occurred.

**Root Cause:** Technical explanation of why the error happened.

**Fix Applied:** What changes were made to resolve it.

**Status:** ✅ RESOLVED | 🔄 IN PROGRESS | ❌ BLOCKED
```
