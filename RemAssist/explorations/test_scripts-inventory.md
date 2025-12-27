# Test Scripts Inventory

This report summarizes the test scripts used for integration and performance testing of the SOA1 pipeline.

## Summary
The `test_scripts/` directory contains primarily integration-style scripts that validate full pipelines (upload → stage A/B → consent → analysis → report). They are designed as standalone Python scripts and are not yet unified under pytest.

## Files and Purpose
- `integration_test_12_files.py` — E2E test across multiple PDFs, verifies resilience, and rehydration after WebUI restart.
- `multi_pdf_test.py` — Multi-PDF processing, timing and metrics collection, writes JSONL logs to `test_logs/`.
- `multi_pdf_timed_test.py` — Similar to `multi_pdf_test.py` with emphasis on per-document timing.
- `test_model_verification.py` — Verifies `/api/models/verify` endpoint and orchestrator model configuration.
- `test_seeding.py` — Tests `/api/analysis/seed` endpoint and report availability.
- `userflow_test.py` — Full user flow test including file upload, consent, and chat follow-up.

## Observations
- Tests are heavily focused on the finance pipeline and real model integration (NemoAgent, Phinance).
- Many helper functions are duplicated across scripts (e.g., upload, poll for status). Suggest extracting shared utilities and consolidating into `tests/` directory.

## Recommendations
1. Convert scripts into pytest tests under `tests/integration/finance_pipeline/`.
2. Add fixtures for launching/stubbing WebUI and SOA1 endpoints when needed.
3. Extract shared utilities into `tests/utils.py` (upload_pdf, wait_for_analysis, grant_consent).
4. Add configuration via `pytest.ini` or environment fixtures to decouple hardcoded paths.
