"""Phinance specialist adapter: builds structured JSON payloads for finance analysis."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional


@dataclass
class Transaction:
    date: str
    merchant: str
    amount: float
    category: Optional[str] = None
    description: Optional[str] = None


@dataclass
class PhinancePayload:
    currency: str
    transactions: List[Dict]
    user_request: str
    metadata: Dict


def build_phinance_payload(transactions_json: str, user_request_text: str) -> str:
    """Build structured JSON payload for Phinance finance specialist."""

    try:
        txn_data = json.loads(transactions_json)
    except json.JSONDecodeError as exc:
        raise ValueError("transactions_json must be valid JSON") from exc

    if not isinstance(txn_data, list):
        raise ValueError("transactions_json must be a list of transaction objects")

    if not user_request_text or not isinstance(user_request_text, str):
        raise ValueError("user_request_text must be a non-empty string")

    payload = PhinancePayload(
        currency="USD",
        transactions=txn_data,
        user_request=user_request_text,
        metadata={"version": "1.0"},
    )

    return json.dumps(asdict(payload), indent=2)
