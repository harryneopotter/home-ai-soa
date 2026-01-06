# 🐛 E2E Analysis Persistence and Logging Failure

**Date**: January 6, 2026
**Session**: 35

## Summary

Instrumented E2E testing revealed that while the core analysis pipeline (upload, extraction, LLM processing) is fast and stable (approx. 15 seconds per document), the final persistence of the LLM output and the retrieval of LLM interaction logs are currently broken.

## Failures Observed

### 1. Analysis Persistence Failure (Critical)

- **Symptom**: The `phinance_analysis` JSON data, which contains the LLM's insights and recommendations, is not being saved to the `batches` table upon job completion.
- **Evidence**: Direct database query using `SELECT phinance_analysis FROM batches WHERE doc_ids LIKE ?` returned `NULL` or an empty row immediately after the job status changed to `"completed"`.
- **Error in Test Script**: `Phinance analysis not found for document [doc_id].`
- **Impact**: Blocks the final delivery of the analysis summary to the user and prevents downstream processing (e.g., PDF generation, dashboard population).

### 2. LLM Interaction Logging Failure

- **Symptom**: The API endpoint for retrieving detailed LLM interaction logs is missing or incorrect.
- **Evidence**: Attempting to fetch logs from `http://localhost:8001/api/log/analysis/{doc_id}` resulted in a `404 Client Error: Not Found`.
- **Impact**: Prevents detailed debugging and performance analysis of the LLM calls (e.g., prompt content, raw response, token counts, model latency).

## Next Steps

1.  Prioritize fixing the analysis persistence issue in the SOA1 service.
2.  Investigate and implement the correct endpoint for LLM interaction logs.
3.  Re-run the instrumented E2E test to verify fixes.
