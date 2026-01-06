"""
Deterministic financial calculations for transaction analysis.

LLMs struggle with arithmetic on large datasets. This module provides
accurate Python-based calculations while LLMs handle qualitative analysis.

Architecture:
    PDF → Extract → LLM Categorizes → Python Calculates → LLM Insights
                                            ↑
                                    (this module)
"""

from typing import List, Dict, Any, Optional
from collections import defaultdict
import re


def strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences from LLM response."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def calculate_financials(transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate accurate financial summary from transaction list.

    Args:
        transactions: List of transaction dicts with keys:
            - amount: float (required)
            - category: str (optional, defaults to 'other')
            - merchant: str (optional)
            - date: str (optional)

    Returns:
        Dictionary with:
            - total_spent: float
            - transaction_count: int
            - categories: dict of category -> total
            - top_merchants: list of {merchant, total, count}
            - date_range: {start, end} if dates present
            - avg_transaction: float
    """
    if not transactions:
        return {
            "total_spent": 0.0,
            "transaction_count": 0,
            "categories": {},
            "top_merchants": [],
            "date_range": None,
            "avg_transaction": 0.0,
        }

    total = 0.0
    category_totals: Dict[str, float] = defaultdict(float)
    merchant_data: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"total": 0.0, "count": 0}
    )
    dates: List[str] = []

    for tx in transactions:
        amount = abs(float(tx.get("amount", 0)))
        total += amount

        category = tx.get("category", "Other").strip()
        if not category:
            category = "Other"
        # Normalize to Title Case for consistency
        category = category.title()
        category_totals[category] += amount

        merchant = tx.get("merchant", "").strip()
        if merchant:
            normalized_merchant = _normalize_merchant_name(merchant)
            merchant_data[normalized_merchant]["total"] += amount
            merchant_data[normalized_merchant]["count"] += 1
            merchant_data[normalized_merchant]["original"] = merchant

        date = tx.get("date", "")
        if date:
            dates.append(date)

    sorted_merchants = sorted(
        merchant_data.items(), key=lambda x: x[1]["total"], reverse=True
    )
    top_merchants = [
        {
            "merchant": data.get("original", name),
            "total": round(data["total"], 2),
            "count": data["count"],
        }
        for name, data in sorted_merchants[:10]
    ]

    sorted_categories = dict(
        sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
    )

    date_range = None
    if dates:
        sorted_dates = sorted(dates)
        date_range = {"start": sorted_dates[0], "end": sorted_dates[-1]}

    tx_count = len(transactions)

    hidden_drains = detect_hidden_drains(transactions)

    return {
        "total_spent": round(total, 2),
        "transaction_count": tx_count,
        "categories": {k: round(v, 2) for k, v in sorted_categories.items()},
        "top_merchants": top_merchants,
        "hidden_drains": hidden_drains,
        "date_range": date_range,
        "avg_transaction": round(total / tx_count, 2) if tx_count > 0 else 0.0,
    }


def _normalize_merchant_name(merchant: str) -> str:
    """
    Normalize merchant name for grouping similar merchants.

    Examples:
        "APPLE.COM/BILL ONE APPLE PARK WAY" -> "apple.com/bill"
        "BUTERA FRUIT MARKET 100 S RANDALL ROAD" -> "butera fruit market"
    """
    name = merchant.lower().strip()

    parts = name.split()
    if len(parts) > 3:
        name = " ".join(parts[:3])

    for suffix in ["llc", "inc", "corp", "ltd"]:
        name = name.replace(f" {suffix}", "")

    return name.strip()


def detect_hidden_drains(
    transactions: List[Dict[str, Any]],
    threshold: float = 50.0,
    min_frequency: int = 3,
) -> List[Dict[str, Any]]:
    """
    Detect small recurring charges that add up over time.

    Hidden drains are merchants with:
    - Average transaction under threshold (default $50)
    - Appearing min_frequency or more times (default 3+)
    """
    merchant_txns: Dict[str, List[float]] = defaultdict(list)
    merchant_names: Dict[str, str] = {}

    for tx in transactions:
        merchant = tx.get("merchant", "").strip()
        if not merchant:
            continue

        amount = abs(float(tx.get("amount", 0)))
        normalized = _normalize_merchant_name(merchant)
        merchant_txns[normalized].append(amount)
        merchant_names[normalized] = merchant

    drains = []
    for normalized, amounts in merchant_txns.items():
        if len(amounts) < min_frequency:
            continue

        avg_amount = sum(amounts) / len(amounts)
        if avg_amount >= threshold:
            continue

        total_period = sum(amounts)
        annual_cost = total_period * 4

        drains.append(
            {
                "merchant": merchant_names.get(normalized, normalized),
                "avg_amount": round(avg_amount, 2),
                "frequency": len(amounts),
                "total_period": round(total_period, 2),
                "annual_cost": round(annual_cost, 2),
            }
        )

    return sorted(drains, key=lambda x: x["annual_cost"], reverse=True)


def calculate_category_percentages(
    categories: Dict[str, float], total: float
) -> Dict[str, Dict[str, Any]]:
    """
    Calculate percentage breakdown for each category.

    Args:
        categories: Dict of category -> total amount
        total: Total spending amount

    Returns:
        Dict of category -> {amount, percentage}
    """
    if total <= 0:
        return {}

    return {
        cat: {"amount": round(amt, 2), "percentage": round((amt / total) * 100, 1)}
        for cat, amt in categories.items()
    }


def build_insights_prompt(
    transactions: List[Dict[str, Any]], summary: Dict[str, Any]
) -> str:
    """
    Build a prompt for Phinance that includes pre-calculated numbers.

    The LLM only needs to provide qualitative insights, not do math.

    Args:
        transactions: Raw transaction list
        summary: Output from calculate_financials()

    Returns:
        Formatted prompt string for Phinance
    """
    categories_with_pct = calculate_category_percentages(
        summary.get("categories", {}), summary.get("total_spent", 0)
    )

    cat_lines = []
    for cat, data in categories_with_pct.items():
        cat_lines.append(f"  - {cat}: ${data['amount']:,.2f} ({data['percentage']}%)")

    merchant_lines = []
    for m in summary.get("top_merchants", [])[:5]:
        merchant_lines.append(
            f"  - {m['merchant']}: ${m['total']:,.2f} ({m['count']} transactions)"
        )

    date_info = ""
    if summary.get("date_range"):
        dr = summary["date_range"]
        date_info = f"Date range: {dr['start']} to {dr['end']}"

    drain_lines = []
    drains = summary.get("hidden_drains", [])[:5]
    for i, d in enumerate(drains, 1):
        drain_lines.append(
            f"  {i}. {d['merchant']}: ${d['avg_amount']:.2f} avg × {d['frequency']} times = ${d['total_period']:.2f} (${d['annual_cost']:.2f}/year projected)"
        )

    drains_section = ""
    drains_task = ""
    example_json = '{{"insights": ["...", "..."], "recommendations": ["...", "..."], "potential_savings": 0.00}}'

    if drain_lines:
        drains_section = f"""
### Potential Hidden Drains (small recurring charges <$50, 3+ times):
{chr(10).join(drain_lines)}
"""
        drains_task = f"""4. drain_verifications: Review each numbered drain above. For each, determine if it's a TRUE drain (discretionary/wasteful) or FALSE (necessary expense). Return object with drain numbers as keys: {{"1": {{"is_drain": true, "reason": "brief explanation"}}, "2": {{"is_drain": false, "reason": "..."}}}}"""
        example_json = '{{"insights": ["...", "..."], "recommendations": ["...", "..."], "potential_savings": 0.00, "drain_verifications": {{"1": {{"is_drain": true, "reason": "..."}}, "2": {{"is_drain": false, "reason": "..."}}}}}}'

    prompt = f"""Analyze this financial data and provide insights.

## Pre-calculated Summary (DO NOT recalculate these numbers)

Total Spent: ${summary.get("total_spent", 0):,.2f}
Transaction Count: {summary.get("transaction_count", 0)}
Average Transaction: ${summary.get("avg_transaction", 0):,.2f}
{date_info}

### Spending by Category:
{chr(10).join(cat_lines)}

### Top Merchants:
{chr(10).join(merchant_lines)}
{drains_section}
## Your Task

Based on the above ACCURATE numbers, provide:
1. insights: 3-5 specific observations about spending patterns (reference the percentages and amounts above)
2. recommendations: 2-3 actionable money-saving suggestions
3. potential_savings: estimated monthly savings if recommendations are followed
{drains_task}

IMPORTANT: The "Other" category is a catch-all for uncategorized transactions. Do NOT mention "Other" in your insights or recommendations - it's not actionable. Focus on specific named categories like Shopping, Travel, Dining, etc.

Respond with valid JSON only:
{example_json}
"""
    return prompt


def merge_calculated_with_llm_response(
    calculated: Dict[str, Any],
    llm_response: Dict[str, Any],
    transactions: List[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Merge Python-calculated numbers with LLM-generated insights.

    Args:
        calculated: Output from calculate_financials()
        llm_response: Parsed JSON from LLM (insights, recommendations, drain_verifications)
        transactions: Optional raw transaction list to include in output

    Returns:
        Complete analysis dict with accurate numbers and qualitative insights
    """
    drain_verifications = llm_response.get("drain_verifications", {})

    hidden_drains = calculated.get("hidden_drains", [])[:5]
    for i, drain in enumerate(hidden_drains):
        key = str(i + 1)
        verification = drain_verifications.get(key)
        if verification:
            drain["is_drain"] = verification.get("is_drain", True)
            drain["llm_reason"] = verification.get("reason", "")
        else:
            drain["is_drain"] = True
            drain["llm_reason"] = "Not verified by LLM"

    result = {
        "total_spent": calculated.get("total_spent", 0),
        "transaction_count": calculated.get("transaction_count", 0),
        "categories": calculated.get("categories", {}),
        "top_merchants": calculated.get("top_merchants", []),
        "hidden_drains": hidden_drains,
        "date_range": calculated.get("date_range"),
        "avg_transaction": calculated.get("avg_transaction", 0),
        "insights": llm_response.get("insights", []),
        "recommendations": llm_response.get("recommendations", []),
        "potential_savings": llm_response.get("potential_savings", 0),
    }

    if transactions:
        result["transactions"] = transactions

    return result
