# Gap Analysis: Phinance vs Nemotron for Finance Analysis

**Test Date:** January 2, 2026  
**Test PDF:** Apple Card Statement - April 2025.pdf  
**Prompt:** Standard Apple Card extraction prompt (17,176 chars / ~4,294 tokens)

---

## Executive Summary

| Metric | Phinance-JSON | NemoAgent (Nemotron) |
|--------|--------------|---------------------|
| **Model Size** | 2.2 GB | 8.7 GB |
| **Transactions Extracted** | 8 | 64 |
| **Latency** | 15-17 seconds | 152 seconds |
| **Output Tokens** | ~800 | ~5,800 |
| **Total Spent Calculated** | $645.24 (partial) | $3,649.33 (complete) |
| **Schema Compliance** | ✓ Complete | ✓ Complete |

**Key Finding:** Phinance extracts only ~12.5% of transactions despite having capacity for more.

---

## Detailed Gaps

### 1. CRITICAL: Transaction Extraction Gap

**Gap:** Phinance missed 56 out of 64 transactions (87.5% miss rate)

**Evidence:**
- Phinance: 8 transactions extracted
- Nemotron: 64 transactions extracted
- Even with `num_predict=8192`, Phinance still only returned 8 transactions

**Root Cause Analysis:**
- NOT a token limit issue (Phinance used only 802 tokens with 8192 limit)
- Appears to be model behavior - Phinance stops after extracting a subset
- Possibly trained to provide "representative sample" rather than exhaustive list

**Impact:**
- Financial totals are severely underestimated
- Phinance reported $645.24 spent (from 8 tx) vs actual $3,649.33 (from 64 tx)
- Category breakdowns are incomplete

---

### 2. WARNING: Sign Convention Difference

**Gap:** Different models use opposite sign conventions for amounts

**Evidence:**
- Phinance: Uses **negative** amounts for purchases (e.g., `-246.85`)
- Nemotron: Uses **positive** amounts for purchases (e.g., `29.80`)

**Impact:**
- Downstream processing must handle both conventions
- Sum calculations need sign normalization
- Cannot directly compare totals without conversion

---

### 3. INFO: Performance Gap

**Gap:** Nemotron is 10x slower than Phinance

**Evidence:**
- Phinance: 15-17 seconds
- Nemotron: 152 seconds (with complete extraction)

**Impact:**
- For single PDF: Acceptable delay for accuracy
- For batch of 10 PDFs: 25 minutes vs 2.5 minutes
- Real-time use cases: Phinance only viable option

---

### 4. Insight Quality Comparison

**Phinance Insights:**
> - "The majority of spending is on groceries & dining."
> - "There are frequent payments made to restaurants and food markets."

**Nemotron Insights:**
> - "Shopping expenditures account for nearly 35% of total spending, with frequent purchases at APPLE.COM, NAME-CHEAP.COM, and NORDSTROM"
> - "Utilities costs have remained relatively stable, with payments to BOOST MOBILE and NICOR GAS appearing regularly"  
> - "Travel expenses are modest but consistent, primarily involving Lufthansa, METRA, and local taxi services"

**Assessment:** Nemotron provides more specific, actionable insights with merchant names and percentages.

---

## Category Comparison

| Category | Phinance | Nemotron |
|----------|----------|----------|
| Groceries | -$1,083.19 | $86.98 |
| Dining | (combined above) | $50.94 |
| Shopping | - | $1,325.78 |
| Services | -$265.19 | $761.32 |
| Transportation | -$197.44 | - |
| Travel | - | $701.16 |
| Utilities | -$197.44 | $512.62 |
| Other | $0 | $210.53 |

**Note:** Phinance uses different category names and negative values.

---

## Recommendations

### Option A: Fix Phinance (Preferred for Speed)

1. **Investigate model fine-tuning** - Why does it stop at ~8 transactions?
2. **Modify prompt** to explicitly request "ALL transactions, do not stop early"
3. **Add iteration** - Call phinance multiple times for different date ranges

### Option B: Use Nemotron for Deep Analysis

1. Keep Phinance for quick summaries / real-time chat
2. Use Nemotron for batch processing where accuracy > speed
3. Post-process Nemotron output to calculate totals/categories

### Option C: Hybrid Approach

1. **Quick mode:** Phinance (15s) - for immediate feedback
2. **Deep mode:** Nemotron (150s) - for detailed analysis
3. Let user choose or auto-select based on context

### Option D: Increase Phinance num_predict in Production

Current: `num_predict: 768` in `models.py`  
Change to: `num_predict: 4096` or higher

**Note:** Testing showed this doesn't help - Phinance naturally stops at ~800 tokens regardless.

---

## Test Artifacts

- `/tmp/test_prompt.txt` - The prompt sent to both models
- `/tmp/phinance_result.json` - Phinance output (num_predict=4096)
- `/tmp/phinance_result_v2.json` - Phinance output (num_predict=8192)
- `/tmp/nemotron_result_v2.json` - Nemotron complete output (num_predict=8192)

---

## Conclusion

**Can Nemotron replace Phinance?**

| Use Case | Recommendation |
|----------|---------------|
| Real-time chat | ❌ Keep Phinance (10x faster) |
| Single PDF analysis | ⚠️ Nemotron (more accurate but slow) |
| Batch processing | ✓ Nemotron (accuracy matters more) |
| Quick summary | ✓ Phinance (speed matters more) |

**Primary Issue:** Phinance's transaction extraction is incomplete, not due to token limits but model behavior. This needs investigation into the model's training or prompt engineering.


---

## Update: Hybrid Approach Tested (Jan 2, 2026)

### Hybrid Results

| Approach | Transactions | Total Spent | Time |
|----------|-------------|-------------|------|
| Phinance Only | 8 | $645 | 15s |
| Nemotron Only | 64 | $3,649 | 152s |
| **Hybrid** | 63 | $3,647 | 165s |

### Hybrid Breakdown
- Nemotron extraction: 162s
- Model swap: 2s  
- Phinance insights: 3s

### Verdict
Hybrid approach provides **98% accuracy** with specialized models doing what they do best.

See: `RemAssist/HYBRID_EXTRACTION_ARCHITECTURE.md` for implementation plan.

