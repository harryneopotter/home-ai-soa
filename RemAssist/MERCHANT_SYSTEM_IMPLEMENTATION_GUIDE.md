# Merchant System Implementation Guide

_Created: January 5, 2026 (Session 33)_
_Updated: January 5, 2026 (Session 34) - Added feedback review, prompt fix, NemoAgent critic_
_Consolidates: Transaction Duplication Fix + LLM Categorization + Chat Correction_

## Overview

This guide covers three interconnected improvements to the merchant/transaction system:

1. **Transaction Duplication Bug Fix** - CRITICAL, blocks everything else
2. **LLM-Assisted Categorization** - Reduce "Other" from 65% to <15%
3. **Chat-Based Correction** - User fixes categories via natural language

**Dependency Order**: Fix #1 → Implement #2 → Implement #3

---

## ⚠️ Feedback Review (Session 34)

_Source: `RemAssist/merchant_plan_feedback.md`, `RemAssist/merchant_plan_feedback2.md`_

### Already Addressed (Session 32)

| Item | Status |
|------|--------|
| `merchant_stable_id` computation | ✅ `compute_merchant_stable_id()` in merchant_normalizer.py |
| Store `merchant_raw`, `merchant`, `merchant_stable_id` in transactions | ✅ `normalize_transactions()` adds all three |
| `transactions` table has `merchant_stable_id` column | ✅ In storage.py schema |

### Still Needs Fixing (Pre-Phase 2)

| Issue | Location | Fix Required |
|-------|----------|--------------|
| **`merchant_mappings` schema broken** | storage.py line 67-77 | See "Schema Fix" section below |
| **LLM response parsing needs robustness** | Phase 2 code | Add code fence handling, key normalization, JSON extraction fallbacks |

### Assessed & Deferred

| Item | Assessment | Decision |
|------|------------|----------|
| **Batch↔doc junction table** | Feedback suggests adding for Phase 3 scoping | **DEFERRED** - YAGNI. Current `batch_id` in batches table + `doc_id` in transactions is sufficient. Add FK to documents if needed later. |
| **Transaction fingerprint (sha256)** | Feedback suggests `(doc_id, date, merchant_stable_id, amount, direction)` | **DEFERRED** - Current `(doc_id, date, merchant, amount)` dedup works. Add fingerprint only if real collisions appear in logs. |
| **Update by stable_id in Phase 3 tools** | Required for chat correction | **IMPLEMENT IN PHASE 3** - But merchant_mappings must be stable_id keyed NOW to avoid mess. |

---

## 🔧 Phinance Prompt Schema Fix (CRITICAL - Next Priority)

_Added: Session 34_

### Problem: System vs User Prompt Conflict

The Modelfile bakes in a system prompt with a 3-field schema, but the user prompt asks for 4 fields.

| Conflict | System Prompt (Modelfile) | User Prompt |
|----------|---------------------------|-------------|
| Schema fields | 3: `insights`, `recommendations`, `potential_savings` | 4: adds `drain_verifications` |
| Nested structure | Not defined | Complex: `{"1": {"is_drain": bool, "reason": str}}` |
| Conditional field | Static schema | `drain_verifications` only when drains exist |

### Current Modelfile SYSTEM
```
You are a Financial Insight Analyst...

SCHEMA:
{
  "insights": ["..."],
  "recommendations": ["..."],
  "potential_savings": 0.00
}
```

### Current User Prompt Asks For
```json
{
  "insights": ["..."],
  "recommendations": ["..."],
  "potential_savings": 0.00,
  "drain_verifications": {"1": {"is_drain": true, "reason": "..."}}
}
```

### Fix: Dynamic System Prompt (Option C)

**Step 1**: Strip SYSTEM from Modelfile, keep only model + parameters:
```dockerfile
FROM /path/to/phinance-model
TEMPLATE "{{ if .System }}<|system|>..."
PARAMETER top_p 0.9
PARAMETER num_predict 512
PARAMETER temperature 0.3
# NO SYSTEM directive
```

**Step 2**: Pass system prompt at runtime in `_invoke_phinance()`:
```python
def _invoke_phinance(prompt: str, include_drains: bool = False) -> dict:
    schema = {
        "insights": ["..."],
        "recommendations": ["..."],
        "potential_savings": 0.00
    }
    if include_drains:
        schema["drain_verifications"] = {"1": {"is_drain": True, "reason": "..."}}
    
    system_prompt = f"""You are a Financial Insight Analyst. You receive pre-calculated financial data.
Your sole job is to provide qualitative reasoning and professional advice.

RULES:
1. DO NOT DO MATH. Trust the pre-calculated numbers provided in the prompt.
2. BE SPECIFIC: Reference the percentages and amounts provided.
3. NO HALLUCINATIONS: Do not invent transactions.
4. JSON ONLY: Respond with a valid JSON object.

SCHEMA:
{json.dumps(schema, indent=2)}
"""
    
    response = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": "phinance-json",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "format": "json",
            "stream": False
        }
    )
    ...
```

**Files to modify**:
- Ollama Modelfile for phinance-json (remove SYSTEM)
- `home-ai/soa1/models.py` or `agent.py` (add dynamic system prompt)

---

## 🔧 NemoAgent Critic Pass (Quality Assurance - Next Priority)

_Added: Session 34_

### Purpose

Validate Phinance output against source data before returning to user. Catches:
- Insights that contradict the numbers
- Unsupported claims
- Missing obvious insights (large recurring charges)
- Illogical drain verifications

### Hardware Context

- **GPU 0**: NemoAgent (13GB) - always warm, orchestrator
- **GPU 1**: Phinance-JSON (4GB) - generator
- Minimum deployment: 2× 3060 12GB

NemoAgent is always loaded → critic pass is **free** (no VRAM cost, ~1-2s latency).

### Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Phinance-JSON  │────▶│   NemoAgent     │────▶│  Retry/Escalate │
│    GPU 1        │     │    GPU 0        │     │  (if fail)      │
│    Generate     │     │    Validate     │     │  qwen fallback  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Implementation

Create `home-ai/soa1/utils/llm_critic.py`:

```python
import requests
import json
import re
from typing import Dict, Any, Tuple

CRITIC_SYSTEM = """You are a financial analysis QA reviewer.
Your job is to validate LLM-generated insights against source data.
Be strict. Flag any inconsistency, unsupported claim, or missing obvious insight."""

CRITIC_USER_TEMPLATE = """
## Source Data (ground truth)
{source_data}

## LLM Output (to validate)
{llm_output}

## Validation Checklist
1. ACCURACY: Do insights match the numbers? (e.g., highest category claim matches data)
2. SUPPORT: Is every claim backed by the source data?
3. COMPLETENESS: Any obvious insight missing? (large recurring charges, top spending anomalies)
4. LOGIC: Are drain_verifications reasonable? (utilities = not drain, subscriptions = maybe drain)
5. ACTIONABLE: Are recommendations specific and achievable?

Reply JSON only:
{{"pass": true, "issues": [], "missing_insights": [], "risk_flags": []}}

If ANY issue found, set pass: false and list issues.
"""

def validate_phinance_output(
    source_data: Dict[str, Any],
    phinance_output: Dict[str, Any]
) -> Tuple[bool, Dict[str, Any]]:
    """
    Validate Phinance output using NemoAgent.
    
    Returns:
        (passed: bool, validation_result: dict)
    """
    prompt = CRITIC_USER_TEMPLATE.format(
        source_data=json.dumps(source_data, indent=2),
        llm_output=json.dumps(phinance_output, indent=2)
    )
    
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "NemoAgent:latest",
                "prompt": f"{CRITIC_SYSTEM}\n\n{prompt}",
                "stream": False
            },
            timeout=60
        )
        
        result = response.json()
        content = result.get("response", "{}")
        
        # Extract JSON from response
        json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
        if json_match:
            validation = json.loads(json_match.group())
            return validation.get("pass", False), validation
        
        return False, {"pass": False, "issues": ["Failed to parse validation response"]}
        
    except Exception as e:
        return False, {"pass": False, "issues": [f"Validation error: {str(e)}"]}
```

### Integration in Pipeline

Update `agent.py` or `batch_processor.py`:

```python
from utils.llm_critic import validate_phinance_output

# After Phinance generates output
phinance_result = _invoke_phinance(prompt)

# Validate with NemoAgent
passed, validation = validate_phinance_output(
    source_data=calculated_summary,
    phinance_output=phinance_result
)

if not passed:
    logger.warning(f"Phinance output failed validation: {validation.get('issues')}")
    # Option 1: Retry with Phinance
    # Option 2: Escalate to qwen
    # Option 3: Return with warnings
    
# Add any missing insights flagged by critic
if validation.get("missing_insights"):
    phinance_result["insights"].extend(validation["missing_insights"])

# Add risk flags if any
if validation.get("risk_flags"):
    phinance_result["risk_flags"] = validation["risk_flags"]
```

### NemoAgent Use Cases Summary

| Role | Description | Cost |
|------|-------------|------|
| **Validation pass** | "Do insights match numbers?" | Free (always warm) |
| **Risk flagger** | Cash advances, unusual spikes | Free |
| **Prompt QA** | JSON schema compliance | Free |
| **Escalation gate** | Decide if qwen retry needed | Free |

### Validation Checklist Details

| Check | What NemoAgent Looks For |
|-------|--------------------------|
| ACCURACY | "Shopping is 31.8%" - does insight match? |
| SUPPORT | Every claim has backing data |
| COMPLETENESS | $3,916/year Apple subscriptions mentioned? |
| LOGIC | Utilities marked as "not drain" (necessary) |
| ACTIONABLE | "Reduce dining" not "spend less" |

### Metrics to Track

- `phinance_validation_pass_rate` - target >90%
- `phinance_retry_rate` - should be <10%
- `common_issues` - log for prompt improvement

---

## 🔧 Schema Fix: merchant_mappings (COMPLETED - Session 34)

### Current Schema (BROKEN)
```sql
CREATE TABLE merchant_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE,  -- WRONG: conflicts with below
    category TEXT,
    confidence_score REAL DEFAULT 0.0,
    times_confirmed INTEGER DEFAULT 0,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (raw_name, category)  -- WRONG: allows same merchant with different categories
)
```

**Problems:**
1. `UNIQUE(raw_name, category)` allows duplicate merchants if category changes
2. `normalized_name UNIQUE` conflicts - two raw names can normalize to same merchant
3. Missing `merchant_stable_id` - the actual identity key
4. Missing `source` column - can't distinguish regex/llm/user

### Fixed Schema
```sql
CREATE TABLE merchant_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_stable_id TEXT NOT NULL UNIQUE,  -- PRIMARY IDENTITY
    raw_name TEXT,                             -- Sample/last-seen (not unique)
    normalized_name TEXT NOT NULL,             -- Display name (not unique)
    category TEXT,
    confidence_score REAL DEFAULT 0.0,
    source TEXT DEFAULT 'regex',               -- 'regex', 'phinance', 'user_confirmed'
    flagged INTEGER DEFAULT 0,                 -- 1 if needs review
    times_confirmed INTEGER DEFAULT 0,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### Migration Path (table is empty, so simple)
```python
# In storage.py init_db(), replace merchant_mappings CREATE TABLE with fixed schema
# No data migration needed - table has 0 rows
```

### UPSERT Logic After Fix
```python
INSERT INTO merchant_mappings
    (merchant_stable_id, raw_name, normalized_name, category, confidence_score, source, flagged)
VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(merchant_stable_id) DO UPDATE SET
    category = excluded.category,
    confidence_score = excluded.confidence_score,
    source = excluded.source,
    flagged = excluded.flagged,
    times_confirmed = times_confirmed + 1,
    last_seen = CURRENT_TIMESTAMP,
    updated_at = CURRENT_TIMESTAMP
```

---

## Phase 1: Transaction Duplication Bug Fix

**Priority**: CRITICAL - Must be fixed first
**Estimated Time**: 30 minutes
**Files**: `batch_processor.py`, `agent.py`

### Problem

All transactions saved to ALL doc_ids instead of their source doc_id, causing 5-6x duplication.

### Implementation Steps

#### Step 1.1: Modify `batch_processor.py`

Location: `background_full_process()` method (~line 463-481)

**Current (buggy)**:
```python
all_text = "\n".join(all_text_parts)
# ... extraction from combined text
transactions = _extract_apple_card_transactions(all_text)
state.extracted_transactions = transactions
```

**Replace with**:
```python
# Extract per-document, tag with doc_id
all_transactions = []
for doc in state.files:
    doc_id = doc.get("doc_id")
    text = doc.get("full_text", "")
    is_apple = doc.get("is_apple_card", False)
    
    if not text:
        continue
    
    if is_apple:
        doc_transactions = _extract_apple_card_transactions(text)
    else:
        doc_transactions = _regex_extract(text, GENERIC_BANK_REGEX)
    
    # Tag each transaction with source doc_id
    for tx in doc_transactions:
        tx["doc_id"] = doc_id
    
    all_transactions.extend(doc_transactions)
    logger.info(f"Extracted {len(doc_transactions)} transactions from {doc_id}")

state.extracted_transactions = all_transactions
state.transaction_count = len(all_transactions)
```

**Note**: Keep `all_text` for Phinance prompt, but extract transactions per-doc.

#### Step 1.2: Modify `agent.py`

Location: `_handle_consent_and_analysis()` method (~line 277-287)

**Current (buggy)**:
```python
for doc_id in doc_ids:
    doc_txns = [t for t in all_transactions]  # WRONG
    if doc_txns:
        fa_storage.save_transactions_for_doc(doc_id, doc_txns)
```

**Replace with**:
```python
for doc_id in doc_ids:
    doc_txns = [t for t in all_transactions if t.get("doc_id") == doc_id]
    if doc_txns:
        fa_storage.save_transactions_for_doc(doc_id, doc_txns)
        logger.info(f"Persisted {len(doc_txns)} transactions for {doc_id}")
```

#### Step 1.3: Clean Up Existing Data

Run once after deploying the fix:

```python
# cleanup_duplicates.py
import sqlite3

conn = sqlite3.connect('/home/ryzen/projects/home-ai/finance-agent/data/finance.db')

# Count before
before = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
print(f"Transactions before: {before}")

# Delete duplicates, keep lowest ID per unique transaction
conn.execute("""
    DELETE FROM transactions WHERE id NOT IN (
        SELECT MIN(id) FROM transactions 
        GROUP BY doc_id, date, merchant, amount
    )
""")
conn.commit()

# Count after
after = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
print(f"Transactions after: {after}")
print(f"Removed {before - after} duplicates")

conn.close()
```

#### Step 1.4: Verification

```bash
# Restart services
sudo systemctl restart soa1-api.service

# Check DB
python3 -c "
import sqlite3
conn = sqlite3.connect('home-ai/finance-agent/data/finance.db')
cur = conn.execute('''
    SELECT doc_id, date, merchant, amount, COUNT(*) as count 
    FROM transactions 
    GROUP BY doc_id, date, merchant, amount 
    HAVING count > 1
    LIMIT 5
''')
dupes = cur.fetchall()
print(f'Remaining duplicates: {len(dupes)}')
for d in dupes:
    print(f'  {d}')
"
```

---

## Phase 2: LLM-Assisted Categorization

**Priority**: High
**Estimated Time**: 2-3 hours
**Files**: `models.py`, `batch_processor.py`, `storage.py`, `merchant_normalizer.py`
**Reference**: `RemAssist/LLM_MERCHANT_CATEGORIZATION.md`

### Implementation Steps

#### Step 2.1: Add DB Schema Changes

In `storage.py`, add migration in `init_db()`:

```python
# Add new columns to merchant_mappings
try:
    conn.execute("ALTER TABLE merchant_mappings ADD COLUMN source TEXT DEFAULT 'regex'")
except sqlite3.OperationalError:
    pass

try:
    conn.execute("ALTER TABLE merchant_mappings ADD COLUMN flagged INTEGER DEFAULT 0")
except sqlite3.OperationalError:
    pass

try:
    conn.execute("ALTER TABLE merchant_mappings ADD COLUMN merchant_stable_id TEXT")
except sqlite3.OperationalError:
    pass
```

#### Step 2.2: Add Phinance Warming Function

In `models.py`:

```python
def warm_phinance():
    """Pre-load Phinance model into VRAM. Fire-and-forget."""
    try:
        response = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": "phinance-json",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a financial transaction categorization specialist. Your role is to accurately categorize merchant transactions. Be ready for categorization tasks."
                    },
                    {"role": "user", "content": "Acknowledge readiness."}
                ],
                "stream": False
            },
            timeout=30
        )
        logger.info("Phinance model warmed up")
    except Exception as e:
        logger.warning(f"Phinance warmup failed: {e}")
```

#### Step 2.3: Add Batch Categorization Function

In `models.py`:

```python
VALID_CATEGORIES = [
    "dining", "groceries", "gas", "entertainment", "shopping", 
    "travel", "utilities", "subscriptions", "health", "transfer", "cash", "other"
]

def categorize_merchants_llm(merchants: List[str]) -> Dict[str, str]:
    """
    Categorize a list of merchant names using Phinance.
    Returns dict mapping merchant_name -> category.
    """
    if not merchants:
        return {}
    
    merchant_list = "\n".join(f"- {m}" for m in merchants)
    prompt = f"""Categorize each merchant into exactly ONE category from this list:
{', '.join(VALID_CATEGORIES)}

Merchants:
{merchant_list}

Return valid JSON only: {{"merchant_name": "category", ...}}"""

    try:
        response = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": "phinance-json",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a financial transaction categorization specialist. Return valid JSON only."
                    },
                    {"role": "user", "content": prompt}
                ],
                "format": "json",
                "stream": False
            },
            timeout=60
        )
        
        result = response.json()
        content = result.get("message", {}).get("content", "{}")
        categories = json.loads(content)
        
        # Validate categories
        validated = {}
        for merchant, cat in categories.items():
            if cat.lower() in VALID_CATEGORIES:
                validated[merchant] = cat.lower()
            else:
                validated[merchant] = "other"
        
        return validated
        
    except Exception as e:
        logger.error(f"LLM categorization failed: {e}")
        return {m: "other" for m in merchants}
```

#### Step 2.4: Integrate into Extraction Flow

In `batch_processor.py`, after extraction and before saving to state:

```python
from models import warm_phinance, categorize_merchants_llm
from home_ai.finance_agent.src import storage as fa_storage

# After Python regex categorization pass
unknown_merchants = set()
for tx in all_transactions:
    if tx.get("category") == "other" or not tx.get("category"):
        raw = tx.get("merchant", "")
        # Check cache first
        cached = fa_storage.get_merchant_mapping(raw)
        if cached and cached.get("category"):
            tx["category"] = cached["category"]
            tx["category_source"] = cached.get("source", "cache")
        else:
            unknown_merchants.add(raw)

# Batch LLM call for unknowns
if unknown_merchants:
    logger.info(f"Sending {len(unknown_merchants)} unknown merchants to Phinance")
    llm_categories = categorize_merchants_llm(list(unknown_merchants))
    
    for tx in all_transactions:
        raw = tx.get("merchant", "")
        if raw in llm_categories:
            tx["category"] = llm_categories[raw]
            tx["category_source"] = "phinance"
            
            # Cache the result
            flagged = 1 if llm_categories[raw] == "other" else 0
            fa_storage.upsert_merchant_mapping(
                raw_name=raw,
                normalized_name=raw,  # or use normalize_merchant()
                category=llm_categories[raw],
                confidence=0.85,
                source="phinance",
                flagged=flagged
            )
```

#### Step 2.5: Update `upsert_merchant_mapping()` Signature

In `storage.py`:

```python
def upsert_merchant_mapping(
    raw_name: str,
    normalized_name: str,
    category: Optional[str],
    confidence: float = 0.0,
    source: str = "regex",
    flagged: int = 0,
) -> int:
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO merchant_mappings
                (raw_name, normalized_name, category, confidence_score, source, flagged)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(raw_name, category) DO UPDATE SET
                confidence_score = excluded.confidence_score,
                times_confirmed = times_confirmed + 1,
                last_seen = CURRENT_TIMESTAMP,
                source = excluded.source,
                flagged = excluded.flagged
            """,
            (raw_name, normalized_name, category, confidence, source, flagged),
        )
        conn.commit()
        return cursor.lastrowid
```

---

## Phase 3: Chat-Based Merchant Correction

**Priority**: Medium
**Estimated Time**: 3-4 hours
**Files**: `agent.py`, `storage.py`, new `tools/merchant_tools.py`
**Reference**: `RemAssist/merchant_helper.md`

### Implementation Steps

#### Step 3.1: Create Merchant Tools Module

Create `home-ai/soa1/tools/merchant_tools.py`:

```python
"""
Merchant category correction tools for LLM function calling.
LLM interprets user intent, these functions execute deterministically.
"""

import sqlite3
from typing import List, Dict, Optional, Any
from difflib import SequenceMatcher
from home_ai.finance_agent.src import storage as fa_storage

def find_merchant_candidates(
    query: str,
    batch_id: Optional[str] = None,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Find merchant candidates matching a user query.
    Returns ranked list with similarity scores.
    """
    query_lower = query.lower()
    query_tokens = set(query_lower.split())
    
    with fa_storage.get_db() as conn:
        # Get merchants from mappings and current transactions
        rows = conn.execute("""
            SELECT DISTINCT 
                m.id as merchant_id,
                m.normalized_name,
                m.raw_name,
                m.category,
                m.source,
                m.confidence_score,
                COUNT(t.id) as txn_count,
                COALESCE(SUM(t.amount), 0) as total_amount
            FROM merchant_mappings m
            LEFT JOIN transactions t ON t.merchant = m.normalized_name
            GROUP BY m.id
        """).fetchall()
    
    candidates = []
    for row in rows:
        name = row[1] or row[2]  # normalized or raw
        name_lower = name.lower()
        
        # Calculate similarity score
        seq_score = SequenceMatcher(None, query_lower, name_lower).ratio()
        
        # Token overlap bonus
        name_tokens = set(name_lower.split())
        overlap = len(query_tokens & name_tokens) / max(len(query_tokens), 1)
        
        # Prefix match bonus
        prefix_bonus = 0.2 if name_lower.startswith(query_lower[:3]) else 0
        
        score = seq_score * 0.5 + overlap * 0.3 + prefix_bonus + (row[6] / 100) * 0.1
        
        candidates.append({
            "merchant_id": row[0],
            "normalized_name": row[1],
            "raw_name": row[2],
            "current_category": row[3],
            "source": row[4],
            "txn_count": row[6],
            "total_amount": row[7],
            "similarity_score": round(score, 3)
        })
    
    # Sort by score, return top N
    candidates.sort(key=lambda x: x["similarity_score"], reverse=True)
    return candidates[:limit]


def update_merchant_category(
    merchant_id: int,
    new_category: str,
    batch_id: Optional[str] = None,
    scope: str = "global"  # "global" or "batch"
) -> Dict[str, Any]:
    """
    Update merchant category and relabel transactions.
    Returns summary of changes.
    """
    with fa_storage.get_db() as conn:
        # Get current state
        row = conn.execute(
            "SELECT normalized_name, category FROM merchant_mappings WHERE id = ?",
            (merchant_id,)
        ).fetchone()
        
        if not row:
            return {"success": False, "error": "Merchant not found"}
        
        old_category = row[1]
        normalized_name = row[0]
        
        # Log the change
        conn.execute("""
            INSERT INTO mapping_change_log 
                (merchant_id, old_category, new_category, batch_id, source)
            VALUES (?, ?, ?, ?, 'user')
        """, (merchant_id, old_category, new_category, batch_id))
        
        # Update mapping
        conn.execute("""
            UPDATE merchant_mappings 
            SET category = ?, source = 'user_confirmed', 
                confidence_score = 1.0, times_confirmed = times_confirmed + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_category, merchant_id))
        
        # Update transactions
        if scope == "global":
            result = conn.execute("""
                UPDATE transactions SET category = ? 
                WHERE merchant = ?
            """, (new_category, normalized_name))
        else:
            result = conn.execute("""
                UPDATE transactions SET category = ? 
                WHERE merchant = ? AND doc_id IN (
                    SELECT doc_id FROM batches WHERE batch_id = ?
                )
            """, (new_category, normalized_name, batch_id))
        
        conn.commit()
        
        return {
            "success": True,
            "merchant": normalized_name,
            "old_category": old_category,
            "new_category": new_category,
            "transactions_updated": result.rowcount
        }


def undo_last_mapping_change() -> Dict[str, Any]:
    """Revert the most recent user-initiated category change."""
    with fa_storage.get_db() as conn:
        # Get last change
        row = conn.execute("""
            SELECT id, merchant_id, old_category, new_category 
            FROM mapping_change_log 
            WHERE source = 'user'
            ORDER BY timestamp DESC LIMIT 1
        """).fetchone()
        
        if not row:
            return {"success": False, "error": "No changes to undo"}
        
        log_id, merchant_id, old_cat, new_cat = row
        
        # Get merchant name
        merchant = conn.execute(
            "SELECT normalized_name FROM merchant_mappings WHERE id = ?",
            (merchant_id,)
        ).fetchone()[0]
        
        # Revert mapping
        conn.execute("""
            UPDATE merchant_mappings SET category = ? WHERE id = ?
        """, (old_cat, merchant_id))
        
        # Revert transactions
        conn.execute("""
            UPDATE transactions SET category = ? WHERE merchant = ?
        """, (old_cat, merchant))
        
        # Mark log entry as undone
        conn.execute(
            "DELETE FROM mapping_change_log WHERE id = ?", (log_id,)
        )
        
        conn.commit()
        
        return {
            "success": True,
            "merchant": merchant,
            "reverted_from": new_cat,
            "reverted_to": old_cat
        }
```

#### Step 3.2: Add Change Log Table

In `storage.py` `init_db()`:

```python
conn.execute("""
    CREATE TABLE IF NOT EXISTS mapping_change_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        merchant_id INTEGER NOT NULL,
        old_category TEXT,
        new_category TEXT,
        batch_id TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        source TEXT DEFAULT 'user',
        FOREIGN KEY (merchant_id) REFERENCES merchant_mappings(id)
    )
""")
```

#### Step 3.3: Register Tools with Agent

In `agent.py`, add tool definitions for function calling:

```python
MERCHANT_TOOLS = [
    {
        "name": "find_merchant_candidates",
        "description": "Search for merchants matching a user query. Use when user wants to change a merchant's category.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Merchant name to search for"},
                "batch_id": {"type": "string", "description": "Optional batch ID to scope search"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "update_merchant_category",
        "description": "Change a merchant's category. Use after confirming which merchant to update.",
        "parameters": {
            "type": "object",
            "properties": {
                "merchant_id": {"type": "integer", "description": "ID of merchant to update"},
                "new_category": {"type": "string", "description": "New category to assign"},
                "scope": {"type": "string", "enum": ["global", "batch"], "default": "global"}
            },
            "required": ["merchant_id", "new_category"]
        }
    },
    {
        "name": "undo_last_mapping_change",
        "description": "Undo the most recent merchant category change.",
        "parameters": {"type": "object", "properties": {}}
    }
]
```

#### Step 3.4: Handle Tool Calls in Agent

Add tool execution logic in agent's message processing:

```python
from tools.merchant_tools import (
    find_merchant_candidates,
    update_merchant_category,
    undo_last_mapping_change
)

def _execute_tool(self, tool_name: str, args: Dict) -> str:
    """Execute a tool and return result as string for LLM."""
    if tool_name == "find_merchant_candidates":
        results = find_merchant_candidates(**args)
        if not results:
            return "No matching merchants found."
        return json.dumps(results[:3], indent=2)
    
    elif tool_name == "update_merchant_category":
        result = update_merchant_category(**args)
        if result["success"]:
            return f"Updated {result['merchant']}: {result['old_category']} → {result['new_category']} ({result['transactions_updated']} transactions)"
        return f"Failed: {result['error']}"
    
    elif tool_name == "undo_last_mapping_change":
        result = undo_last_mapping_change()
        if result["success"]:
            return f"Reverted {result['merchant']}: {result['reverted_from']} → {result['reverted_to']}"
        return f"Failed: {result['error']}"
    
    return f"Unknown tool: {tool_name}"
```

---

## Testing Checklist

### Phase 1 Tests
- [ ] Upload 5 PDFs, verify each transaction has correct `doc_id`
- [ ] Check DB: no duplicate transactions
- [ ] Dashboard shows correct transaction count

### Phase 2 Tests
- [ ] Upload new batch, check "Other" category percentage
- [ ] Verify Phinance called only for unknown merchants
- [ ] Check `merchant_mappings` table for new entries with `source='phinance'`
- [ ] Re-upload same PDFs, verify cache hit (no Phinance call)

### Phase 3 Tests
- [ ] Chat: "Move Chintu Communication to Utilities"
- [ ] Verify disambiguation prompt if multiple matches
- [ ] Check transaction categories updated
- [ ] Chat: "Undo last change" - verify revert works
- [ ] Check `mapping_change_log` table for audit trail

---

## Rollback Procedures

### Phase 1
No rollback needed - bug fix only.

### Phase 2
Set feature flag: `USE_LLM_CATEGORIZATION = False` in `batch_processor.py`

### Phase 3
Comment out tool registrations in `agent.py`. Chat corrections won't work but system remains functional.

---

## Success Metrics

| Metric | Before | Target |
|--------|--------|--------|
| "Other" category % | 65% | <15% |
| Transaction duplication | 5-6x | 1x |
| Category correction time | N/A | <30s via chat |
| Cache hit rate | N/A | >80% after 1 week |

---

## Phase 2.5: Backfill Existing "Other" Merchants

**Priority**: High (run after Phase 2 deployment)
**Estimated Time**: 5-10 minutes (automated)
**Dependency**: Phase 2 must be complete

### Current State
- 412 unique merchants in "Other" category
- 6306 transactions affected
- Top offenders: Apple variants, American Taxi, Bombay Mart, ComEd, Village of Algonquin

### Backfill Script

Save as `scripts/backfill_other_merchants.py`:

```python
#!/usr/bin/env python3
"""
One-time backfill script to categorize existing "Other" merchants.
Run AFTER Phase 2 (LLM Categorization) is deployed.
"""

import sys
sys.path.insert(0, "/home/ryzen/projects/home-ai/soa1")
sys.path.insert(0, "/home/ryzen/projects")

from models import categorize_merchants_llm
from home_ai.finance_agent.src import storage as fa_storage

def main():
    # Get unique merchants in Other
    with fa_storage.get_db() as conn:
        rows = conn.execute('''
            SELECT DISTINCT merchant FROM transactions 
            WHERE category = 'other' OR category IS NULL
        ''').fetchall()

    merchants = [r[0] for r in rows]
    print(f"Found {len(merchants)} merchants to categorize")
    
    if not merchants:
        print("No merchants to backfill!")
        return

    categorized = 0
    still_other = 0
    
    # Batch in chunks of 50
    for i in range(0, len(merchants), 50):
        chunk = merchants[i:i+50]
        print(f"\nProcessing batch {i//50 + 1} ({len(chunk)} merchants)...")
        
        results = categorize_merchants_llm(chunk)
        
        with fa_storage.get_db() as conn:
            for merchant, category in results.items():
                flagged = 1 if category == "other" else 0
                
                if category != "other":
                    categorized += 1
                else:
                    still_other += 1
                
                # Upsert mapping
                conn.execute('''
                    INSERT INTO merchant_mappings 
                        (raw_name, normalized_name, category, confidence_score, source, flagged)
                    VALUES (?, ?, ?, 0.85, 'phinance_backfill', ?)
                    ON CONFLICT(raw_name, category) DO UPDATE SET
                        category = excluded.category,
                        source = 'phinance_backfill',
                        flagged = excluded.flagged,
                        last_seen = CURRENT_TIMESTAMP
                ''', (merchant, merchant, category, flagged))
                
                # Update transactions
                conn.execute(
                    "UPDATE transactions SET category = ? WHERE merchant = ?",
                    (category, merchant)
                )
            
            conn.commit()
        
        print(f"Processed {min(i+50, len(merchants))}/{len(merchants)}")

    print(f"\n=== Backfill Complete ===")
    print(f"Categorized: {categorized}")
    print(f"Still Other: {still_other}")
    print(f"Success rate: {categorized / len(merchants) * 100:.1f}%")

if __name__ == "__main__":
    main()
```

### Run Instructions

```bash
cd /home/ryzen/projects
python3 scripts/backfill_other_merchants.py
```

### Verification

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('home-ai/finance-agent/data/finance.db')
total = conn.execute('SELECT COUNT(*) FROM transactions').fetchone()[0]
other = conn.execute(\"SELECT COUNT(*) FROM transactions WHERE category = 'other' OR category IS NULL\").fetchone()[0]
print(f'Other: {other}/{total} ({other/total*100:.1f}%)')
"
```

**Target**: <15% in "Other" category after backfill
