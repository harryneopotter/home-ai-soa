# Current System Functionality (User Perspective)

## What the system is
SOA1 is a local-first home assistant that helps with document understanding and analysis, especially finance workflows. It runs on your machine and is designed to keep data local.

## What a user can do today

### 1) Chat normally
- Ask questions or request summaries.
- The assistant can answer based on current conversation context and (if enabled) memory.

### 2) Upload documents for analysis
- You can upload PDFs (bank statements, invoices, utility bills, general docs).
- The system reads structure and returns a response immediately.
- Background processing extracts metadata and prepares the analysis pipeline.

### 3) Ask for finance analysis
- After upload, you can explicitly request financial analysis.
- Finance analysis uses deterministic Python calculations plus a finance model for insights.
- The system can generate:
  - Spending summaries
  - Category breakdowns
  - Top merchants
  - Hidden drain detection

### 4) Choose report output format
Once analysis is complete, you can request:
- Web dashboard
- PDF export
- Infographic (if enabled)

## Consent behavior (user-facing)
- Uploading files grants permission to read and summarize them.
- Any action that **writes data** or **creates rules** requires explicit consent.
- Specialist invocation is gated by explicit intent (no silent, automatic specialist runs).

## Identity and user awareness
- The system now establishes an active user context per request.
- Identity prompt includes:
  - What the system is (name, nature, hardware awareness)
  - The active user and any stored traits
  - Known family members (if present in the identity manifest)

## What is not user-visible
These are internal behaviors that users do not see directly:
- CONTROL headers (policy enforcement layer)
- Consent and action gating
- Specialist router logic
- Memory propose/commit system

## Current limitations (user-visible)
- Only finance workflows are fully implemented end-to-end.
- Additional domain tools (medical, scheduling, general tasks) are not yet active.
- Family-aware personalization exists at the prompt layer, but UI-level user selection is limited to `X-User-ID` header routing.
