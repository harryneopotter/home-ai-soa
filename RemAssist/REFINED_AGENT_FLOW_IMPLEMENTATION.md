# 🎯 Refined Agent Flow & Instant Delivery Implementation Guide

**Reference**: `RemAssist/PROGRESSIVE_FLOW.md` (Canonical Spec)

## 1. Current State (Audit)

| Feature | Status | Location |
| :--- | :--- | :--- |
| **Output Tracking** | ✅ Exists | `BatchState.outputs` (dict with keys: `dashboard_json`, `pdf_command`, `infographic_prompt`) |
| **Output Endpoint** | ✅ Exists | `GET /api/batch/output/{batch_id}/{format}` in `api.py` |
| **Output Proxy** | ✅ Exists | `/api/proxy/output` in `soa-webui/main.py` |
| **Type Inference** | ✅ Exists | `SimplePDFProcessor._infer_document_type` in `pdf_processor.py` |
| **Background extraction** | ✅ Exists | `batch_processor.py` runs regex extraction in background |

---

## 2. Refined Flow Overview

| Phase | User Action | System/Agent Action |
| :--- | :--- | :--- |
| **1. Upload** | Uploads files | **System**: Saves files, extracts metadata, starts background extraction. <br> **Agent**: (LLM generated) "Looks like you have uploaded some <subject> related documents. Are you looking to get them analyzed or do you have any other queries?" |
| **2. Wait** | *User reads/thinks* | **System**: (Silent) Completes regex extraction and calculates "interesting findings". No extra LLM chatter. |
| **3. Consent** | "Yes, analyze" | **System**: Fires Specialist (Phinance) prompt. <br> **Agent**: "Started! While I work, I noticed you spent $X on Y this month. Results in a moment." (Uses pre-calculated findings to engage user). |
| **4. Done** | *User reads findings* | **System**: Specialist finishes. **Wraps Results** (JSON, PDF Command, Image Prompt) into `BatchState.outputs`. <br> **Agent**: "Analysis process completed. [Quick Summary]. How would you like the full report? 1. Web, 2. PDF, 3. Infographic" |
| **5. Delivery** | Selects option | **System**: Delivers pre-generated asset instantly (<1s). |

---

## 3. Data "Wrapping" for Instant Delivery

The "Wrap" step ensures that all components needed for the final report are consolidated and sitting in RAM ready for the user's selection.

### Final Report Components (The Wrap):
1.  **Calculated Numbers**: (Python) Totals, category spending, hidden drains.
2.  **Specialist Insights**: (LLM) Narrative observations and recommendations.
3.  **Raw Transactions**: (SQLite) The full list of extracted line items.

### Implementation Logic (`output_generator.py`):
- **`dashboard_json`**: Combine the calculated totals and LLM insights into the structured JSON expected by `soa_dashboard.html`. Include the full transaction list from the database.
- **`pdf_command`**: Build the shell command string with all data flags prepared.
- **`infographic_prompt`**: Build the specific image generation prompt based on the highest-spending category and total savings.

---

## 4. Modified Task List

1.  **Refine `OutputGenerator`**: Update the `generate_dashboard_json` method to utilize `home-ai/soa1/utils/dashboard_json.py` for comprehensive "wrapping" of Python + LLM data.
2.  **Subject-Aware Orchestration**: Ensure the Orchestrator knows its role via instructions in `orchestrator.md` and uses injected `interesting_findings` forauthoritative engagement during Specialist processing.
3.  **WebUI Batch Dashboard**: Implement `@app.get("/dashboard/batch/{batch_id}")` in `soa-webui/main.py` to serve the `soa_dashboard.html` template using the pre-generated batch JSON.
4.  **Instant Delivery Verification**: Run E2E test to confirm that picking "Web Report" loads the dashboard in <1 second using the cached data.