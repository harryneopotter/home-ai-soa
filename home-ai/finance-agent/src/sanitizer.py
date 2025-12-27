"""Sanitize and validate Phinance JSON output before persistence."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

VALID_CATEGORIES = {
    "dining",
    "groceries",
    "shopping",
    "transportation",
    "entertainment",
    "utilities",
    "healthcare",
    "travel",
    "subscriptions",
    "services",
    "gas",
    "education",
    "personal",
    "home",
    "gifts",
    "fees",
    "other",
    "unknown",
}

# Merchant name patterns to strip (cashback %, addresses, phone numbers)
MERCHANT_CLEANUP_PATTERNS = [
    r"\s+\d+%\s+\$[\d.]+$",  # " 1% $0.26" at end
    r"\s+\d{5}(?:-\d{4})?(?:\s*[A-Z]{2})?\s*(?:USA|CHE|GBR|CAN|MEX)?\s*$",  # " 95014 CA USA" or "60013-2995IL"
    r"\s+\d{4,5}(?:\s+[A-Z]{2})?(?:\s+CHE)?$",  # " 8060 ZH CHE"
    r"\s+\d{3}-\d{3}-\d{4}$",  # phone " 800-334-7661"
    r"\s+\d{3,4}-\d{7,}$",  # phone " 0091-18001025110037"
    r"\s+\d{10,}$",  # phone " 8009256278"
    r"\s+[A-Z]{6}$",  # " CHECHE" country codes doubled
    r"\s+[A-Z]{2}\s+CAN$",  # " ON CAN"
    r"\s+Amzn\.co.*$",  # Amazon suffixes
]

# Merchant categorization rules (keyword -> category)
MERCHANT_CATEGORY_RULES = {
    # Dining/Food
    "starbucks": "dining",
    "mcdonald": "dining",
    "chipotle": "dining",
    "dunkin": "dining",
    "coffee": "dining",
    "restaurant": "dining",
    "cafe": "dining",
    "pizza": "dining",
    "burger": "dining",
    "taco": "dining",
    "sushi": "dining",
    "bakery": "dining",
    "deli": "dining",
    "grill": "dining",
    "kitchen": "dining",
    "bistro": "dining",
    "eatery": "dining",
    "food": "dining",
    "takeaway": "dining",
    "take away": "dining",
    # Groceries
    "walmart": "groceries",
    "target": "groceries",
    "costco": "groceries",
    "kroger": "groceries",
    "safeway": "groceries",
    "whole foods": "groceries",
    "trader joe": "groceries",
    "aldi": "groceries",
    "publix": "groceries",
    "grocery": "groceries",
    "supermarket": "groceries",
    "market": "groceries",
    # Shopping
    "amazon": "shopping",
    "ebay": "shopping",
    "best buy": "shopping",
    "home depot": "shopping",
    "lowes": "shopping",
    "ikea": "shopping",
    "macy": "shopping",
    "nordstrom": "shopping",
    "gap": "shopping",
    "old navy": "shopping",
    "nike": "shopping",
    "adidas": "shopping",
    "hudson": "shopping",
    "spirit of": "shopping",
    "confiserie": "shopping",
    # Transportation
    "uber": "transportation",
    "lyft": "transportation",
    "taxi": "transportation",
    "cab": "transportation",
    "metro": "transportation",
    "transit": "transportation",
    "parking": "transportation",
    "toll": "transportation",
    # Gas
    "shell": "gas",
    "chevron": "gas",
    "exxon": "gas",
    "mobil": "gas",
    "bp ": "gas",
    "texaco": "gas",
    "76 ": "gas",
    "gas station": "gas",
    "fuel": "gas",
    # Travel
    "hotel": "travel",
    "marriott": "travel",
    "hilton": "travel",
    "hyatt": "travel",
    "airbnb": "travel",
    "airline": "travel",
    "united air": "travel",
    "delta air": "travel",
    "american air": "travel",
    "southwest": "travel",
    "lufthan": "travel",
    "pullman": "travel",
    "novotel": "travel",
    "flughafen": "travel",
    "airport": "travel",
    "airside": "travel",
    # Subscriptions
    "netflix": "subscriptions",
    "spotify": "subscriptions",
    "hulu": "subscriptions",
    "disney+": "subscriptions",
    "apple.com/bill": "subscriptions",
    "google *": "subscriptions",
    "youtube": "subscriptions",
    "hbo": "subscriptions",
    "prime video": "subscriptions",
    "icloud": "subscriptions",
    # Utilities
    "electric": "utilities",
    "water": "utilities",
    "gas bill": "utilities",
    "internet": "utilities",
    "comcast": "utilities",
    "at&t": "utilities",
    "verizon": "utilities",
    "t-mobile": "utilities",
    # Healthcare
    "pharmacy": "healthcare",
    "cvs": "healthcare",
    "walgreens": "healthcare",
    "hospital": "healthcare",
    "medical": "healthcare",
    "doctor": "healthcare",
    "clinic": "healthcare",
    "dental": "healthcare",
    # Entertainment
    "movie": "entertainment",
    "cinema": "entertainment",
    "theater": "entertainment",
    "concert": "entertainment",
    "ticket": "entertainment",
    "game": "entertainment",
    "steam": "entertainment",
    "playstation": "entertainment",
    "xbox": "entertainment",
    "nintendo": "entertainment",
    # Travel (additional)
    "westjet": "travel",
    "westin": "travel",
    "hampton inn": "travel",
    "enterprise rent": "transportation",
    "hertz": "transportation",
    "avis": "transportation",
    "rental car": "transportation",
    "rent-a-car": "transportation",
    # Utilities (additional)
    "comed": "utilities",
    "nicor": "utilities",
    "peoples gas": "utilities",
    "xfinity": "utilities",
    "spectrum": "utilities",
    # Groceries (additional)
    "butera": "groceries",
    "jewel": "groceries",
    "mariano": "groceries",
    "hy-vee": "groceries",
    "wegmans": "groceries",
    "fresh": "groceries",
    "bombay mart": "groceries",
    # Services
    "groot": "services",
    "waste": "services",
    "lawn": "services",
    "cleaning": "services",
    "repair": "services",
    # Dining (additional)
    "flavors of ind": "dining",
    "indian": "dining",
    "thai": "dining",
    "chinese": "dining",
    "mexican": "dining",
    "italian": "dining",
}


@dataclass
class SanitizationResult:
    success: bool
    data: Optional[Dict[str, Any]]
    errors: List[str]


def clean_merchant_name(raw_merchant: str) -> str:
    cleaned = raw_merchant.strip()
    for pattern in MERCHANT_CLEANUP_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:80] if cleaned else raw_merchant[:80]


def categorize_merchant(merchant: str) -> str:
    merchant_lower = merchant.lower()
    for keyword, category in MERCHANT_CATEGORY_RULES.items():
        if keyword in merchant_lower:
            return category
    return "other"


def build_analysis_from_transactions(
    transactions: List[Dict[str, Any]],
    doc_id: str,
) -> Dict[str, Any]:
    if not transactions:
        return {
            "doc_id": doc_id,
            "currency": "USD",
            "transaction_count": 0,
            "total_spent": 0.0,
            "by_category": {},
            "top_merchants": [],
            "date_range": None,
        }

    total_spent = 0.0
    by_category: Dict[str, float] = {}
    merchant_totals: Dict[str, float] = {}
    dates: List[str] = []

    for tx in transactions:
        amount = tx.get("amount", 0)
        if isinstance(amount, (int, float)) and amount > 0:
            total_spent += amount

        category = tx.get("category", "other")
        by_category[category] = by_category.get(category, 0) + abs(amount)

        merchant = tx.get("merchant", "Unknown")
        merchant_totals[merchant] = merchant_totals.get(merchant, 0) + abs(amount)

        if tx.get("date"):
            dates.append(tx["date"])

    sorted_merchants = sorted(
        merchant_totals.items(), key=lambda x: x[1], reverse=True
    )[:10]
    top_merchants = [
        {"name": name, "total": round(total, 2)} for name, total in sorted_merchants
    ]

    sorted_categories = sorted(by_category.items(), key=lambda x: x[1], reverse=True)
    by_category_rounded = {cat: round(amt, 2) for cat, amt in sorted_categories}

    date_range = None
    if dates:
        date_range = {"start": min(dates), "end": max(dates)}

    return {
        "doc_id": doc_id,
        "currency": "USD",
        "transaction_count": len(transactions),
        "total_spent": round(total_spent, 2),
        "by_category": by_category_rounded,
        "top_merchants": top_merchants,
        "date_range": date_range,
    }


def strip_json_comments(raw: str) -> str:
    raw = re.sub(r"//[^\n]*", "", raw)
    raw = re.sub(r"/\*.*?\*/", "", raw, flags=re.DOTALL)
    raw = re.sub(r",(\s*[\]}])", r"\1", raw)
    raw = re.sub(r'"\s*\n\s*"', '",\n"', raw)
    raw = re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", raw)
    return raw


def extract_json_from_response(raw: str) -> Optional[str]:
    raw = strip_json_comments(raw)

    fences = ["```json", "```"]
    for fence in fences:
        if fence in raw:
            parts = raw.split(fence)
            if len(parts) >= 2:
                raw = parts[1].split("```")[0] if "```" in parts[1] else parts[1]
                break

    raw = raw.strip()

    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start_idx = raw.find(start_char)
        if start_idx != -1:
            depth = 0
            for i, char in enumerate(raw[start_idx:], start_idx):
                if char == start_char:
                    depth += 1
                elif char == end_char:
                    depth -= 1
                    if depth == 0:
                        return raw[start_idx : i + 1]

    return raw if raw else None


def validate_date(date_str: str) -> bool:
    patterns = [
        "%m/%d/%Y",
        "%m/%d/%y",
        "%Y-%m-%d",
        "%m/%d",
    ]
    for pattern in patterns:
        try:
            datetime.strptime(date_str, pattern)
            return True
        except ValueError:
            continue
    return False


def validate_amount(amount: Any) -> Tuple[bool, Optional[float]]:
    if isinstance(amount, (int, float)):
        return True, float(amount)

    if isinstance(amount, str):
        cleaned = amount.replace("$", "").replace(",", "").strip()
        try:
            return True, float(cleaned)
        except ValueError:
            return False, None

    return False, None


def normalize_category(category: Optional[str]) -> str:
    if not category:
        return "unknown"

    normalized = category.lower().strip()

    aliases = {
        "food": "dining",
        "restaurant": "dining",
        "restaurants": "dining",
        "food & drink": "dining",
        "grocery": "groceries",
        "supermarket": "groceries",
        "transport": "transportation",
        "transit": "transportation",
        "uber": "transportation",
        "lyft": "transportation",
        "subscription": "subscriptions",
        "streaming": "subscriptions",
        "netflix": "subscriptions",
        "spotify": "subscriptions",
        "retail": "shopping",
        "amazon": "shopping",
        "health": "healthcare",
        "medical": "healthcare",
        "pharmacy": "healthcare",
        "hotel": "travel",
        "flight": "travel",
        "airline": "travel",
        "fuel": "gas",
        "gasoline": "gas",
        "electric": "utilities",
        "water": "utilities",
        "internet": "utilities",
        "phone": "utilities",
    }

    if normalized in aliases:
        return aliases[normalized]

    if normalized in VALID_CATEGORIES:
        return normalized

    return "other"


def sanitize_transaction(
    tx: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    errors = []
    sanitized = {}

    date = tx.get("date")
    if not date:
        errors.append("Missing date field")
    elif not validate_date(str(date)):
        errors.append(f"Invalid date format: {date}")
    else:
        sanitized["date"] = str(date)

    merchant = tx.get("merchant") or tx.get("description") or tx.get("name")
    if not merchant:
        errors.append("Missing merchant/description field")
    else:
        sanitized["merchant"] = str(merchant).strip()[:100]

    amount = tx.get("amount")
    if amount is None:
        errors.append("Missing amount field")
    else:
        valid, parsed = validate_amount(amount)
        if not valid:
            errors.append(f"Invalid amount: {amount}")
        else:
            sanitized["amount"] = parsed
            sanitized["currency"] = "USD"

    category = tx.get("category")
    sanitized["category"] = normalize_category(category)

    if tx.get("description") and tx.get("merchant"):
        sanitized["description"] = str(tx["description"]).strip()[:200]

    if errors:
        return None, errors

    return sanitized, []


def sanitize_analysis(
    analysis: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    errors = []
    sanitized = {}

    if "total_spent" in analysis or "total" in analysis:
        total = analysis.get("total_spent") or analysis.get("total")
        valid, parsed = validate_amount(total)
        if valid:
            sanitized["total_spent"] = parsed
            sanitized["currency"] = "USD"

    if "by_category" in analysis:
        by_cat = analysis["by_category"]
        if isinstance(by_cat, dict):
            sanitized["by_category"] = {}
            for cat, amt in by_cat.items():
                valid, parsed = validate_amount(amt)
                if valid:
                    sanitized["by_category"][normalize_category(cat)] = parsed

    if "recurring" in analysis:
        recurring = analysis["recurring"]
        if isinstance(recurring, list):
            sanitized["recurring"] = [str(r)[:50] for r in recurring[:20]]

    if "insights" in analysis or "investment" in analysis:
        insights = analysis.get("insights") or analysis.get("investment")
        if isinstance(insights, list):
            sanitized["insights"] = [str(i)[:200] for i in insights[:10]]
        elif isinstance(insights, str):
            sanitized["insights"] = [insights[:200]]

    if (
        "recommendations" in analysis
        or "suggestions" in analysis
        or "advice" in analysis
    ):
        recs = (
            analysis.get("recommendations")
            or analysis.get("suggestions")
            or analysis.get("advice")
        )
        if isinstance(recs, list):
            sanitized["recommendations"] = [str(r)[:200] for r in recs[:10]]
        elif isinstance(recs, str):
            sanitized["recommendations"] = [recs[:200]]

    if "potential_savings" in analysis:
        valid, parsed = validate_amount(analysis["potential_savings"])
        if valid:
            sanitized["potential_savings"] = parsed

    if "top_merchants" in analysis:
        top = analysis["top_merchants"]
        if isinstance(top, list):
            sanitized["top_merchants"] = top[:10]

    return sanitized, errors


def repair_json_string(json_str: str) -> str:
    json_str = strip_json_comments(json_str)
    json_str = re.sub(r"\(\s*This[^)]*\)", "", json_str)
    json_str = re.sub(r"\([^)]{0,100}\)", "", json_str)
    json_str = re.sub(r'"\s*,\s*,\s*"', '", "', json_str)
    json_str = re.sub(r'"\s+(?=[,\]}])', '"', json_str)
    return json_str


def sanitize_phinance_response(raw_response: str) -> SanitizationResult:
    if not raw_response or not raw_response.strip():
        return SanitizationResult(
            success=False, data=None, errors=["Empty Phinance response"]
        )

    json_str = extract_json_from_response(raw_response)
    if not json_str:
        return SanitizationResult(
            success=False, data=None, errors=["Could not extract JSON from response"]
        )

    json_str = repair_json_string(json_str)

    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as e:
        return SanitizationResult(
            success=False, data=None, errors=[f"Invalid JSON: {str(e)}"]
        )

    result = {"transactions": [], "analysis": {}, "raw_valid": True}
    all_errors = []

    if isinstance(parsed, list):
        for i, tx in enumerate(parsed):
            if isinstance(tx, dict):
                sanitized, errors = sanitize_transaction(tx)
                if sanitized:
                    result["transactions"].append(sanitized)
                if errors:
                    all_errors.extend([f"Transaction {i}: {e}" for e in errors])

    elif isinstance(parsed, dict):
        if "transactions" in parsed:
            for i, tx in enumerate(parsed["transactions"]):
                if isinstance(tx, dict):
                    sanitized, errors = sanitize_transaction(tx)
                    if sanitized:
                        result["transactions"].append(sanitized)
                    if errors:
                        all_errors.extend([f"Transaction {i}: {e}" for e in errors])

        analysis_fields = [
            "total_spent",
            "total",
            "by_category",
            "recurring",
            "insights",
            "recommendations",
            "potential_savings",
            "top_merchants",
            "summary",
        ]
        if any(f in parsed for f in analysis_fields):
            sanitized_analysis, analysis_errors = sanitize_analysis(parsed)
            result["analysis"] = sanitized_analysis
            all_errors.extend(analysis_errors)

        if "summary" in parsed:
            result["analysis"]["summary"] = str(parsed["summary"])[:500]

    if not result["transactions"] and not result["analysis"]:
        return SanitizationResult(
            success=False,
            data=None,
            errors=all_errors or ["No valid data extracted from Phinance response"],
        )

    return SanitizationResult(success=True, data=result, errors=all_errors)


__all__ = [
    "sanitize_phinance_response",
    "sanitize_transaction",
    "SanitizationResult",
    "VALID_CATEGORIES",
    "clean_merchant_name",
    "categorize_merchant",
    "build_analysis_from_transactions",
]
