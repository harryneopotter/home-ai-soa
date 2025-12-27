# src Directory Inventory

## Overview
The `src` directory houses the LlamaFarm monorepo core: server, CLI, runtimes, docs, and designer UI. It's aimed at a broader audience and supports multi-runtime deployments, OpenAI-compatible API, and extension points for RAG (retrieval-augmented generation).

## Key Documents
- `src/README.md` — Monorepo overview, quickstart, and architecture details
- `src/AGENTS.md` — Agent guidelines and operational rules for AI agents working on the repo
- `src/CONTRIBUTING.md` — Contributor workflow and PR guidelines
- `src/docs/website/docs/...` — Docusaurus docs for API, configuration, and tutorials

## Notable Modules
- `src/server` — Python FastAPI server for project chat, datasets, and RAG APIs
- `src/cli` — Go-based CLI providing `lf` commands for project lifecycle and chat
- `src/runtimes` — Runtime providers (Ollama, Lemonade, Universal) with README and quickstarts
- `src/prompts` — Prompt management and examples

## Observations
- The `src` subtree is well-organized with dedicated documentation and mirrors standard LlamaFarm structure.
- OpenAI-compatible `/v1` endpoints are used heavily here for the universal runtime and server API.
- No immediate duplication issues were found in top-level docs, but runtimes and providers implement overlapping compatibility layers (e.g., `openai`-compat vs `ollama` native providers) which is intentional to support different backends.

## Recommendations
- Keep runtime provider differences documented (they're intentional). For SOA1-specific features (keep_alive pinning), prefer Ollama native endpoints where needed.
- No immediate code changes recommended in `src` as the module separation is logical and well-documented.
