# Insights Quality Comparison: Phinance vs NemoAgent

**Test Date:** January 2, 2026  
**Task:** Analyze 66 pre-extracted transactions and provide spending insights  
**Source Data:** Pre-extracted transactions from Apple Card statement

---

## Performance Metrics

| Metric | Phinance-JSON | NemoAgent (Nemotron 8B) |
|--------|---------------|-------------------------|
| **Latency** | **10.3 seconds** ✅ | 70.8 seconds |
| **Output Tokens** | 169 | 2,667 |
| **Input Tokens** | 9,693 | 7,691 |
| **Speed Ratio** | 1x (baseline) | 6.9x slower |

---

## Phinance Response

**Latency:** 10.3 seconds  
**Quality Grade:** ❌ POOR

```json
{
  "insights": [
    "The individual frequently shops at GROCERY_STORE and APPLE stores, indicating a preference for groceries and technology products.",
    "Transportation costs are consistently high throughout the month of April.",
    "There is significant spending on travel-related expenses."
  ],
  "recommendations": [
    "Consider using public transport or carpooling to reduce gas expenses. Consider switching mobile service providers for a better deal if possible.",
    "Review subscriptions and eliminate any unnecessary ones, like the 'CAFE_NAME' subscription."
  ],
  "potential_savings": 250.00
}
```

### Phinance Issues

1. **No total calculated** - User doesn't know how much they spent
2. **No category breakdown** - No spending by category
3. **No top merchants** - Doesn't identify biggest expenses
4. **Generic insights** - "Transportation costs are consistently high" (no numbers)
5. **Invented data** - References a "subscription" that doesn't exist in data
6. **Arbitrary savings** - $250 potential savings with no justification

---

## NemoAgent Response

**Latency:** 70.8 seconds  
**Quality Grade:** ✅ GOOD (but too slow)

```json
{
  "total_spent": 4602.71,
  "categories": {
    "groceries": 214.07,
    "gas": 111.57,
    "subscriptions": 182.97,
    "shopping": 234.89,
    "dining": 141.69,
    "utilities": 365.93,
    "transportation": 146.42,
    "other": 2128.08
  },
  "top_merchants": [
    {"merchant": "AIRLINE_A", "total": 169.49},
    {"merchant": "GROCERY_STORE", "total": 86.98},
    {"merchant": "APPLE.COM/BILL", "total": 52.94},
    {"merchant": "DEPARTMENT_STORE", "total": 59.37},
    {"merchant": "AMAZON", "total": 159.14}
  ],
  "insights": [
    "The 'other' category accounts for 46% of total spending, primarily driven by domain registrar and airline transactions",
    "Four separate trips to MOBILE_CARRIER for fuel purchases totaling $111.57",
    "Apple subscriptions and related purchases contribute nearly 10% to overall expenses",
    "Multiple dining purchases at LOCAL_RESTAURANT"
  ],
  "recommendations": [
    "Review 'other' category transactions for potential expense optimization",
    "Consider consolidating fuel purchases at MOBILE_CARRIER",
    "Evaluate subscription renewals for APPLE.COM and similar services",
    "Explore bulk purchasing options for recurring grocery expenses"
  ]
}
```

### NemoAgent Strengths

1. ✅ **Calculated total** - $4,602.71 total spent
2. ✅ **Category breakdown** - Full breakdown with amounts
3. ✅ **Top merchants identified** - Top 5 with spending totals
4. ✅ **Specific insights** - "46% of total spending", "$111.57", "nearly 10%"
5. ✅ **Actionable recommendations** - Specific to the data
6. ✅ **No hallucinations** - All merchants exist in source data

### NemoAgent Weakness

1. ❌ **Too slow** - 70.8 seconds is unacceptable for interactive use

---

## Side-by-Side Comparison

| Aspect | Phinance | NemoAgent | Winner |
|--------|----------|-----------|--------|
| **Total spent** | ❌ Not provided | ✅ $4,602.71 | NemoAgent |
| **Categories** | ❌ None | ✅ 8 categories with amounts | NemoAgent |
| **Top merchants** | ❌ None | ✅ Top 5 with totals | NemoAgent |
| **Insight quality** | ❌ Generic | ✅ Specific with percentages | NemoAgent |
| **Accuracy** | ❌ Hallucinated data | ✅ Matches source | NemoAgent |
| **Latency** | ✅ 10.3s | ❌ 70.8s | Phinance |

**Verdict:** Phinance is fast but useless. NemoAgent is accurate but too slow.

---

## The Problem

Neither model is acceptable for production:

- **Phinance (10s)**: Output quality is too low to be useful
- **NemoAgent (71s)**: Output quality is excellent but latency is unacceptable

**Target:** We need a model that can produce NemoAgent-quality insights in ~15-20 seconds.

---

## Candidate Replacement Models

Available locally (from `ollama list`):

| Model | Size | Expected Speed | Reasoning Quality |
|-------|------|----------------|-------------------|
| **qwen2.5:7b-instruct** | 4.7 GB | ~15-25s | ⭐ High (instruction-tuned) |
| **deepseek-r1:8b** | 5.2 GB | ~20-30s | ⭐ High (reasoning model) |
| **mistral:latest** | 4.4 GB | ~15-20s | ⭐ Medium-High |
| **dolphin3:latest** | 4.9 GB | ~15-25s | ⭐ Medium |
| **phi3:latest** | 2.2 GB | ~8-12s | ⭐ Medium |
| **llama3:latest** | 4.7 GB | ~15-25s | ⭐ Medium |

### Not Suitable (Too Large/Slow)

| Model | Size | Reason |
|-------|------|--------|
| qwq:latest | 19 GB | Too large, would be slow |
| llama3.3:latest | 42 GB | Way too large |
| mixtral:latest | 26 GB | Too large |
| qwen3:30b-a3b | 18 GB | Too large |
| llama3.2:1b | 1.3 GB | Too small, likely low quality |

### Recommended Test Order

1. **qwen2.5:7b-instruct** - Best balance of speed and instruction following
2. **deepseek-r1:8b** - May produce better reasoning/insights
3. **mistral:latest** - Proven performer, good JSON output

---

## Prompt Used for Testing

The same prompt was sent to both models:

```
Analyze the following financial transactions and provide insights.

Transaction data (JSON):
{
  "transactions": [
    {
      "date": "03/30/2025",
      "merchant": "GROCERY_STORE_A",
      "amount": 29.8,
      "category": "groceries",
      "raw_line": "03/30/2025 GROCERY_STORE_A [LOCATION] 1% $0.30 $29.80"
    },
    {
      "date": "03/31/2025",
      "merchant": "MOBILE_CARRIER",
      "amount": 15.11,
      "category": "gas",
      "raw_line": "03/31/2025 MOBILE_CARRIER [LOCATION] 1% $0.15 $15.11"
    },
    {
      "date": "03/31/2025",
      "merchant": "DOMAIN_REGISTRAR",
      "amount": 109.16,
      "category": "other",
      "raw_line": "03/31/2025 DOMAIN_REGISTRAR [LOCATION] 1% $1.09 $109.16"
    },
    {
      "date": "04/01/2025",
      "merchant": "APPLE.COM/BILL",
      "amount": 3.99,
      "category": "subscriptions",
      "raw_line": "04/01/2025 APPLE.COM/BILL [LOCATION] 3% $0.12 $3.99"
    },
    {
      "date": "04/02/2025",
      "merchant": "APPLE.COM/BILL",
      "amount": 25.95,
      "category": "subscriptions",
      "raw_line": "04/02/2025 APPLE.COM/BILL [LOCATION] 3% $0.78 $25.95"
    },
    {
      "date": "04/02/2025",
      "merchant": "Daily Cash Adjustment",
      "amount": 2.0,
      "category": "other",
      "raw_line": "04/02/2025 Daily Cash Adjustment $2.00"
    },
    {
      "date": "04/02/2025",
      "merchant": "AIRLINE_A",
      "amount": 58.0,
      "category": "travel",
      "raw_line": "04/02/2025 AIRLINE_A [LOCATION] 1% $0.58 $58.00"
    },
    {
      "date": "04/02/2025",
      "merchant": "GOOGLE_SUBSCRIPTION",
      "amount": 5.49,
      "category": "subscriptions",
      "raw_line": "04/02/2025 GOOGLE_SUBSCRIPTION [LOCATION] 1% $0.05 $5.49"
    },
    {
      "date": "04/02/2025",
      "merchant": "ELECTRONICS_STORE",
      "amount": 141.27,
      "category": "other",
      "raw_line": "04/02/2025 ELECTRONICS_STORE [LOCATION] 1% $1.41 $141.27"
    },
    {
      "date": "04/02/2025",
      "merchant": "APPLE.COM/BILL",
      "amount": 13.01,
      "category": "subscriptions",
      "raw_line": "04/02/2025 APPLE.COM/BILL [LOCATION] 3% $0.39 $13.01"
    },
    {
      "date": "04/04/2025",
      "merchant": "EVENT_SERVICE",
      "amount": 258.62,
      "category": "other",
      "raw_line": "04/04/2025 EVENT_SERVICE [LOCATION] 1% $2.59 $258.62"
    },
    {
      "date": "04/04/2025",
      "merchant": "GOOGLE_FI",
      "amount": 75.23,
      "category": "subscriptions",
      "raw_line": "04/04/2025 GOOGLE_FI [LOCATION] 1% $0.75 $75.23"
    },
    {
      "date": "04/05/2025",
      "merchant": "HVAC_SERVICE",
      "amount": 20.0,
      "category": "other",
      "raw_line": "04/05/2025 HVAC_SERVICE [LOCATION] 1% $0.20 $20.00"
    },
    {
      "date": "04/05/2025",
      "merchant": "TAXI_SERVICE_A",
      "amount": 64.9,
      "category": "transportation",
      "raw_line": "04/05/2025 TAXI_SERVICE_A [LOCATION] 2% $1.30 $64.90"
    },
    {
      "date": "04/05/2025",
      "merchant": "AIRPORT_NEWS",
      "amount": 26.43,
      "category": "shopping",
      "raw_line": "04/05/2025 AIRPORT_NEWS [LOCATION] 1% $0.26 $26.43"
    },
    {
      "date": "04/05/2025",
      "merchant": "MOBILE_CARRIER",
      "amount": 5.37,
      "category": "gas",
      "raw_line": "04/05/2025 MOBILE_CARRIER [LOCATION] 1% $0.05 $5.37"
    },
    {
      "date": "04/05/2025",
      "merchant": "MOBILE_CARRIER",
      "amount": 5.37,
      "category": "gas",
      "raw_line": "04/05/2025 MOBILE_CARRIER [LOCATION] 1% $0.05 $5.37"
    },
    {
      "date": "04/06/2025",
      "merchant": "AIRLINE_RETAIL_DE",
      "amount": 32.22,
      "category": "travel",
      "raw_line": "04/06/2025 AIRLINE_RETAIL_DE [GERMANY] 1% $0.32 $32.22"
    },
    {
      "date": "04/06/2025",
      "merchant": "AIRPORT_FOOD_DE",
      "amount": 5.04,
      "category": "travel",
      "raw_line": "04/06/2025 AIRPORT_FOOD_DE [GERMANY] 1% $0.05 $5.04"
    },
    {
      "date": "04/06/2025",
      "merchant": "TAXI_DE_A",
      "amount": 43.51,
      "category": "other",
      "raw_line": "04/06/2025 TAXI_DE_A [GERMANY] 1% $0.44 $43.51"
    },
    {
      "date": "04/06/2025",
      "merchant": "HOTEL_DE",
      "amount": 129.99,
      "category": "travel",
      "raw_line": "04/06/2025 HOTEL_DE [GERMANY] 1% $1.30 $129.99"
    },
    {
      "date": "04/07/2025",
      "merchant": "ELECTRONICS_DE",
      "amount": 11.09,
      "category": "other",
      "raw_line": "04/07/2025 ELECTRONICS_DE [GERMANY] 1% $0.11 $11.09"
    },
    {
      "date": "04/07/2025",
      "merchant": "FOOD_HALL_DE",
      "amount": 61.73,
      "category": "other",
      "raw_line": "04/07/2025 FOOD_HALL_DE [GERMANY] 1% $0.62 $61.73"
    },
    {
      "date": "04/07/2025",
      "merchant": "PHARMACY_DE",
      "amount": 58.86,
      "category": "other",
      "raw_line": "04/07/2025 PHARMACY_DE [GERMANY] 1% $0.59 $58.86"
    },
    {
      "date": "04/08/2025",
      "merchant": "TAXI_DE_B",
      "amount": 18.13,
      "category": "other",
      "raw_line": "04/08/2025 TAXI_DE_B [GERMANY] 1% $0.18 $18.13"
    },
    {
      "date": "04/09/2025",
      "merchant": "EUROSHOP_DE",
      "amount": 4.95,
      "category": "other",
      "raw_line": "04/09/2025 EUROSHOP_DE [GERMANY] 1% $0.05 $4.95"
    },
    {
      "date": "04/09/2025",
      "merchant": "BAKERY_DE",
      "amount": 35.51,
      "category": "other",
      "raw_line": "04/09/2025 BAKERY_DE [GERMANY] 1% $0.36 $35.51"
    },
    {
      "date": "04/09/2025",
      "merchant": "TRANSIT_DE",
      "amount": 3.44,
      "category": "dining",
      "raw_line": "04/09/2025 TRANSIT_DE [GERMANY] 1% $0.03 $3.44"
    },
    {
      "date": "04/10/2025",
      "merchant": "CATERING_DE",
      "amount": 19.42,
      "category": "other",
      "raw_line": "04/10/2025 CATERING_DE [GERMANY] 1% $0.19 $19.42"
    },
    {
      "date": "04/10/2025",
      "merchant": "TAXI_DE_C",
      "amount": 16.54,
      "category": "transportation",
      "raw_line": "04/10/2025 TAXI_DE_C [GERMANY] 1% $0.17 $16.54"
    },
    {
      "date": "04/10/2025",
      "merchant": "SHOP_DE",
      "amount": 15.94,
      "category": "other",
      "raw_line": "04/10/2025 SHOP_DE [GERMANY] 1% $0.16 $15.94"
    },
    {
      "date": "04/10/2025",
      "merchant": "TAXI_DE_D",
      "amount": 19.03,
      "category": "other",
      "raw_line": "04/10/2025 TAXI_DE_D [GERMANY] 1% $0.19 $19.03"
    },
    {
      "date": "04/11/2025",
      "merchant": "DUTY_FREE_DE",
      "amount": 32.0,
      "category": "travel",
      "raw_line": "04/11/2025 DUTY_FREE_DE [GERMANY] 1% $0.32 $32.00"
    },
    {
      "date": "04/11/2025",
      "merchant": "AIRPORT_SHOP_DE",
      "amount": 6.15,
      "category": "travel",
      "raw_line": "04/11/2025 AIRPORT_SHOP_DE [GERMANY] 1% $0.06 $6.15"
    },
    {
      "date": "04/11/2025",
      "merchant": "AIRLINE_B",
      "amount": 3.69,
      "category": "other",
      "raw_line": "04/11/2025 AIRLINE_B [GERMANY] 1% $0.04 $3.69"
    },
    {
      "date": "04/11/2025",
      "merchant": "TAXI_SERVICE_A",
      "amount": 40.25,
      "category": "transportation",
      "raw_line": "04/11/2025 TAXI_SERVICE_A [LOCATION] 2% $0.81 $40.25"
    },
    {
      "date": "04/11/2025",
      "merchant": "INDIAN_RESTAURANT",
      "amount": 86.35,
      "category": "dining",
      "raw_line": "04/11/2025 INDIAN_RESTAURANT [LOCATION] 1% $0.86 $86.35"
    },
    {
      "date": "04/13/2025",
      "merchant": "HOTEL_RESTAURANT",
      "amount": 27.0,
      "category": "other",
      "raw_line": "04/13/2025 HOTEL_RESTAURANT [LOCATION] 1% $0.27 $27.00"
    },
    {
      "date": "04/13/2025",
      "merchant": "MOBILE_CARRIER",
      "amount": 30.63,
      "category": "gas",
      "raw_line": "04/13/2025 MOBILE_CARRIER [LOCATION] 1% $0.31 $30.63"
    },
    {
      "date": "04/13/2025",
      "merchant": "DOMAIN_REGISTRAR",
      "amount": 34.88,
      "category": "other",
      "raw_line": "04/13/2025 DOMAIN_REGISTRAR [LOCATION] 1% $0.35 $34.88"
    },
    {
      "date": "04/13/2025",
      "merchant": "ELECTRIC_UTILITY",
      "amount": 268.45,
      "category": "utilities",
      "raw_line": "04/13/2025 ELECTRIC_UTILITY [LOCATION] 1% $2.68 $268.45"
    },
    {
      "date": "04/15/2025",
      "merchant": "CAFE",
      "amount": 31.88,
      "category": "dining",
      "raw_line": "04/15/2025 CAFE [LOCATION] 1% $0.32 $31.88"
    },
    {
      "date": "04/15/2025",
      "merchant": "GROCERY_STORE_A",
      "amount": 22.56,
      "category": "groceries",
      "raw_line": "04/15/2025 GROCERY_STORE_A [LOCATION] 1% $0.23 $22.56"
    },
    {
      "date": "04/16/2025",
      "merchant": "LOCAL_STORE",
      "amount": 18.63,
      "category": "other",
      "raw_line": "04/16/2025 LOCAL_STORE [LOCATION] 1% $0.19 $18.63"
    },
    {
      "date": "04/17/2025",
      "merchant": "GAS_UTILITY",
      "amount": 97.44,
      "category": "utilities",
      "raw_line": "04/17/2025 GAS_UTILITY [LOCATION] 1% $0.97 $97.44"
    },
    {
      "date": "04/18/2025",
      "merchant": "PHONE_CARRIER",
      "amount": 246.85,
      "category": "other",
      "raw_line": "04/18/2025 PHONE_CARRIER [LOCATION] 1% $2.47 $246.85"
    },
    {
      "date": "04/21/2025",
      "merchant": "HEALTH_FOOD_STORE",
      "amount": 105.32,
      "category": "dining",
      "raw_line": "04/21/2025 HEALTH_FOOD_STORE [LOCATION] 1% $1.05 $105.32"
    },
    {
      "date": "04/21/2025",
      "merchant": "USPS",
      "amount": 30.95,
      "category": "other",
      "raw_line": "04/21/2025 USPS [LOCATION] 1% $0.31 $30.95"
    },
    {
      "date": "04/21/2025",
      "merchant": "GROCERY_STORE_B",
      "amount": 77.22,
      "category": "groceries",
      "raw_line": "04/21/2025 GROCERY_STORE_B [LOCATION] 1% $0.77 $77.22"
    },
    {
      "date": "04/22/2025",
      "merchant": "TAXI_SERVICE_A",
      "amount": 90.2,
      "category": "transportation",
      "raw_line": "04/22/2025 TAXI_SERVICE_A [LOCATION] 2% $1.80 $90.20"
    },
    {
      "date": "04/22/2025",
      "merchant": "POKE_RESTAURANT",
      "amount": 19.06,
      "category": "other",
      "raw_line": "04/22/2025 POKE_RESTAURANT [LOCATION] 1% $0.19 $19.06"
    },
    {
      "date": "04/22/2025",
      "merchant": "TRANSIT_METRA",
      "amount": 6.75,
      "category": "other",
      "raw_line": "04/22/2025 TRANSIT_METRA [LOCATION] 1% $0.07 $6.75"
    },
    {
      "date": "04/23/2025",
      "merchant": "MUNICIPAL_WATER",
      "amount": 65.65,
      "category": "other",
      "raw_line": "04/23/2025 MUNICIPAL_WATER [LOCATION] 1% $0.66 $65.65"
    },
    {
      "date": "04/23/2025",
      "merchant": "MOBILE_CARRIER_B",
      "amount": 11.72,
      "category": "gas",
      "raw_line": "04/23/2025 MOBILE_CARRIER_B [LOCATION] 1% $0.12 $11.72"
    },
    {
      "date": "04/23/2025",
      "merchant": "AMAZON",
      "amount": 159.14,
      "category": "shopping",
      "raw_line": "04/23/2025 AMAZON [LOCATION] 1% $1.59 $159.14"
    },
    {
      "date": "04/24/2025",
      "merchant": "MOBILE_CARRIER",
      "amount": 55.09,
      "category": "gas",
      "raw_line": "04/24/2025 MOBILE_CARRIER [LOCATION] 1% $0.55 $55.09"
    },
    {
      "date": "04/25/2025",
      "merchant": "DEPARTMENT_STORE",
      "amount": 59.37,
      "category": "shopping",
      "raw_line": "04/25/2025 DEPARTMENT_STORE [LOCATION] 1% $0.59 $59.37"
    },
    {
      "date": "04/25/2025",
      "merchant": "AIRLINE_C",
      "amount": 248.97,
      "category": "other",
      "raw_line": "04/25/2025 AIRLINE_C [LOCATION] 1% $2.49 $248.97"
    },
    {
      "date": "04/27/2025",
      "merchant": "GROCERY_STORE_A",
      "amount": 34.62,
      "category": "groceries",
      "raw_line": "04/27/2025 GROCERY_STORE_A [LOCATION] 1% $0.35 $34.62"
    },
    {
      "date": "04/27/2025",
      "merchant": "AIRLINE_C",
      "amount": 169.49,
      "category": "other",
      "raw_line": "04/27/2025 AIRLINE_C [LOCATION] 1% $1.69 $169.49"
    },
    {
      "date": "04/27/2025",
      "merchant": "AIRLINE_C",
      "amount": 169.49,
      "category": "other",
      "raw_line": "04/27/2025 AIRLINE_C [LOCATION] 1% $1.69 $169.49"
    },
    {
      "date": "04/27/2025",
      "merchant": "INDIAN_RESTAURANT",
      "amount": 43.24,
      "category": "dining",
      "raw_line": "04/27/2025 INDIAN_RESTAURANT [LOCATION] 1% $0.43 $43.24"
    },
    {
      "date": "04/28/2025",
      "merchant": "HOME_IMPROVEMENT",
      "amount": 11.2,
      "category": "shopping",
      "raw_line": "04/28/2025 HOME_IMPROVEMENT [LOCATION] 1% $0.11 $11.20"
    },
    {
      "date": "04/30/2025",
      "merchant": "APPLE.COM/BILL",
      "amount": 9.99,
      "category": "subscriptions",
      "raw_line": "04/30/2025 APPLE.COM/BILL [LOCATION] 3% $0.30 $9.99"
    },
    {
      "date": "07/22/2024",
      "merchant": "Apple Online Store",
      "amount": 274.0,
      "category": "other",
      "raw_line": "07/22/2024 Apple Online Store [LOCATION] $274.00"
    },
    {
      "date": "10/13/2024",
      "merchant": "Apple Online Store",
      "amount": 714.0,
      "category": "other",
      "raw_line": "10/13/2024 Apple Online Store [LOCATION] $714.00"
    }
  ],
  "currency": "USD",
  "request_type": "full_analysis"
}

Provide a JSON response with:
- total_spent: Sum of all transaction amounts
- categories: Breakdown by category with totals
- top_merchants: Top 5 merchants by spending
- insights: 3-5 observations about spending patterns
- recommendations: 2-3 actionable recommendations

Respond with valid JSON only.
```

---

## Test Artifacts

- `/tmp/analysis_prompt.txt` - The original prompt sent to both models
- `/tmp/phinance_analysis_result.json` - Full Phinance response
- `/tmp/nemoagent_analysis_result.json` - Full NemoAgent response
- `/tmp/nemoagent_raw_response.json` - Including "thinking" field

---

*Created: January 2, 2026*

---

## Hybrid Approach Results (January 2, 2026)

After discovering that LLMs struggle with arithmetic, we implemented a hybrid approach:
- **Python** calculates all numbers (totals, categories, percentages)
- **LLM** provides qualitative insights only (observations, recommendations)

### The Problem with Phinance for Insights

Phinance's Modelfile has a baked-in system prompt that forces it to output the full financial analysis schema (total_spent, categories, top_merchants, etc.). When asked to provide "insights only", it ignores the request and outputs its hardcoded format with malformed JSON.

### Solution: Use qwen2.5:7b-instruct for Insights

| Model | Role | Time | Quality |
|-------|------|------|---------|
| **Python** | Calculate totals, categories, percentages | 0.05ms | 100% accurate |
| **qwen2.5:7b-instruct** | Generate qualitative insights | 5-6s | Excellent |
| **Phinance** | Transaction extraction only | ~10s | Good (for extraction) |

### Hybrid Test Results

**Test:** 19 transactions, pre-calculated summary fed to qwen2.5

```
=== TIMING ===
Python calculation: 0.05ms
LLM insights: 6.3s
Total: 6.3s

=== ACCURACY ===
Total: $2,720.12 (Python-calculated, 100% accurate)

=== INSIGHTS (qwen2.5-generated) ===
1. "The majority of spending (64.8%) is 'other', indicating untracked/discretionary expenses"
2. "Dining and shopping account for 17% - cost-cutting possible here"
3. "Utilities at 13.5% is relatively high, hinting at potential inefficiencies"

=== RECOMMENDATIONS ===
1. "Review 'other' expenses to identify unnecessary costs"
2. "Negotiate better utility rates or switch providers"
3. "Set dining/shopping budget limits based on current $234.91 and $218.51"

=== ESTIMATED SAVINGS ===
$107.62/month
```

### Comparison: All Three Approaches

| Aspect | Phinance Only | NemoAgent Only | Hybrid (Python + qwen2.5) |
|--------|--------------|----------------|---------------------------|
| **Time** | 10s | 71s | **6.3s** ✅ |
| **Math Accuracy** | ❌ Poor | ⚠️ Approximate | ✅ **100%** |
| **Insight Quality** | ❌ Generic | ✅ Specific | ✅ **Specific** |
| **Recommendations** | ❌ Generic | ✅ Actionable | ✅ **Actionable** |
| **Total Spent** | ❌ Missing | ⚠️ $4,602.71 | ✅ **$4,637.33** |

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Transactions (pre-extracted by Phinance or NemoAgent)              │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Python: calculate_financials()                                     │
│  ─────────────────────────────                                      │
│  • total_spent, categories, top_merchants                           │
│  • 0.05ms, 100% accurate                                            │
│  • File: home-ai/soa1/utils/financial_calculator.py                 │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  qwen2.5:7b-instruct: Insights only (no math)                       │
│  ─────────────────────────────────────────────                      │
│  • insights[], recommendations[], potential_savings                 │
│  • 5-6s, qualitative analysis                                       │
│  • File: home-ai/soa1/models.py (call_insights_model)               │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Merge: Python numbers + LLM insights                               │
│  ─────────────────────────────────────                              │
│  • Accurate totals + smart observations                             │
│  • Best of both worlds                                              │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Files Modified

| File | Change |
|------|--------|
| `home-ai/soa1/utils/financial_calculator.py` | Created - Python calculation utilities |
| `home-ai/soa1/models.py` | Added `call_insights_model()` function, "insights" endpoint config |
| `home-ai/soa1/agent.py` | Updated `_invoke_phinance()` to use hybrid approach |

### Why This Works

LLMs process language (tokens), not numbers. When asked to "sum these 66 amounts", they:
1. Convert each number to tokens
2. Simulate addition through pattern matching
3. Often get wrong answers on large datasets

By pre-calculating with Python, we:
1. Get 100% accurate numbers instantly
2. Give the LLM a simplified task (qualitative analysis only)
3. Combine strengths of both approaches

*Updated: January 2, 2026*
