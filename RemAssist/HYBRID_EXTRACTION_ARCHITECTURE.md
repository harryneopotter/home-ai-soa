# Hybrid Calculation Architecture

## Overview

The finance pipeline uses a **hybrid approach** where Python handles all arithmetic and LLMs handle qualitative analysis only. This solves the fundamental problem that LLMs struggle with math on large datasets.

## The Problem

LLMs process language (tokens), not numbers. When asked to sum 66 transaction amounts:
1. They convert each number to tokens
2. Simulate addition through pattern matching
3. Often produce incorrect results on large datasets

**Test Results:**
- Phinance (10s): No total calculated, generic insights, hallucinated data
- NemoAgent (71s): Total $4,602.71 (close but not exact), good insights but too slow
- Python (0.05ms): Exact $4,637.33, 100% accurate

## The Solution

```
┌─────────────────────────────────────────────────────────────────────┐
│  PDF Upload                                                          │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 1: Transaction Extraction (Phinance/NemoAgent)               │
│  ─────────────────────────────────────────────────────              │
│  • Input: Raw PDF text                                              │
│  • Output: JSON array of transactions                               │
│  • Model: phinance-json:latest or NemoAgent:latest                  │
│  • Time: ~10-180s per PDF                                           │
│  • Runs in BACKGROUND after upload                                  │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 2: Python Calculation                                         │
│  ───────────────────────────────                                     │
│  • Input: Extracted transactions                                     │
│  • Output: Accurate totals, categories, top merchants                │
│  • Time: 0.05ms (instant!)                                           │
│  • 100% accurate                                                     │
│  • File: home-ai/soa1/utils/financial_calculator.py                  │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 3: Insights Generation (qwen2.5:7b-instruct)                  │
│  ──────────────────────────────────────────────────                  │
│  • Input: Pre-calculated summary (NOT raw transactions)              │
│  • Output: insights[], recommendations[], potential_savings          │
│  • Model: qwen2.5:7b-instruct                                        │
│  • Time: ~5-6s                                                       │
│  • Qualitative analysis only (no math required)                      │
│  • File: home-ai/soa1/models.py (call_insights_model)                │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 4: Merge Results                                              │
│  ─────────────────────────                                           │
│  • Python numbers (accurate) + LLM insights (qualitative)            │
│  • Best of both worlds                                               │
│  • File: home-ai/soa1/utils/financial_calculator.py                  │
└─────────────────────────────────────────────────────────────────────┘
```

## Implementation Files

### `home-ai/soa1/utils/financial_calculator.py`

Core calculation utilities:

```python
def calculate_financials(transactions: List[Dict]) -> Dict:
    """Calculate accurate totals, categories, top merchants."""
    # Returns: total_spent, transaction_count, categories, top_merchants, 
    #          date_range, avg_transaction

def build_insights_prompt(transactions, summary) -> str:
    """Build prompt for LLM with pre-calculated numbers."""
    # LLM only needs to analyze, not calculate

def merge_calculated_with_llm_response(calculated, llm_response) -> Dict:
    """Merge Python numbers with LLM qualitative insights."""
```

### `home-ai/soa1/models.py`

Added insights model endpoint:

```python
DEFAULT_MODELS = {
    "nemotron": {...},
    "phinance": {...},
    "insights": {
        "base_url": "http://localhost:11434",
        "model_name": "qwen2.5:7b-instruct",
        "temperature": 0.3,
        "max_tokens": 1024,
    },
}

def call_insights_model(prompt: str) -> str:
    """Call qwen2.5 for qualitative financial insights."""
```

### `home-ai/soa1/agent.py`

Updated `_invoke_phinance()` to use hybrid approach:

```python
def _invoke_phinance(self, document_context):
    # 1. Load transactions from storage
    all_transactions = ...
    
    # 2. Python calculates (0.05ms, 100% accurate)
    calculated = calculate_financials(all_transactions)
    
    # 3. Build insights prompt with pre-calculated data
    insights_prompt = build_insights_prompt(all_transactions, calculated)
    
    # 4. LLM provides qualitative analysis only
    raw_response = call_insights_model(insights_prompt)
    
    # 5. Merge results
    analysis = merge_calculated_with_llm_response(calculated, llm_insights)
```

## Model Responsibilities

| Model | Responsibility | Why |
|-------|---------------|-----|
| **Phinance** | Extract transactions from PDF text | Specialized for structured extraction |
| **Python** | Calculate totals, percentages, rankings | 100% accurate, instant |
| **qwen2.5** | Generate insights and recommendations | Good at qualitative analysis, clean JSON |

## Why NOT Use Phinance for Insights

Phinance has a **baked-in Modelfile system prompt** that forces it to output the full financial analysis schema. When asked to "only provide insights", it:
1. Ignores the request
2. Outputs its hardcoded format
3. Produces malformed JSON

Solution: Use a general-purpose model (qwen2.5) that follows prompts without override.

## Performance Comparison

| Approach | Time | Math Accuracy | Insight Quality |
|----------|------|---------------|-----------------|
| Phinance only | 10s | ❌ Missing/wrong | ❌ Generic |
| NemoAgent only | 71s | ⚠️ ~99% | ✅ Good |
| **Hybrid** | **6.3s** | ✅ **100%** | ✅ **Good** |

## VRAM Considerations

Models involved:
- `phinance-json:latest` (2.2 GB) - For extraction
- `qwen2.5:7b-instruct` (4.7 GB) - For insights
- Both can fit in VRAM simultaneously on RTX 5060 Ti (16 GB each)

No model swapping required for the insights phase.

## Test Results (January 2, 2026)

```
=== HYBRID CALCULATION TEST ===

Python calculation: 0.05ms
  Total: $2,720.12
  Categories: 8
  Transactions: 19

LLM insights (qwen2.5): 6.3s
  Insights: 3 items
  Recommendations: 3 items
  Potential savings: $107.62

Total time: 6.3s (vs 71s for NemoAgent alone)
```

---

*Created: January 2, 2026*
*Last Updated: January 2, 2026*
