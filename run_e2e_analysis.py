#!/usr/bin/env python3
"""E2E Analysis Test: upload multiple PDFs, consent to analysis, wait for completion."""

import requests
import time
import os
import sys
import argparse
from pathlib import Path
from urllib.parse import urlparse, parse_qs

BASE_URL = "http://localhost:8080"
SOA1_API = "http://localhost:8001"


def upload_via_webui(pdf_path: Path) -> str:
    """Uploads a single PDF and returns the doc_id."""
    print(f"  Uploading {pdf_path.name}...")
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    with open(pdf_path, "rb") as f:
        files = {"file": (pdf_path.name, f, "application/pdf")}
        r = requests.post(
            f"{BASE_URL}/api/proxy/upload",
            files=files,
            allow_redirects=False,
            timeout=60,
        )

    loc = r.headers.get("Location")
    if loc:
        parsed = urlparse(loc)
        q = parse_qs(parsed.query)
        doc_vals = q.get("doc") or q.get("doc_id")
        if doc_vals:
            return doc_vals[0]

    if r.status_code == 200:
        try:
            data = r.json()
            doc_id = data.get("doc_id")
            if doc_id:
                return doc_id
            raise RuntimeError(f"JSON response missing doc_id: {data}")
        except requests.exceptions.JSONDecodeError:
            raise RuntimeError(
                f"Upload returned 200 but not valid JSON. Response: {r.text[:100]}..."
            )

    raise RuntimeError(f"Upload failed, status={r.status_code}")


def run_stage_ab(doc_id: str) -> dict:
    """Runs the extraction and pre-analysis stage."""
    r = requests.post(
        f"{BASE_URL}/analyze-stage-ab", json={"doc_id": doc_id}, timeout=180
    )
    r.raise_for_status()
    return r.json()


def grant_consent(doc_id: str) -> bool:
    """Grants consent for full analysis."""
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


def confirm_and_wait(doc_id: str, max_wait: int = 180) -> bool:
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
        time.sleep(5)
    print(f"Timeout waiting for {doc_id}")
    return False


def process_single_doc(pdf_path: Path) -> tuple:
    """Runs the full analysis flow for one document."""
    try:
        doc_id = upload_via_webui(pdf_path)
        run_stage_ab(doc_id)
        ok_consent = grant_consent(doc_id)
        if not ok_consent:
            return doc_id, False
        ok_analysis = confirm_and_wait(doc_id)
        return doc_id, ok_analysis
    except Exception as e:
        print(f"  CRITICAL ERROR during processing: {e}")
        return "N/A", False


def test_flow(pdf_paths: list[str]):
    """Runs the E2E flow for a list of PDF files."""
    n = len(pdf_paths)
    print(f"=== E2E Analysis Test: {n} document(s) ===")
    results = []

    for i, pdf_path_str in enumerate(pdf_paths):
        pdf_path = Path(pdf_path_str)
        print(f"\n[{i + 1}/{n}] Processing document: {pdf_path.name}")
        doc_id, ok = process_single_doc(pdf_path)
        print(f"  doc_id={doc_id} completed={ok}")
        results.append((pdf_path.name, ok))

    passed = sum(1 for _, ok in results if ok)
    print(
        f"\n=== Results: {passed}/{len(results)} documents processed successfully ==="
    )

    if passed != n:
        print("!!! E2E TEST FAILED: Not all documents processed successfully. !!!")
        return False

    print("=== E2E TEST PASSED ===")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run E2E analysis on a list of PDF files."
    )
    parser.add_argument(
        "pdf_files", nargs="+", help="List of absolute paths to PDF files."
    )
    args = parser.parse_args()

    print("Checking service health...")
    try:
        requests.get(f"{BASE_URL}/health", timeout=5).raise_for_status()
        requests.get(f"{SOA1_API}/health", timeout=5).raise_for_status()
        print("Services are healthy.")
    except Exception:
        print(
            "!!! CRITICAL: SOA-WebUI or SOA1 service is not running. Please start them before running the test. !!!"
        )
        sys.exit(1)

    success = test_flow(args.pdf_files)
    sys.exit(0 if success else 1)
