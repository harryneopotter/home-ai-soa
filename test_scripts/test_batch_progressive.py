import asyncio
import httpx
import json
import os
from pathlib import Path

BASE_URL = "http://localhost:8001"
TEST_PDF = Path(
    "/home/ryzen/projects/home-ai/finance_agent/data/uploads/finance-20251231-135146-d632a5_Apple Card Statement - April 2025.pdf"
)


async def test_batch_progressive():
    async with httpx.AsyncClient(timeout=60.0) as client:
        print("--- Phase 1: Batch Upload ---")
        if not TEST_PDF.exists():
            print(f"Test PDF not found: {TEST_PDF}")
            return

        files = [
            ("files", (TEST_PDF.name, open(TEST_PDF, "rb"), "application/pdf")),
            (
                "files",
                ("Copy_" + TEST_PDF.name, open(TEST_PDF, "rb"), "application/pdf"),
            ),
        ]

        resp = await client.post(f"{BASE_URL}/upload-batch", files=files)
        if resp.status_code != 200:
            print(f"Upload failed: {resp.status_code} {resp.text}")
            return

        data = resp.json()
        batch_id = data.get("batch_id")
        print(f"Batch ID: {batch_id}")
        print(f"Agent Response: {data.get('agent_response')[:100]}...")

        print("\n--- Phase 2: Background Analysis ---")
        await asyncio.sleep(5)

        print("\n--- Phase 3: Grant Consent ---")
        resp = await client.post(
            f"{BASE_URL}/api/batch/consent?batch_id={batch_id}&action=analyze"
        )
        if resp.status_code != 200:
            print(f"Consent failed: {resp.status_code} {resp.text}")
            return

        data = resp.json()
        print(f"Status: {data.get('status')}")
        print(f"Preliminary Insights: {data.get('preliminary_insights')[:100]}...")

        print("\n--- Phase 4 & 5: Completion & Output ---")
        for _ in range(30):
            await asyncio.sleep(2)
            resp = await client.get(f"{BASE_URL}/api/output/{batch_id}/dashboard")
            if resp.status_code == 200:
                print("Dashboard output ready!")
                break
            elif resp.status_code == 404:
                print("Batch not found?")
                break
            else:
                print(f"Waiting for output... ({resp.status_code})")

        print("\n--- Test Complete ---")


if __name__ == "__main__":
    asyncio.run(test_batch_progressive())
