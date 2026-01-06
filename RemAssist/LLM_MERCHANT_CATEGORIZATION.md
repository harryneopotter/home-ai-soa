# LLM-Assisted Merchant Categorization

_Created: January 5, 2026_

## Problem Statement

Currently, 65%+ of transactions fall into "Other" category because:
1. Python regex/keyword matching only covers major brands
2. Local merchants, abbreviations, and cryptic names aren't recognized
3. No learning mechanism for new merchants

## Solution: Phinance-Assisted Categorization

Use Phinance (fastest model per testing) to categorize unknown merchants after Python regex pass.

## Architecture

### Flow Diagram

```
Upload → Text Extraction Starts
              ↓
[First chunk extracted - finance doc detected]
              ↓
         ┌────────────────────────────────┐
         │ Background: Warm up Phinance   │
         │ (if not already loaded)        │
         └────────────────────────────────┘
              ↓
[All chunks extracted → transactions parsed]
              ↓
[Python regex categorization pass]
    ├── Known merchants → category assigned (instant, 0.95 confidence)
    └── Unknown merchants → collect unique raw names
              ↓
[Check merchant_mappings cache]
    ├── Cached → use stored category
    └── Not cached → add to LLM batch
              ↓
[Single Phinance call with unknown merchants]
              ↓
[Store results in merchant_mappings]
    ├── source = 'phinance'
    ├── flagged = true if category == 'other'
    └── confidence_score from Phinance
              ↓
[Merge categories back into transactions]
              ↓
[Ready for analysis with accurate category spend]
```

### Phinance Warming

On first finance document detection, send a system prompt to load Phinance:

```json
{
  "model": "phinance-json",
  "messages": [
    {
      "role": "system", 
      "content": "You are a financial transaction categorization specialist. Your role is to accurately categorize merchant transactions. You will receive a list of merchant names and must assign each one to exactly one category. Be ready for categorization tasks."
    },
    {
      "role": "user",
      "content": "Acknowledge readiness."
    }
  ]
}
```

This loads the model into VRAM (~1s on NVMe) while extraction continues.

### Categorization Prompt

```json
{
  "model": "phinance-json",
  "messages": [
    {
      "role": "system",
      "content": "You are a financial transaction categorization specialist. Categorize each merchant into exactly ONE category from this list: dining, groceries, gas, entertainment, shopping, travel, utilities, subscriptions, health, transfer, cash, other. Return valid JSON only."
    },
    {
      "role": "user",
      "content": "Categorize these merchants:\n\n1. WHATABRGR #1234 DALLAS TX\n2. JOE'S BBQ SHACK\n3. SQ *MAIN ST COFFEE\n4. POS DEBIT 7823\n\nReturn JSON format: {\"merchant_name\": \"category\", ...}"
    }
  ],
  "format": "json"
}
```

### Expected Response

```json
{
  "WHATABRGR #1234 DALLAS TX": "dining",
  "JOE'S BBQ SHACK": "dining", 
  "SQ *MAIN ST COFFEE": "dining",
  "POS DEBIT 7823": "other"
}
```

## Database Schema Changes

Extend existing `merchant_mappings` table:

```sql
ALTER TABLE merchant_mappings ADD COLUMN source TEXT DEFAULT 'regex';
-- Values: 'regex', 'phinance', 'user_confirmed', 'nemo'

ALTER TABLE merchant_mappings ADD COLUMN flagged INTEGER DEFAULT 0;
-- 1 = categorized as 'other', needs human review or escalation

ALTER TABLE merchant_mappings ADD COLUMN merchant_stable_id TEXT;
-- Link to stable ID from merchant_normalizer.py
```

## Implementation Steps

### Phase 1: Phinance Warming (Non-blocking)
- [ ] Add `warm_phinance()` function in `models.py`
- [ ] Call on first finance doc detection in `batch_processor.py`
- [ ] Fire-and-forget (don't await)

### Phase 2: Batch Categorization
- [ ] Add `categorize_merchants_llm(merchants: List[str]) -> Dict[str, str]` in `models.py`
- [ ] Integrate into extraction flow after Python pass
- [ ] Deduplicate merchants before sending (use `set()`)

### Phase 3: Caching
- [ ] Check `merchant_mappings` before LLM call
- [ ] Store new mappings with `source='phinance'`
- [ ] Flag `category='other'` results for review

### Phase 4: Flagged Review (Future)
- [ ] Escalate flagged merchants to NemoAgent or user
- [ ] Update `source` to `'user_confirmed'` or `'nemo'` after review
- [ ] Increment `times_confirmed` for learning

## Files to Modify

| File | Changes |
|------|---------|
| `home-ai/soa1/models.py` | Add `warm_phinance()`, `categorize_merchants_llm()` |
| `home-ai/soa1/batch_processor.py` | Integrate warming + categorization into flow |
| `home-ai/finance-agent/src/storage.py` | Add migration for new columns, update `upsert_merchant_mapping()` |
| `home-ai/soa1/utils/merchant_normalizer.py` | Add cache lookup before returning "other" |

## Performance Estimates

| Step | Time |
|------|------|
| Python regex pass | ~0.05ms |
| Phinance warming | ~1s (parallel with extraction) |
| Phinance categorization (50 merchants) | ~2-3s |
| DB cache lookup | ~1ms |
| **Total added latency** | ~2-3s (one-time per batch) |

## Success Metrics

- Reduce "Other" category from 65% to <15%
- Cache hit rate >80% after initial population
- No increase in user-facing latency (warming is parallel)

## Rollback Plan

If Phinance categorization degrades quality:
1. Set feature flag `USE_LLM_CATEGORIZATION = False`
2. Fall back to Python-only categorization
3. Keep cached mappings (don't delete)
