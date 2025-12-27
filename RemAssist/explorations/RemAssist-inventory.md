# RemAssist Directory Inventory

## Document Files

- **ACTIONS_DETAILED.md** — Detailed action log documenting each step in consent and phinance implementation changes
- **CONSENT_PHINANCE_CHANGES.md** — Summary of consent endpoint implementation and phinance model logging additions
- **CRITICAL_REVIEW.md** — Comprehensive review of RemAssist project architecture, identifying critical issues and architectural concerns
- **ERROR_HANDLING_RATE_LIMITING_PLAN.md** — Detailed plan for implementing error handling and rate limiting in SOA1 system
- **errors.md** — Error tracking log with dated entries for debugging and institutional memory
- **FINANCE_MVP_EXECUTION_PLAN.md** — Finance intelligence MVP execution plan with implementation roadmap
- **FINANCE_UPLOAD_CONSENT_AND_PERSISTENCE.md** — Design document for finance upload flow with consent and persistence requirements
- **History.md** — Complete task history with dated entries for all major changes and implementations
- **IMPLEMENTATION_GUIDE.md** — Constitutional guide for user engagement and specialist invocation rules
- **IMPLEMENTATION_SUMMARY.md** — Summary of error handling and rate limiting implementation achievements
- **LLAMAFARM_SETUP_SUMMARY.md** — Analysis and setup summary for LlamaFarm integration
- **low-latency-architecture-summary.md** — Architecture summary for two-stage pipeline with self-optimization
- **MODEL_CONFIGURATION.md** — Configuration details for Qwen 2.5 7B model setup and performance
- **MODEL_UPGRADE_GUIDE.md** — Guide for upgrading models to maximize GPU utilization
- **NEXT_TASKS.md** — Unified task queue with current priorities and system snapshot
- **next-tasks.md** — Additional task tracking file (appears to be duplicate of NEXT_TASKS.md)
- **OLLAMA_CONFIGURATION_GUIDE.md** — Comprehensive guide for Ollama setup and embedding model integration
- **OLLAMA_MIGRATION_GUIDE.md** — Step-by-step guide for migrating Ollama models to dedicated storage
- **PDF_DEMO_TESTING.md** — Guide for PDF processing and API endpoint testing
- **SERVICES_CONFIG.md** — Configuration reference for all SOA1 services and hardware setup
- **SESSION_20251214_SUMMARY.md** — Session summary for December 14, 2025 with Ollama and model upgrade work
- **SESSION_20251224_SUMMARY.md** — Session summary for December 24, 2025 with finance MVP implementation
- **SESSION_SUMMARY.md** — Session summary for December 13, 2025 with web UI infrastructure setup
- **SOA1_ISSUES_AND_FINDINGS.md** — Documentation of SOA1 issues discovered during GPU migration and fixes applied
- **TEMPLATE_ISSUES.md** — Documentation of template issues in main.py and current working status

## Code Files

- No code files found in RemAssist directory

## Config Files

- **soa-webui.service** — Systemd service unit for SOA1 WebUI with security hardening, resource limits, and PYTHONPATH configuration
- **soa1-api.service** — Systemd service unit for SOA1 API with Uvicorn, security hardening, and resource limits

## Scripts

- No script files found in RemAssist directory

## Other Files

- No other files (tests, templates, etc.) found in RemAssist directory

## Issues and Duplication

- **Multiple Session Summaries**: Three separate session summary files (SESSION_20251214_SUMMARY.md, SESSION_20251224_SUMMARY.md, SESSION_SUMMARY.md) with overlapping content covering different time periods but similar structure
- **Duplicate Task Files**: Both NEXT_TASKS.md and next-tasks.md exist with similar content, potentially causing confusion about which is authoritative
- **Overlapping Documentation**: Multiple files cover similar topics (OLLAMA_CONFIGURATION_GUIDE.md, OLLAMA_MIGRATION_GUIDE.md, MODEL_UPGRADE_GUIDE.md all discuss Ollama/model configuration)
- **Redundant Implementation Docs**: Both IMPLEMENTATION_GUIDE.md and FINANCE_UPLOAD_CONSENT_AND_PERSISTENCE.md cover consent and specialist invocation rules
- **Scattered History**: History.md contains comprehensive history, but individual session summaries duplicate some historical information

The directory serves primarily as documentation and configuration storage for the RemAssist project, with no actual code implementation. The main issues are organizational - consolidating duplicate files and reducing overlap between documentation would improve maintainability.
