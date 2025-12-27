#!/usr/bin/env python3
"""Test SQLite persistence for transactions - verifies no re-parsing needed."""

import sys
import tempfile
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

_temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["FINANCE_DB_PATH"] = _temp_db.name

from src.storage import (
    init_db,
    save_transactions_for_doc,
    get_transactions_by_doc,
    has_transactions_for_doc,
)


def test_transaction_persistence():
    print("Initializing test database...")
    init_db()

    doc_id = "test-doc-001"

    assert not has_transactions_for_doc(doc_id), "Should have no transactions initially"
    print(f"✓ No transactions for {doc_id} initially")

    mock_transactions = [
        {
            "date": "2025-12-20",
            "description": "WHOLE FOODS MARKET #123",
            "amount": 127.43,
            "category": "groceries",
            "merchant": "Whole Foods",
        },
        {
            "date": "2025-12-21",
            "description": "SHELL OIL 123456",
            "amount": 45.00,
            "category": "gas",
            "merchant": "Shell",
        },
        {
            "date": "2025-12-22",
            "description": "NETFLIX.COM",
            "amount": 15.99,
            "category": "subscription",
            "merchant": "Netflix",
        },
    ]

    count = save_transactions_for_doc(doc_id, mock_transactions, user_id="test-user")
    print(f"✓ Saved {count} transactions for {doc_id}")

    assert has_transactions_for_doc(doc_id), "Should have transactions after save"
    print(f"✓ has_transactions_for_doc({doc_id}) = True")

    stored = get_transactions_by_doc(doc_id)
    assert len(stored) == 3, f"Expected 3 transactions, got {len(stored)}"
    print(f"✓ Retrieved {len(stored)} transactions from DB")

    assert stored[0]["merchant"] == "Whole Foods"
    assert stored[0]["amount"] == 127.43
    assert stored[0]["doc_id"] == doc_id
    print("✓ Transaction data integrity verified")

    if has_transactions_for_doc(doc_id):
        print(f"✓ Re-parse skipped: transactions already exist for {doc_id}")
        cached = get_transactions_by_doc(doc_id)
        print(f"  → Loaded {len(cached)} transactions from cache instead")

    print("\n✅ All persistence tests passed!")

    os.unlink(_temp_db.name)


if __name__ == "__main__":
    test_transaction_persistence()
