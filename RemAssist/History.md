### January 2, 2026 - Security Hardening: Rate Limiting (Session 20)

#### 🛡️ Rate Limiting Implemented
- **Feature**: Implemented token bucket rate limiting on public-facing API endpoints.
- **File Modified**: `home-ai/soa1/utils/rate_limiter.py`
- **Logic**: Configured `get_limiter_for_endpoint` to correctly map endpoints to specific limits:
    - `/upload-batch` and `/upload-pdf` use `pdf_limiter` (10 requests/minute).
    - `/ask-with-tts` uses `tts_limiter` (20 requests/minute).
    - All other endpoints (`/api/chat`, `/ask`, `/api/batch/consent`, etc.) use `api_limiter` (100 requests/minute).
- **Rationale**: Mitigates resource exhaustion and abuse, aligning with the project's security goals.

#### 📝 Security Scope Clarification
- **Decision**: Deferred comprehensive security measures (API Key Authentication, Audit Logging, HTTPS Enforcement) as the system is currently restricted to a local, on-premise network via Tailscale.
- **Action**: Added a dedicated task for comprehensive security hardening to the `NEXT_TASKS.md` for a future development phase.

#### 📝 Files Modified
- `home-ai/soa1/utils/rate_limiter.py` - Updated endpoint mapping.
- `RemAssist/History.md` - Updated with current session summary.
- `RemAssist/NEXT_TASKS.md` - Updated with final status and new deferred task.

---

### January 2, 2026 - Bug Fix and Input Validation (Session 21)

#### 🐛 Fixed `_invoke_phinance()` Tuple Unpacking Bug
- **Issue**: `call_phinance()` was updated to return `Tuple[str, int]` (response, attempts), but `_invoke_phinance()` still expected a plain string, causing a TypeError.
- **File Modified**: `home_ai/soa1/agent.py`
- **Fix**: Changed `raw_response = call_phinance(...)` to `raw_response, _ = call_phinance(...)`

#### 🧹 Code Cleanup
- Removed unnecessary comments in `analyze_batch()` function per project hook rules:
  - `# Merge transactions into the analysis dictionary`
  - `# --- Merchant Normalization ---`
  - `# ------------------------------`

#### 🛡️ Input Length Limits Added
- **File Modified**: `home_ai/soa1/api.py`
- **Constants Added**:
  - `MAX_MESSAGE_LENGTH = 10000` (chars)
  - `MAX_FILE_SIZE = 10 * 1024 * 1024` (10 MB)
  - `MAX_BATCH_ID_LENGTH = 100` (chars)
- **Endpoints Protected**:
  - `/api/chat` - message length validation
  - `/ask` - query length validation
  - `/ask-with-tts` - query length validation
  - `/upload-batch` - file size validation per file
  - `/api/batch/consent` - batch_id length validation
  - `/upload-pdf` - already had file size validation (10MB)

#### 📝 Files Modified
- `home_ai/soa1/agent.py` - Bug fix and comment cleanup
- `home_ai/soa1/api.py` - Input validation constants and checks

---

### January 2, 2026 - Logging Enhancements (Session 21 continued)

#### 📊 Enhanced Model Call Logging
- **Correlation IDs**: Added `correlation_id` field to link request/response pairs
  - Generated via `generate_correlation_id()` helper function
  - Format: `req-{12-char-hex}`
- **Attempt Tracking**: Added `attempt` field for retry scenarios
  - Each retry attempt is logged individually with its timing
- **Dynamic prompt_source**: Fixed `_dispatch_request()` to use `endpoint.name` instead of hardcoded "phinance"
  - NemoAgent calls logged as `prompt_source="nemoagent"`
  - Phinance calls logged as `prompt_source="phinance"`

#### 📝 Files Modified
- `home_ai/soa1/utils/model_logging.py` - Added `generate_correlation_id()`, `correlation_id` and `attempt` fields
- `home_ai/soa1/models.py` - Updated `_dispatch_request()` signature, added logging params to retry loop
- `home_ai/soa1/model.py` - Added correlation_id to NemoAgent logging

#### Log Entry Structure
```json
{
  "timestamp_utc": "2026-01-02T10:28:57.569827Z",
  "correlation_id": "req-deee1a444716",
  "attempt": 1,
  "model_name": "phinance-json:latest",
  "prompt_source": "phinance",
  "prompt_type": "request|response",
  "latency_ms": 18187.5,
  "status": "success"
}
```

---


### January 2, 2026 - Hardware Specs Documentation (Session 22)

#### 📄 Created Hardware Specs Document
- **New File**: `RemAssist/HARDWARE_SPECS.md`
- **Purpose**: Comprehensive hardware reference for AI agents to understand resource limits
- **Contents**:
  - System identity (hostname, OS, IP)
  - CPU specs (i5-12600K, 16 threads)
  - RAM specs (128 GB DDR5)
  - GPU specs (2x RTX 5060 Ti, 16GB each)
  - Current GPU allocation (NemoAgent ~10.7GB, phinance ~10.8GB)
  - Storage specs (2x 1TB NVMe)
  - Ollama model inventory
  - Resource planning matrix with decision guide

#### 📝 Updated Documentation
- **AGENTS.md**: Added HARDWARE_SPECS.md reference with mandatory GPU check rule
- **PROJECT_STATE.md**: Updated VRAM figures, added hardware specs reference
- **home-ai/ARCHITECTURE.md**: Corrected CUDA version (13.0), updated VRAM figures

#### 🎯 Key Decision
- Agents MUST check HARDWARE_SPECS.md before proposing new models or GPU-intensive features
- This prevents proposals that exceed available VRAM budget
