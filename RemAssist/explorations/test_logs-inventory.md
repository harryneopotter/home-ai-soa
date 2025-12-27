# Test Logs Inventory

## Overview
The `test_logs/` directory contains JSON Lines (.jsonl) logs and summary .md/.json files capturing detailed test run information from integration and performance tests. These logs provide per-step timing and status information for upload, stage-AB parsing, analysis, and report generation.

## Notable Files
- `multi_pdf_test_20251226.md` — Markdown summary of multi-PDF performance test
- `multi_pdf_test_20251226-*.json` — JSON exports of multi-PDF test run data
- `userflow_20251225-*.jsonl` — Userflow runs with detailed per-step events (upload_result, stage_ab, analyze_confirm_and_wait, reports_check)

## Typical Session Structure (from logs)
1. upload_result
2. stage_ab (header parsing / structure extraction)
3. analyze_confirm (consent confirmation + analysis run)
4. reports_check (verify transactions.json, analysis.json, dashboard outputs)

## Findings
- Tests consistently show Stage-AB (~8-10s) and analysis (~12-15s) as dominant contributors to runtime.
- Logs are complete and provide good evidence for bottleneck analysis.
- Log format is consistent and suitable for automated parsing and aggregation.

## Recommendations
- Centralize test logs under a retention policy to avoid disk growth
- Create an analyzer script to aggregate results across runs and generate dashboards for test performance trends
- Consider integrating selected test runs into CI for regression detection (e.g., per-commit timing regression checks)
