"""Simple seeding test for monitoring/report seeding endpoints.

This script is intentionally lightweight and runnable without pytest so it can be
used during quick demos.
"""

import requests
import sys

BASE = "http://localhost:8080"


def fail(msg: str):
    print("FAIL:", msg)
    sys.exit(1)


def main():
    try:
        r = requests.post(
            f"{BASE}/api/analysis/seed", params={"force": "true"}, timeout=10
        )
    except Exception as e:
        fail(f"Seed endpoint not reachable: {e}")

    if r.status_code != 200:
        fail(f"Seed endpoint returned {r.status_code}: {r.text}")

    print("Seed response:", r.json())

    # Check jobs
    r2 = requests.get(f"{BASE}/api/analysis/jobs", timeout=10)
    if r2.status_code != 200:
        fail(f"Jobs endpoint returned {r2.status_code}: {r2.text}")

    jobs = r2.json().get("jobs", [])
    if not jobs:
        fail("No jobs found after seeding")

    seeded = [j for j in jobs if j.get("seeded")]
    if not seeded:
        fail("No seeded jobs present in jobs response")

    print(f"Found {len(seeded)} seeded jobs (sample: {seeded[0].get('doc_id')})")

    # Check reports listing
    r3 = requests.get(f"{BASE}/api/reports", timeout=10)
    if r3.status_code != 200:
        fail(f"Reports endpoint returned {r3.status_code}: {r3.text}")

    reports = r3.json().get("reports", [])
    if not reports:
        fail("No reports returned by /api/reports")

    print(f"Reports count: {len(reports)} (sample: {reports[0].get('doc_id')})")

    # Attempt to fetch a report file
    sample = reports[0]["doc_id"]
    r4 = requests.get(f"{BASE}/reports/{sample}/dashboard/analysis.json", timeout=10)
    if r4.status_code != 200:
        fail(f"Failed to fetch report file: {r4.status_code} {r4.text}")

    print("Report file fetched OK")

    print("SEEDING TEST: PASS")


if __name__ == "__main__":
    main()
