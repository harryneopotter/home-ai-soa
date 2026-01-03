# Session 24 Summary — January 3, 2026

## Overview
Fixed batch upload persistence and WebUI proxy issues. Implemented Option A for batch state persistence (batch_id ↔ session_id + doc_ids mapping).

---

## Problems Solved

### 1. WebUI Batch Upload Creating Orphan Batch IDs
**Root Cause:** WebUI's `/api/proxy/upload-batch` was:
- Creating its own local `batch_id`
- Uploading files individually to `/upload-pdf`
- Never calling SOA1's `/upload-batch` endpoint
- Storing status in local `_batch_status` dict

**Fix:** Changed WebUI proxy to forward files directly to SOA1's `/upload-batch` and return SOA1's batch_id.

**File:** `soa-webui/main.py` (lines 1098-1126)

### 2. Batch State Not Persisted
**Root Cause:** `BatchProcessor` stored batches in-memory only (`self.batches` dict). Lost on restart.

**Fix:** Implemented Option A persistence:
- Added `batches` table to SQLite
- Added status change callback in `batch_processor.py`
- Save batch on creation, update on status change

### 3. Documents Not Saved During Batch Upload
**Root Cause:** `/upload-batch` extracted text but didn't call `save_document()` (unlike `/upload-pdf`).

**Fix:** Added document persistence in `/upload-batch` loop.

---

## Files Modified

| File | Changes |
|------|---------|
| `soa-webui/main.py` | Fixed `/api/proxy/upload-batch` to proxy to SOA1 |
| `home-ai/soa1/api.py` | Added document persistence in batch upload, status callback registration, new `/api/batch/session/{session_id}` endpoint |
| `home-ai/soa1/batch_processor.py` | Added `set_status_callback()` for persistence notifications |
| `home-ai/finance-agent/src/storage.py` | Added `batches` table, CRUD functions (`save_batch`, `update_batch_status`, `get_batch`, `get_batches_for_session`, `get_latest_batch_for_session`), migration for `doc_ids` column |

---

## New Database Schema

### `batches` table
```sql
CREATE TABLE batches (
    batch_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'uploading',
    file_count INTEGER DEFAULT 0,
    doc_ids TEXT,  -- JSON array of document IDs
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### New Endpoints
- `GET /api/batch/session/{session_id}` — Returns latest batch for session (for page refresh recovery)

---

## Current Persistence State

**What's persisted:**
| Table | Data |
|-------|------|
| `batches` | batch_id, session_id, status, file_count, doc_ids (JSON), timestamps |
| `documents` | document_id, filename, pages, bytes, upload_ts |

**What's NOT persisted (planned for next session):**
- Extracted text content
- Preliminary insights
- Phinance analysis results
- Pre-generated outputs

---

## Next Steps (Documented in NEXT_TASKS.md)

**Full Batch Persistence — Compressed Text Storage:**

```sql
ALTER TABLE batches ADD COLUMN extracted_text_gz BLOB;  -- gzipped, PII-cleaned
ALTER TABLE batches ADD COLUMN phinance_analysis TEXT;  -- JSON
```

**Flow:**
1. On upload: extract → clean PII → gzip → store
2. On recovery: decompress → rebuild BatchState
3. On Phinance complete: store analysis JSON

**Why compressed text instead of PDFs:**
- 10x smaller than PDF binary
- Can redact PII before storage
- Text gzips ~90%
- Instant recovery (no re-extraction)
- Auditable without PDF tools

---

## Services Status

| Service | Port | Status |
|---------|------|--------|
| SOA1 API | 8001 | Running (needs `PYTHONPATH=/home/ryzen/projects`) |
| WebUI | 8080 | Running |

**Start commands:**
```bash
# SOA1
cd /home/ryzen/projects/home-ai/soa1
PYTHONPATH=/home/ryzen/projects python3 api.py &

# WebUI
cd /home/ryzen/projects/soa-webui
python3 main.py &
```

---

## Test Verification

```bash
# Upload batch
curl -s -X POST http://localhost:8001/upload-batch \
  -H "X-Session-ID: test-session" \
  -F "files=@/path/to/file.pdf"

# Check persistence
python3 -c "
from home_ai.finance_agent.src import storage
storage.init_db()
print(storage.get_latest_batch_for_session('test-session'))
"
```

**Expected output:**
```python
{
  'batch_id': 'batch-xxx',
  'session_id': 'test-session',
  'status': 'ready',
  'file_count': 1,
  'doc_ids': ['doc-xxx'],
  ...
}
```

---

## Known Issues

1. **SOA1 exits after requests when started with nohup** — Works fine when started directly with `python3 api.py &`

2. **PYTHONPATH sensitivity** — Must use `/home/ryzen/projects` (not `/home/ryzen/projects/home-ai`) for `home_ai` imports to work

3. **Test PDFs in `/home/ryzen/projects/usb/`** — Corrupted (all zeros). Use `/home/ryzen/Documents/j666/` for valid PDFs.
