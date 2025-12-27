"""Test script to verify Nemotron and Phinance models respond correctly."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.storage import init_db, insert_transactions, Transaction
from src.models import call_nemotron, call_phinance


async def test_models():
    """Insert mock transaction and verify both models respond."""
    print("Initializing database...")
    init_db()

    print("Inserting mock transaction...")
    mock_tx = Transaction(
        id=None,
        date="2025-12-23",
        description="Amazon AWS Monthly Bill",
        amount=150.00,
        category="Infrastructure",
        merchant="Amazon Web Services",
        user_id="test-user-1",
    )

    insert_transactions("test-user-1", [mock_tx])
    print(f"✓ Transaction inserted: {mock_tx.description}")

    print("\n=== Testing Nemotron (GPU 0) ===")
    nemotron_prompt = (
        "You are a helpful assistant. "
        "Respond briefly to: 'What services did I pay for this month?'"
    )
    nemotron_response = await call_nemotron(nemotron_prompt)
    print(f"Nemotron response: {nemotron_response}")

    print("\n=== Testing Phinance (GPU 1) ===")
    phinance_payload = """{
        "transactions": [
            {
                "date": "2025-12-23",
                "description": "Amazon AWS Monthly Bill",
                "amount": 150.00,
                "merchant": "Amazon Web Services"
            }
        ],
        "currency": "USD"
    }"""
    phinance_response = await call_phinance(phinance_payload)
    print(f"Phinance response: {phinance_response}")

    print("\n✓ Test complete. Both models are accessible.")


if __name__ == "__main__":
    asyncio.run(test_models())
