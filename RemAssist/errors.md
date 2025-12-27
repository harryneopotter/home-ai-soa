# 🐛 Error Tracking Log

This file tracks errors encountered during development, their root causes, and fixes applied.
Agents MUST update this file when encountering and resolving errors.

---

## Error Log

### 2025-12-26: Module Import Error - `home_ai` not found

**Error:**
```
ModuleNotFoundError: No module named 'home_ai'
```

**Context:** WebUI (`soa-webui/main.py`) failed to start after restart.

**Root Cause:** 
- The code imports `from home_ai.soa1.utils.logging_utils import setup_logging`
- The actual directory is `home-ai` (with hyphen), not `home_ai` (with underscore)
- Python module names cannot contain hyphens, so imports use underscores
- The previous long-running process had this working via unknown mechanism (possibly PYTHONPATH or cached imports)

**Fix Applied:**
1. Created symlink: `ln -s /home/ryzen/projects/home-ai /home/ryzen/projects/home_ai`
2. Set PYTHONPATH when starting WebUI: `export PYTHONPATH="/home/ryzen/projects:${PYTHONPATH:-}"`

**Status:** ✅ RESOLVED

---

### 2025-12-26: Module Import Error - `home_ai.finance_agent` not found

**Error:**
```
ModuleNotFoundError: No module named 'home_ai.finance_agent'
```

**Context:** WebUI started but `/analyze-confirm` endpoint failed with 500 error.

**Root Cause:**
- Similar to above, but for the nested directory
- Code imports `from home_ai.finance_agent.src import storage`
- The actual directory is `finance-agent` (with hyphen)

**Fix Applied:**
1. Created symlink: `ln -s /home/ryzen/projects/home-ai/finance-agent /home/ryzen/projects/home-ai/finance_agent`

**Status:** ✅ RESOLVED

---

### 2025-12-26: Job Record Not Found - `/analyze-confirm` returns 404

**Error:**
```json
{"detail":"Job record not found; upload required"}
```

**Context:** Smoke test fails at `/analyze-confirm` step. Upload and stage-ab succeed, but analyze-confirm cannot find the job.

**Root Cause:**
- The `/analyze-stage-ab` endpoint (line 572 in `main.py`) only saves document metadata IF a job already exists
- It never creates a new job record for new uploads
- The `/analyze-confirm` endpoint (line 613) expects the job to exist in the database
- Previous test runs worked because old job records matched by coincidence or the old process had stale in-memory state

**Code Path:**
```python
# analyze_stage_ab (line 572-573) - BUG
job = fa_storage.load_job_by_doc_id(req.doc_id)
if job:  # <-- Only saves if job EXISTS, never creates one!
    fa_storage.save_document(...)
```

**Fix Applied:**
- Modified `analyze_stage_ab` function in `soa-webui/main.py` (line 572-580)
- Added logic to create job record if `load_job_by_doc_id` returns None
- Uses `fa_storage.create_analysis_job()` with generated job_id

**Status:** ✅ RESOLVED

---

### 2025-12-26: Consent Flow Missing - `/analyze-confirm` returns consent_required

**Error:**
```json
{"status": "consent_required", "message": "Consent required before analysis"}
```

**Context:** Smoke test `userflow_test.py` fails after stage-ab. The `/analyze-confirm` endpoint returns `consent_required` instead of `started`, causing `analysis-status` polling to fail with 404.

**Root Cause:**
- The consent-first architecture requires explicit user consent before specialist invocation
- New job records are created with `consent_given=0` (default)
- `/analyze-confirm` checks `if job_record.get("consent_given") != 1:` and refuses to start analysis
- The test script was missing the consent step between stage-ab and analyze-confirm
- Old tests passed because legacy job records had `consent_given=1` already set

**Fix Applied:**
- Added `grant_consent()` function to `test_scripts/userflow_test.py`
- Calls `POST /api/consent` with `{"doc_id": "...", "confirm": true, "specialist": "phinance"}`
- Inserted consent step in `main()` between stage-ab and analyze-confirm

**Status:** ✅ RESOLVED

---

### 2025-12-26: phinance-json Model Loads with 90% CPU / 10% GPU Split

**Error:**
```
ollama ps
NAME                    ID              SIZE      PROCESSOR          UNTIL
phinance-json:latest    ca839790957e    4.0 GB    90%/10% CPU/GPU    Forever
```

**Context:** Despite setting `num_gpu: 99` in `call_phinance_insights()` (models.py line 221), the model consistently loaded with only 1/33 layers on GPU, causing transaction extraction to take ~23s instead of ~3.6s.

**Root Cause:**
1. **Stale bytecode cache**: Python was using cached `.pyc` files that still had the old `num_gpu: 1` value
2. **Process not restarted**: The WebUI uvicorn process had been running since before the code change
3. **Ollama behavior**: `num_gpu` option only affects model loading, not already-loaded models. When phinance was reloaded (e.g., after timeout), it used the cached/stale code's `num_gpu: 1`

**Evidence from logs:**
```
# Ollama scheduler log during reload:
load_tensors: offloading 1 repeating layers to GPU
load_tensors: offloaded 1/33 layers to GPU

# Model call log showed stale value:
phinance | opts={'num_gpu': 1, 'num_thread': 1}  # Should be 99!
```

**Fix Applied:**
1. Cleared all `__pycache__` directories: `find /home/ryzen/projects/home-ai -name "__pycache__" -type d -exec rm -rf {} +`
2. Killed and restarted WebUI process
3. Manually reloaded phinance-json with correct GPU settings: `curl ... -d '{"model": "phinance-json:latest", "options": {"num_gpu": 99}, "keep_alive": -1}'`

**Prevention:**
- Always restart WebUI after modifying finance-agent code
- Consider adding `--reload` flag to uvicorn in development
- The `model_manager.py` initialization correctly sets `num_gpu: 99` at startup, so a clean restart will always work

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
