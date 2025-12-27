# Logs Inventory Report

## Overview
Logs are stored in multiple locations (`logs/`, `home-ai/soa1/logs/`, `soa-webui/logs/`, and `test_logs/`). The logging system is implemented using Python's logging module with `RotatingFileHandler`. Structured logs (JSONL) are used for model calls and test userflow traces.

## Key Points
- Primary logs: `agent.log`, `api.log`, `memory.log`, `model.log`, `pdf_processor.log` across service-specific directories
- Model calls are aggregated into `home-ai/logs/model_calls.jsonl` (structured JSONL)
- Test runs write JSONL logs to `test_logs/` for analysis

## Issues & Recommendations
1. **Duplicate filenames across services**: Standardize filenames, prefix with service name (e.g., `soa1-agent.log`)
2. **Duplicate model_call entries**: Investigate and fix duplicate entries in `model_calls.jsonl` (likely retry logic or duplicate logging)
3. **Centralize logs**: Consider central log directory or a simple convention for cross-service logs for easier troubleshooting
4. **Rotation & retention**: Implement and monitor log rotation and retention to prevent disk issues

## Next Steps
- Add a small script to parse `model_calls.jsonl` and deduplicate similar calls
- Add a health-check in start scripts that validates log files are being written to
- Create a `logs/README.md` documenting log locations and conventions
