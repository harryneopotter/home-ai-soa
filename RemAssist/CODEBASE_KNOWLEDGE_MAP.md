# SOA1 Codebase Knowledge Map (February 2026)

## 1. Executive Summary
**SOA1 (Son of Anton)** is a local-first, privacy-focused home AI assistant. It specializes in high-accuracy financial analysis of documents (PDFs) while maintaining strict user agency through a capability-based consent model. The system is designed to run entirely on local consumer hardware with no cloud dependencies.

---

## 2. System Architecture & Services

### 2.1 Service Map
| Service | Port | Directory | Primary Role |
| :--- | :--- | :--- | :--- |
| **SOA1 API** | 8001 | `home-ai/soa1/` | Main backend, orchestrator, specialist routing. |
| **WebUI** | 8080 | `soa-webui/` | Dashboard, chat interface, PDF upload frontend. |
| **Ollama** | 11434 | External | LLM inference (NemoAgent, phinance-json, qwen2.5). |
| **MemLayer** | 8000 | External | Long-term vector memory. |
| **SQLite** | N/A | `finance-agent/data/` | Persistent storage (`finance.db`). |

### 2.2 Hardware Allocation (32GB Total VRAM)
- **GPU 0 (16GB)**: `NemoAgent:latest` (~13GB). Handles conversation, intent, consent, and critic pass.
- **GPU 1 (16GB)**: `phinance-json:latest` (~4GB). Handles transaction extraction and qualitative insights.

---

## 3. Core Logic & Components

### 3.1 Orchestration (`agent.py` & `orchestrator.py`)
- **`SOA1Agent.ask()`**: The main entry point for all queries. It coordinates memory retrieval, intent classification, and specialist invocation.
- **`[INVOKE:phinance]`**: A specific tag returned by the orchestrator model to signal that the specialist should take over.
- **Consent Gate**: Enforced by `orchestrator.py`. Explicit confirmation is required for any side-effect (DB writes, rule creation).

### 3.2 Progressive Batch Pipeline (`batch_processor.py`)
Implements a 5-phase background pipeline:
1. **Upload**: Returns in <30ms with quick metadata.
2. **Parsing**: Full PDF text extraction with PII redaction.
3. **Extraction**: Regex-based transaction extraction (Apple Card state machine or Generic Bank regex).
4. **Normalization**: Merchant categorization using 40+ patterns and stable ID hashing.
5. **Calculation**: Deterministic Python math for totals and categories.

### 3.3 Hybrid Calculation Architecture
Solves LLM arithmetic inaccuracy:
- **Python**: Calculates sums, counts, and percentages (100% accurate, 0.05ms).
- **LLM (qwen2.5)**: Generates qualitative insights and recommendations (5-6s).
- **NemoAgent Critic**: A final pass where the orchestrator validates the specialist output against the raw numbers.

---

## 4. Technical Invariants & Design Patterns

### 4.1 CONTROL Header System (`control_header.py`)
Every data chunk sent to the model is preceded by a `[CONTROL]` block specifying:
- **Stage**: `UPLOADING`, `PDF_PARSE`, `READY`, etc.
- **Capabilities**: `read_uploads`, `write_persistent`, etc.
- **Allowed Actions**: `classify_intent`, `invoke_specialist`, etc.
- **Invariant**: `invoke_specialist` is **ONLY** allowed when `stage=READY`.

### 4.2 Capability-Based Consent (M0.2)
- **Implicit**: `READ_UPLOADS`, `ANALYZE_DETERMINISTIC` (granted on upload).
- **Explicit**: `WRITE_PERSISTENT`, `CREATE_RULES`, `DEVICE_CONTROL`, `EXTERNAL_API`.

### 4.3 Merchant Stable IDs
Uses SHA-256 hashes of normalized merchant names to ensure graph linkage survives dictionary updates.

---

## 5. Detailed Data Flows

### 5.1 The "Analyze my spending" Flow
1. **User Uploads**: `POST /upload-batch` -> Creates `batch_id` -> Returns metadata.
2. **Background**: `BatchProcessor` extracts and calculates financials.
3. **User Chat**: "Analyze my spending" -> NemoAgent detects intent.
4. **Consent**: Assistant asks "Do you want me to proceed?".
5. **Invocation**: User says "yes" -> `[INVOKE:phinance]` detected -> `_invoke_phinance()` called.
6. **Hybrid Pass**: Python numbers + LLM insights -> NemoAgent Critic check.
7. **Pre-gen**: Outputs (Dashboard JSON, PDF command) generated async while user reads.

---

## 6. Storage & Database Schema (`finance.db`)
- **`documents`**: Metadata for every uploaded file.
- **`batches`**: Links multiple documents to a session and tracks pipeline status.
- **`transactions`**: Extracted line items with source `doc_id` and `merchant_stable_id`.
- **`chat_history`**: Persistent session-based conversation logs.
- **`merchant_mappings`**: Cached LLM categorizations for unknown merchants.

---

## 7. Security & Guardrails
- **Rate Limiting**: 10/min for uploads, 100/min for general API.
- **Input Validation**: 10MB file limit, 10k character message limit.
- **PII Redaction**: Performed during PDF parsing before text reaches LLM.
- **Tailscale**: Access restricted to `100.64.0.0/10` range in WebUI.

---

## 8. Current Status & Roadmap (M1)
**Next Priority**: **M1 Modular Orchestrator Implementation**
- Decouple specialists from `agent.py` using a registry and generic router.
- Implement dynamic prompt injection via `{{SPECIALIST_INSTRUCTIONS}}` placeholders.
- Remove hardcoded finance paths to support future Budgeting and Knowledge agents.

---
*Generated by Analysis Agent - Feb 19, 2026*
