import re
from typing import Dict, Optional, Tuple, List

MERCHANT_PATTERNS: List[Tuple[str, str, str]] = [
    (
        r"^AMZN\s*\*?.*|^AMAZON\.COM\s*\*?.*|^Amazon\s*Prime.*|^AMAZON MKTP.*",
        "Amazon",
        "Shopping",
    ),
    (r"^UBER\s*\*?\s*EATS.*", "Uber Eats", "Food & Dining"),
    (r"^UBER\s*\*?\s*TRIP.*|^UBER\s*\*?\s*BV.*", "Uber", "Transportation"),
    (r"^LYFT\s*\*?.*", "Lyft", "Transportation"),
    (r"^DOORDASH\s*\*?.*|^DD\s*\*?DOORDASH.*", "DoorDash", "Food & Dining"),
    (r"^GRUBHUB\s*\*?.*", "Grubhub", "Food & Dining"),
    (r"^TST\s*\*\s*(.+)", "\\1", "Food & Dining"),
    (r"^SQ\s*\*\s*(.+)", "\\1", "Shopping"),
    (r"^PAYPAL\s*\*\s*(.+)", "\\1 (PayPal)", "Shopping"),
    (r"^VENMO\s*\*?.*", "Venmo", "Transfer"),
    (r"^ZELLE\s*\*?.*", "Zelle", "Transfer"),
    (r"^APPLE\.COM/BILL.*|^APPLE\.COM/US.*", "Apple", "Subscriptions"),
    (r"^GOOGLE\s*\*?\s*PLAY.*|^GOOGLE\s*\*?\s*STORAGE.*", "Google", "Subscriptions"),
    (r"^NETFLIX\.COM.*|^NETFLIX\s*\*?.*", "Netflix", "Entertainment"),
    (r"^SPOTIFY.*", "Spotify", "Entertainment"),
    (r"^HULU.*", "Hulu", "Entertainment"),
    (r"^HBO\s*MAX.*|^HBOMAX.*", "HBO Max", "Entertainment"),
    (r"^DISNEY\s*PLUS.*|^DISNEYPLUS.*", "Disney+", "Entertainment"),
    (r"^PARAMOUNT\s*\+.*", "Paramount+", "Entertainment"),
    (r"^PEACOCK.*", "Peacock", "Entertainment"),
    (r"^WALMART\s*\*?.*|^WM\s+SUPERCENTER.*", "Walmart", "Shopping"),
    (r"^TARGET\s*\*?.*|^TARGET\s+\d+.*", "Target", "Shopping"),
    (r"^COSTCO\s*\*?.*|^COSTCO WHSE.*", "Costco", "Shopping"),
    (r"^WHOLE\s*FOODS.*|^WHOLEFDS.*", "Whole Foods", "Groceries"),
    (r"^TRADER\s*JOE.*", "Trader Joe's", "Groceries"),
    (r"^KROGER\s*\*?.*", "Kroger", "Groceries"),
    (r"^SAFEWAY\s*\*?.*", "Safeway", "Groceries"),
    (r"^PUBLIX\s*\*?.*", "Publix", "Groceries"),
    (r"^STARBUCKS\s*\*?.*|^STARBUCKS STORE.*", "Starbucks", "Food & Dining"),
    (r"^MCDONALDS\s*\*?.*|^MCDONALD'S.*", "McDonald's", "Food & Dining"),
    (r"^CHICK-FIL-A\s*\*?.*|^CHICKFILA.*", "Chick-fil-A", "Food & Dining"),
    (r"^CHIPOTLE\s*\*?.*", "Chipotle", "Food & Dining"),
    (r"^SHELL\s*OIL.*|^SHELL\s+SERVICE.*", "Shell", "Gas"),
    (r"^CHEVRON\s*\*?.*", "Chevron", "Gas"),
    (r"^EXXON\s*\*?.*|^EXXONMOBIL.*", "Exxon", "Gas"),
    (r"^BP\s*\*?.*|^BP\s+#\d+.*", "BP", "Gas"),
    (r"^CVS\s*\*?.*|^CVS/PHARM.*", "CVS", "Health"),
    (r"^WALGREENS\s*\*?.*", "Walgreens", "Health"),
    (r"^ATM\s*WITHDRAWAL.*|^ATM\s+.*", "ATM Withdrawal", "Cash"),
    (r"^CHECK\s*\d+.*", "Check", "Transfer"),
]

_compiled_patterns: List[Tuple[re.Pattern, str, str]] = [
    (re.compile(pattern, re.IGNORECASE), normalized, category)
    for pattern, normalized, category in MERCHANT_PATTERNS
]


def normalize_merchant(raw_name: str) -> Tuple[str, Optional[str], float]:
    if not raw_name:
        return ("Unknown", None, 0.0)

    raw_name = raw_name.strip()

    for pattern, normalized, category in _compiled_patterns:
        match = pattern.match(raw_name)
        if match:
            if "\\1" in normalized and match.groups():
                normalized = match.group(1).strip().title()
            return (normalized, category, 0.95)

    cleaned = re.sub(r"\s*#?\d+\s*$", "", raw_name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if cleaned != raw_name:
        return (cleaned.title(), None, 0.5)

    return (raw_name.title(), None, 0.3)


def normalize_transactions(transactions: List[Dict]) -> List[Dict]:
    for tx in transactions:
        raw_merchant = tx.get("merchant", "")
        normalized, suggested_cat, confidence = normalize_merchant(raw_merchant)

        tx["merchant_raw"] = raw_merchant
        tx["merchant"] = normalized
        tx["merchant_confidence"] = confidence

        if suggested_cat and not tx.get("category"):
            tx["category"] = suggested_cat
            tx["category_source"] = "merchant_normalizer"

    return transactions


def get_merchant_stats(transactions: List[Dict]) -> Dict[str, Dict]:
    stats = {
        "total": len(transactions),
        "high_confidence": 0,
        "medium_confidence": 0,
        "low_confidence": 0,
        "unique_raw": set(),
        "unique_normalized": set(),
    }

    for tx in transactions:
        confidence = tx.get("merchant_confidence", 0)
        if confidence >= 0.9:
            stats["high_confidence"] += 1
        elif confidence >= 0.5:
            stats["medium_confidence"] += 1
        else:
            stats["low_confidence"] += 1

        stats["unique_raw"].add(tx.get("merchant_raw", tx.get("merchant", "")))
        stats["unique_normalized"].add(tx.get("merchant", ""))

    stats["unique_raw"] = len(stats["unique_raw"])
    stats["unique_normalized"] = len(stats["unique_normalized"])
    stats["reduction_ratio"] = round(
        1 - (stats["unique_normalized"] / max(stats["unique_raw"], 1)), 2
    )

    return stats
