# Plan Directory Inventory Report

## Document Files

- **plan/future-plans/self-correcting-mechanism.md** — Comprehensive design for a self-correcting AI system with structured logging, confidence scoring, backtracking triggers, and a three-tier night auditor for continuous improvement.
- **plan/current-plan/complete-workflow-architecture.md** — Detailed architecture for low-perceived-latency user workflow combining progressive PDF parsing, early intent confirmation, and parallel output generation.
- **plan/current-plan/low-latency-architecture-summary.md** — Summary of two-stage pipeline approach using smaller models for fast responses and larger models for overnight audits to achieve low latency while maintaining accuracy.
- **plan/current-plan/proposed-system.md** — Brainstorming document proposing a two-stage pipeline with Qwen 7B for parsing and Phinance Phi-3.5 for analysis, including testing strategies and alternative models.
- **plan/current-plan/gpt-research.md** — Extended discussion on self-correcting mechanisms, resource monitoring, unified logging, and overnight audit processes for multi-agent systems.
- **plan/home_assistant_update.md** — Updated project plan for local AI home-assistant infrastructure, including technical foundation, roadmap, and architecture overview.
- **plan/local_ai_home_assistant_infrastructure_project_plan.md** — Original comprehensive project plan for building offline AI assistant stack with phases, testing guidelines, and future enhancements.
- **plan/current-plan/Open-Source AI Agent Research.pdf** — PDF document on open-source AI agent research (content not extractable).
- **plan/current-plan/exportedfile.pdf** — Exported PDF file (content not extractable).
- **plan/current-plan/You are an expert software architect researching e.pdf** — PDF document titled with architect research prompt (content not extractable).

## Code Files

- **plan/current-plan/soa_dashboard.html** — Interactive financial dashboard web interface with metrics, charts, transaction tables, and insights; purpose: display financial analysis results in a user-friendly web UI.
  - Functions/classes: initializeChart(), generateMockTransactions(), updateStatusPill(), applyFilters(), sortBy(), renderTransactions(), renderPagination(), resetFilters(), exportCSV(), toggleHiddenDrains()
  - Key API calls: fetch() for loading JSON data, Chart.js for visualization
  - Top-level imports: Chart.js library, mock data object
- **plan/UI/code.html** — Secure web UI for SOA1 system status and services; purpose: provide a brutalist-style interface for monitoring system status and active services.
  - Functions/classes: None (static HTML with inline JavaScript)
  - Key API calls: None
  - Top-level imports: Tailwind CSS, Google Fonts, Material Symbols

## Config Files

- None identified in the plan directory.

## Scripts

- None identified in the plan directory.

## Other Files (Tests, Templates)

- **plan/current-plan/soa_dashboard.html** — Template for financial dashboard UI with mock data and interactive elements.
- **plan/UI/code.html** — Template for secure system status UI with Tailscale access indicators.

## Issues and Duplication

- **Overlapping Project Plans**: Multiple versions of the home assistant infrastructure plan exist (home_assistant_update.md and local_ai_home_assistant_infrastructure_project_plan.md) with similar content but different updates, potentially causing confusion on current roadmap.
- **Redundant Architecture Discussions**: Several documents cover similar themes of self-correcting systems and low-latency pipelines (self-correcting-mechanism.md, low-latency-architecture-summary.md, proposed-system.md, gpt-research.md), with overlapping concepts around logging, audits, and resource monitoring.
- **Duplicate PDF Research**: Three PDF files appear to be research or exported documents with unclear differentiation, possibly representing different stages of the same research without clear versioning.
