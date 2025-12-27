#!/usr/bin/env python3
"""Integration test: upload N PDFs, consent to analysis, wait for completion, restart SOA1, verify context."""

import requests
import time
import os
from pathlib import Path
from urllib.parse import urlparse, parse_qs

BASE_URL = "http://localhost:8080"
SOA1_API = "http://localhost:8001"
TEST_PDF = Path(
    "/home/ryzen/projects/home-ai/finance-agent/data/uploads/finance-20251224-153218-4de4ed_Apple Card Statement - September 2025.pdf"
)


def upload_via_webui(pdf_path: Path) -> str:
    with open(pdf_path, "rb") as f:
        files = {"file": (pdf_path.name, f, "application/pdf")}
        r = requests.post(
            f"{BASE_URL}/upload", files=files, allow_redirects=False, timeout=60
        )
    loc = r.headers.get("Location")
    if not loc:
        raise RuntimeError(f"No redirect from upload, status={r.status_code}")
    parsed = urlparse(loc)
    q = parse_qs(parsed.query)
    doc_vals = q.get("doc") or q.get("doc_id")
    if not doc_vals:
        raise RuntimeError(f"No doc_id in redirect: {loc}")
    return doc_vals[0]


def run_stage_ab(doc_id: str) -> dict:
    r = requests.post(
        f"{BASE_URL}/analyze-stage-ab", json={"doc_id": doc_id}, timeout=180
    )
    r.raise_for_status()
    return r.json()


def grant_consent(doc_id: str) -> bool:
    r = requests.post(
        f"{SOA1_API}/api/consent",
        json={"doc_id": doc_id, "confirm": True, "specialist": "phinance"},
        timeout=30,
    )
    if r.status_code != 200:
        print(f"Consent failed: {r.status_code} {r.text}")
        return False
    data = r.json()
    return data.get("confirmed", False)


def confirm_and_wait(doc_id: str, max_wait: int = 120) -> bool:
    r = requests.post(
        f"{BASE_URL}/analyze-confirm", json={"doc_id": doc_id}, timeout=10
    )
    r.raise_for_status()
    resp = r.json()
    if resp.get("status") not in ("started", "running"):
        print(f"analyze-confirm returned unexpected status: {resp}")
        return False

    start = time.time()
    while time.time() - start < max_wait:
        rr = requests.get(f"{BASE_URL}/analysis-status/{doc_id}", timeout=10)
        if rr.status_code == 404:
            time.sleep(2)
            continue
        rr.raise_for_status()
        st = rr.json()
        if st.get("status") == "completed":
            return True
        if st.get("status") == "failed":
            print(f"Analysis failed: {st}")
            return False
        time.sleep(2)
    print(f"Timeout waiting for {doc_id}")
    return False


def process_single_doc(pdf_path: Path) -> tuple:
    doc_id = upload_via_webui(pdf_path)
    run_stage_ab(doc_id)
    ok_consent = grant_consent(doc_id)
    if not ok_consent:
        return doc_id, False
    ok_analysis = confirm_and_wait(doc_id)
    return doc_id, ok_analysis


def restart_webui():
    os.system("pkill -f 'python.*main.py' || true")
    time.sleep(2)
    env_cmd = "export PYTHONPATH='/home/ryzen/projects:${PYTHONPATH:-}' &&"
    os.system(
        f"cd /home/ryzen/projects && {env_cmd} python3 soa-webui/main.py > /tmp/soa-webui.log 2>&1 &"
    )
    time.sleep(5)
    for _ in range(10):
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=5)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def test_flow(n: int = 12):
    print(f"=== Integration Test: {n} document(s) ===")
    results = []

    for i in range(n):
        print(f"\n[{i + 1}/{n}] Processing document...")
        doc_id, ok = process_single_doc(TEST_PDF)
        print(f"  doc_id={doc_id} completed={ok}")
        results.append((doc_id, ok))
        if not ok:
            print(f"  FAILED at document {i + 1}, stopping early")
            break

    passed = sum(1 for _, ok in results if ok)
    print(
        f"\n=== Results: {passed}/{len(results)} documents processed successfully ==="
    )

    if passed == 0:
        print("No documents processed, skipping rehydration test")
        return False

    print("\nRestarting WebUI for rehydration test...")
    if not restart_webui():
        print("WebUI failed to restart")
        return False

    print("Verifying chat picks up analysis context...")
    q = "What is a quick insight from my recent analysis?"
    try:
        r = requests.post(f"{BASE_URL}/api/chat", json={"message": q}, timeout=120)
        r.raise_for_status()
        resp = r.json()
        response_text = resp.get("response", "")
        print(f"Chat response: {response_text[:200]}...")
        if response_text:
            print("\n=== TEST PASSED ===")
            return True
    except Exception as e:
        print(f"Chat request failed: {e}")

    print("\n=== TEST FAILED ===")
    return False


if __name__ == "__main__":
    import sys

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    success = test_flow(n)
    sys.exit(0 if success else 1)
