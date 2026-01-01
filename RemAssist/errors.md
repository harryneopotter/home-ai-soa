# 🐛 Error Tracking Log

This file tracks errors encountered during development, their root causes, and fixes applied.
Agents MUST update this file when encountering and resolving errors.

---

## Error Log

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
