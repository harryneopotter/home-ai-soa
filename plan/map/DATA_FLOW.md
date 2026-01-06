# Data Flow to Chat Agent (Finance Pipeline)

**Version**: 1.0  
**Date**: January 4, 2026  
**Status**: Verified via Code Analysis  

---

## Overview

The "Chat Agent" in SOA1 consists of two distinct LLM interactions:
1.  **The Orchestrator (`NemoAgent`)**: Handles the conversation, intent detection, and consent. It receives **metadata and summary findings**, but NOT raw data.
2.  **The Specialist (`Phinance` / `Qwen2.5`)**: Handles deep analysis. It receives **raw transactions and calculated aggregates**.

---

## 1. Data Passed to Orchestrator (NemoAgent)

The Orchestrator receives a constructed prompt containing the following blocks. It **does not** see the full list of transactions.

### A. Document Context Block (`[DOCUMENT CONTEXT]`)
Generated in `agent.py` -> `_format_document_context` using `BatchState` from `batch_processor.py`.

| Field | Source | Example Value | Purpose |
| :--- |
| **Batch ID** | `BatchState.batch_id` | `batch-a1b2c3d4` | Tracking context. |
| **Status** | `BatchState.status` | `ready` | Context awareness (e.g., "I'm still reading..."). |
| **Tx Count** | `BatchState.transaction_count` | `42` | Scale awareness. |
| **Findings** | `BatchState.interesting_findings` | - "Total spending: $4,637.33"<br>- "Highest category: Dining ($847)"<br>- "Subscriptions: $120/mo" | **Engagement Hooks**. Gives the agent "something to say" before analysis is fully run. |
| **Files** | `document_context["documents"]` | List of files. | |
| - Filename | `doc["filename"]` | `Apple Card - Sept.pdf` | Identification. |
| - Pages | `doc["pages"]` | `3` | Scope awareness. |
| - Type | `doc["inferred_type"]` | `credit_card_statement` | Contextual understanding. |
| - Headers | `doc["header_lines"]` | `["Apple Card", "Statement Date..."]` | Verification (First 3 lines). |

### B. Memory Context
From `MemLayer` (vector search).
-   Relevant past facts/events matching the query.
-   *Example*: "- (2025-12-01) User mentioned they want to cut down on dining."

### C. Chat History
-   Last 20 messages (User/Assistant pairs) for conversational continuity.

---

## 2. Data Passed to Specialist (Phinance Pipeline)

When `[INVOKE:phinance]` is triggered, a different set of data is prepared for the analysis models.

### A. Python Calculation Layer (The "Truth")
Before calling any LLM, `utils/financial_calculator.py` computes:
-   **Total Spent**: Exact sum of all transactions (float).
-   **Categories**: Dict of `{category_name: amount}`.
-   **Top Merchants**: List of `{merchant: name, amount: X}`.
-   **Date Range**: Start and End dates.

### B. Data passed to Insights Model (`qwen2.5:7b-instruct`)
The `insights_prompt` includes:
-   **Calculated Aggregates**: The exact numbers from Python (to prevent math hallucinations).
-   **Hidden Drains**: List of detected recurring charges (Netflix, Spotify, etc.).
-   **Raw Transactions** (Optional/Partial): Depending on token limits, relevant transaction subsets may be included for pattern matching.

---

## 3. Data Structures

### `BatchState` (in `batch_processor.py`)
The central object holding data passed to the agent.
```python
@dataclass
class BatchState:
    batch_id: str
    status: str  # uploading -> parsing -> ready -> analyzing -> complete
    
    # Metadata for Orchestrator
    files: List[Dict]          # filenames, page counts, headers
    interesting_findings: List[str] # Pre-calculated hooks
    
    # Raw Data for Specialist (NOT passed to Orchestrator)
    extracted_transactions: List[Dict] # Full transaction list
    calculated_summary: Dict   # Python-computed totals/stats
    phinance_analysis: Dict    # Final LLM output (after analysis)
```

### `document_context` Dictionary
The actual object passed to `agent.ask()`.
```python
{
    "batch_id": "batch-...",
    "session_id": "...",
    "documents": [
        {
            "filename": "statement.pdf",
            "pages": 5,
            "inferred_type": "bank_statement",
            "preview_text": "Bank of America\nAccount Statement..."
        }
    ]
}
```

---

## Summary of Boundaries

1.  **Orchestrator** sees **Metadata + Summary Stats**. It knows *about* the data (file types, totals, key findings) but doesn't see the *rows*.
2.  **Specialist** sees **Aggregates + Patterns**. It relies on Python for the math.
3.  **Frontend** sees **JSON Reports**. The final dashboard JSON is pre-generated and served statically/via API, bypassing the LLM for display.

---

## Update: January 6, 2026

### Current Data Flow Integrity Issue
- **Persistence Failure**: While the specialist generates the `phinance_analysis` JSON, it is currently failing to persist to the `batches` table in the SQLite database. Data flow is interrupted between Specialist completion and Frontend retrieval.
