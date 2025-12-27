"""
Dashboard JSON Converter - Transforms phinance output to dashboard-compatible format.
"""

import json
import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _parse_date(date_str: str) -> str:
    """Convert MM/DD/YYYY or DD-MM-YYYY to YYYY-MM-DD format."""
    if not date_str:
        return ""

    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str

    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", date_str)
    if match:
        month, day, year = match.groups()
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"

    match = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{4})$", date_str)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"

    return date_str


def _generate_transaction_id(txn: Dict[str, Any], index: int) -> str:
    key = f"{txn.get('date', '')}-{txn.get('merchant', '')}-{txn.get('amount', '')}-{index}"
    hash_suffix = hashlib.md5(key.encode()).hexdigest()[:8]
    return f"txn{str(index).zfill(5)}_{hash_suffix}"


CATEGORY_MAP = {
    "Groceries": "Groceries",
    "Grocery": "Groceries",
    "Food": "Groceries",
    "Dining": "Dining",
    "Restaurant": "Dining",
    "Restaurants": "Dining",
    "Transport": "Transportation",
    "Transportation": "Transportation",
    "Travel": "Travel",
    "Gas": "Transportation",
    "Fuel": "Transportation",
    "Shopping": "Shopping",
    "Retail": "Shopping",
    "Healthcare": "Healthcare",
    "Medical": "Healthcare",
    "Pharmacy": "Healthcare",
    "Utilities": "Utilities",
    "Bills": "Utilities",
    "Subscriptions": "Subscriptions",
    "Subscription": "Subscriptions",
    "Entertainment": "Entertainment",
    "Services": "Services",
    "Other": "Other",
}


def _normalize_category(category: str) -> str:
    if not category:
        return "Other"
    normalized = category.strip().title()
    return CATEGORY_MAP.get(normalized, normalized)


def convert_transactions(
    phinance_transactions: Dict[str, Any], confidence_default: float = 0.95
) -> Dict[str, Any]:
    """
    Convert phinance transactions.json to dashboard format.

    Expected input: {"transactions": [{"date": "MM/DD/YYYY", "merchant": "...", "amount": 10.50, "category": "..."}]}
    Output: {"transactions": [{"id": "txn00001", "date": "YYYY-MM-DD", "merchant": "...", "category": "...", "amount": -10.50, "confidence": 0.95}]}
    """
    raw_txns = phinance_transactions.get("transactions", [])

    converted = []
    for i, txn in enumerate(raw_txns):
        date_str = _parse_date(txn.get("date", ""))
        merchant = txn.get("merchant", "Unknown Merchant")
        category = _normalize_category(txn.get("category", "Other"))

        amount = txn.get("amount", 0.0)
        if amount > 0:
            amount = -abs(amount)

        confidence = txn.get("confidence", confidence_default)

        converted.append(
            {
                "id": _generate_transaction_id(txn, i),
                "date": date_str,
                "merchant": merchant,
                "category": category,
                "amount": round(amount, 2),
                "confidence": round(confidence, 2),
            }
        )

    converted.sort(key=lambda x: x["date"], reverse=True)
    return {"transactions": converted}


def convert_analysis(
    phinance_analysis: Dict[str, Any],
    transactions_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convert phinance analysis.json to dashboard format with summary metrics.

    Expected input: {"total_spent": 8321.71, "by_category": {...}, "insights": [...], "recommendations": [...]}
    Output: {"summary": {...}, "categories": [...], "insights": [...], "recommendations": [...], "potential_savings": 702.14}
    """
    total_spent = abs(phinance_analysis.get("total_spent", 0.0))
    total_income = phinance_analysis.get("total_income", 0.0)
    transaction_count = phinance_analysis.get("transaction_count", 0)

    net_savings = total_income - total_spent
    avg_transaction = -total_spent / transaction_count if transaction_count > 0 else 0.0

    date_range = phinance_analysis.get("date_range", {})
    num_months = 1
    if date_range.get("start") and date_range.get("end"):
        try:
            start = _parse_date(date_range["start"])
            end = _parse_date(date_range["end"])
            start_dt = datetime.strptime(start, "%Y-%m-%d")
            end_dt = datetime.strptime(end, "%Y-%m-%d")
            delta_days = (end_dt - start_dt).days
            num_months = max(1, (delta_days // 30) + 1)
        except (ValueError, TypeError):
            pass

    summary = {
        "totalincome": round(total_income, 2),
        "totalspending": round(total_spent, 2),
        "netsavings": round(net_savings, 2),
        "numtransactions": transaction_count,
        "avgtransaction": round(avg_transaction, 2),
        "nummonths": num_months,
    }

    by_category_raw = phinance_analysis.get("by_category", {})
    # Aggregate values when categories merge (e.g., "gas" + "transportation" -> "Transportation")
    by_category_aggregated = {}
    for cat, value in by_category_raw.items():
        normalized = _normalize_category(cat)
        by_category_aggregated[normalized] = (
            by_category_aggregated.get(normalized, 0.0) + value
        )
    categories = sorted(by_category_aggregated.keys())

    top_merchants = phinance_analysis.get("top_merchants", [])
    merchants = []
    for m in top_merchants:
        name = m.get("name", "") if isinstance(m, dict) else str(m)
        if len(name) > 40:
            name = name[:37] + "..."
        merchants.append(name)

    insights = phinance_analysis.get("insights", [])
    if isinstance(insights, str):
        insights = [s.strip() for s in insights.split("\n") if s.strip()]

    recommendations = phinance_analysis.get("recommendations", [])
    if isinstance(recommendations, str):
        recommendations = [s.strip() for s in recommendations.split("\n") if s.strip()]

    potential_savings = phinance_analysis.get("potential_savings", 0.0)

    return {
        "summary": summary,
        "categories": categories,
        "merchants": merchants,
        "by_category": {k: round(v, 2) for k, v in by_category_aggregated.items()},
        "top_merchants": top_merchants,
        "date_range": {
            "start": _parse_date(date_range.get("start", "")),
            "end": _parse_date(date_range.get("end", "")),
        },
        "insights": insights,
        "recommendations": recommendations,
        "potential_savings": round(potential_savings, 2),
    }


def convert_for_dashboard(
    transactions_path: str, analysis_path: str, output_dir: Optional[str] = None
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Convert phinance output files to dashboard format. Writes to output_dir if specified.
    Returns tuple of (dashboard_transactions, dashboard_analysis).
    """
    with open(transactions_path, "r") as f:
        raw_transactions = json.load(f)

    with open(analysis_path, "r") as f:
        raw_analysis = json.load(f)

    dashboard_transactions = convert_transactions(raw_transactions)
    dashboard_analysis = convert_analysis(raw_analysis, dashboard_transactions)

    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        with open(output_path / "transactions.json", "w") as f:
            json.dump(dashboard_transactions, f, indent=2)

        with open(output_path / "analysis.json", "w") as f:
            json.dump(dashboard_analysis, f, indent=2)

    return dashboard_transactions, dashboard_analysis


def generate_dashboard_json(
    phinance_output: Dict[str, Any], nemoagent=None
) -> Dict[str, Any]:
    """Legacy function for backward compatibility."""
    return convert_analysis(phinance_output)


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Convert phinance output to dashboard JSON format."
    )
    parser.add_argument("report_dir", help="Directory containing phinance output files")
    parser.add_argument(
        "-o", "--output", help="Output directory (default: input_dashboard)"
    )
    parser.add_argument(
        "--stdout", action="store_true", help="Print to stdout instead of files"
    )
    args = parser.parse_args()

    report_dir = Path(args.report_dir)
    transactions_path = report_dir / "transactions.json"
    analysis_path = report_dir / "analysis.json"

    if not transactions_path.exists():
        print(f"Error: {transactions_path} not found", file=sys.stderr)
        sys.exit(1)

    if not analysis_path.exists():
        print(f"Error: {analysis_path} not found", file=sys.stderr)
        sys.exit(1)

    output_dir = (
        None if args.stdout else (args.output or str(report_dir) + "_dashboard")
    )

    txns, analysis = convert_for_dashboard(
        str(transactions_path), str(analysis_path), output_dir
    )

    if args.stdout:
        print("=== transactions.json ===")
        print(json.dumps(txns, indent=2))
        print("\n=== analysis.json ===")
        print(json.dumps(analysis, indent=2))
    else:
        print(f"Converted files written to: {output_dir}")
        print(f"  - transactions.json ({len(txns['transactions'])} transactions)")
        print(f"  - analysis.json (summary + {len(analysis['insights'])} insights)")
