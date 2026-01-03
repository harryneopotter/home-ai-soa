import asyncio
import httpx
import json


async def test_batch_flow():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        try:
            resp = await client.get("/health")
            print(f"Health check: {resp.json()}")
        except Exception as e:
            print(f"Server not running? {e}")
            return

        print("Testing /upload-batch...")


if __name__ == "__main__":
    print("Test script ready. Run with server active.")
