#!/usr/bin/env python3
"""Timed integration test: upload N PDFs, consent to analysis, log detailed timing."""

import requests
import time
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from datetime import datetime

BASE_URL = "http://localhost:8080"
SOA1_API = "http://localhost:8001"

UNIQUE_PDFS = [
    Path(
        "/home/ryzen/projects/home-ai/finance-agent/data/uploads/finance-20251224-153218-4de4ed_Apple Card Statement - September 2025.pdf"
    ),
    Path(
        "/home/ryzen/projects/home-ai/finance-agent/data/uploads/finance-20251224-153221-1ec3b8_Apple Card Statement - October 2025.pdf"
    ),
    Path(
        "/home/ryzen/projects/home-ai/finance-agent/data/uploads/finance-20251224-153223-32baec_Apple Card Statement - November 2025.pdf"
    ),
    Path(
        "/home/ryzen/projects/home-ai/finance-agent/data/uploads/finance-20251224-155339-e97168_Apple Card Statement - May 2025.pdf"
    ),
    Path(
        "/home/ryzen/projects/home-ai/finance-agent/data/uploads/finance-20251224-155341-01602f_Apple Card Statement - March 2025.pdf"
    ),
    Path(
        "/home/ryzen/projects/home-ai/finance-agent/data/uploads/finance-20251224-155336-1e780c_Apple Card Statement - November 2025.pdf"
    ),
]


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}] {msg}")


def upload_via_webui(pdf_path: Path) -> tuple[str, float]:
    start = time.time()
    with open(pdf_path, "rb") as f:
        files = {"file": (pdf_path.name, f, "application/pdf")}
        r = requests.post(
            f"{BASE_URL}/upload", files=files, allow_redirects=False, timeout=60
        )
    elapsed = time.time() - start
    loc = r.headers.get("Location")
    if not loc:
        raise RuntimeError(f"No redirect from upload, status={r.status_code}")
    parsed = urlparse(loc)
    q = parse_qs(parsed.query)
    doc_vals = q.get("doc") or q.get("doc_id")
    if not doc_vals:
        raise RuntimeError(f"No doc_id in redirect: {loc}")
    return doc_vals[0], elapsed


def run_stage_ab(doc_id: str) -> tuple[dict, float]:
    start = time.time()
    r = requests.post(
        f"{BASE_URL}/analyze-stage-ab", json={"doc_id": doc_id}, timeout=180
    )
    elapsed = time.time() - start
    r.raise_for_status()
    return r.json(), elapsed


def grant_consent(doc_id: str) -> tuple[bool, float]:
    start = time.time()
    r = requests.post(
        f"{SOA1_API}/api/consent",
        json={"doc_id": doc_id, "confirm": True, "specialist": "phinance"},
        timeout=30,
    )
    elapsed = time.time() - start
    if r.status_code != 200:
        return False, elapsed
    data = r.json()
    return data.get("confirmed", False), elapsed


def confirm_and_wait(doc_id: str, max_wait: int = 180) -> tuple[bool, float, dict]:
    start = time.time()
    r = requests.post(
        f"{BASE_URL}/analyze-confirm", json={"doc_id": doc_id}, timeout=10
    )
    r.raise_for_status()
    resp = r.json()
    if resp.get("status") not in ("started", "running"):
        return False, time.time() - start, resp

    while time.time() - start < max_wait:
        rr = requests.get(f"{BASE_URL}/analysis-status/{doc_id}", timeout=10)
        if rr.status_code == 404:
            time.sleep(1)
            continue
        rr.raise_for_status()
        st = rr.json()
        if st.get("status") == "completed":
            return True, time.time() - start, st
        if st.get("status") == "failed":
            return False, time.time() - start, st
        time.sleep(1)
    return False, time.time() - start, {"status": "timeout"}


def get_timing_details(doc_id: str) -> dict:
    try:
        r = requests.get(f"{BASE_URL}/analysis-timing/{doc_id}", timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}


def process_single_doc(pdf_path: Path, index: int) -> dict:
    result = {
        "index": index,
        "pdf_name": pdf_path.name,
        "success": False,
        "timings": {},
        "transaction_count": 0,
        "total_spent": 0,
        "error": None,
    }

    try:
        log(f"[{index}] Uploading {pdf_path.name}...")
        doc_id, upload_time = upload_via_webui(pdf_path)
        result["doc_id"] = doc_id
        result["timings"]["upload"] = upload_time
        log(f"[{index}] Upload complete: doc_id={doc_id} ({upload_time:.2f}s)")

        log(f"[{index}] Running stage-ab...")
        stage_ab_result, stage_ab_time = run_stage_ab(doc_id)
        result["timings"]["stage_ab"] = stage_ab_time
        result["institution"] = stage_ab_result.get("institution", "unknown")
        log(f"[{index}] Stage-AB complete ({stage_ab_time:.2f}s)")

        log(f"[{index}] Granting consent...")
        consent_ok, consent_time = grant_consent(doc_id)
        result["timings"]["consent"] = consent_time
        if not consent_ok:
            result["error"] = "Consent failed"
            return result
        log(f"[{index}] Consent granted ({consent_time:.2f}s)")

        log(f"[{index}] Running analysis...")
        analysis_ok, analysis_time, analysis_result = confirm_and_wait(doc_id)
        result["timings"]["analysis"] = analysis_time

        if analysis_ok:
            result["success"] = True
            result["transaction_count"] = analysis_result.get("transaction_count", 0)
            result["total_spent"] = analysis_result.get("total_spent", 0)

            timing_details = get_timing_details(doc_id)
            if timing_details.get("timings"):
                result["step_timings"] = timing_details["timings"]

            log(
                f"[{index}] Analysis complete ({analysis_time:.2f}s) - {result['transaction_count']} transactions, ${result['total_spent']:.2f}"
            )
        else:
            result["error"] = (
                f"Analysis failed: {analysis_result.get('status', 'unknown')}"
            )
            log(f"[{index}] Analysis FAILED ({analysis_time:.2f}s)")

    except Exception as e:
        result["error"] = str(e)
        log(f"[{index}] ERROR: {e}")

    return result


def run_test(n: int):
    log(f"========== STARTING TEST: {n} PDF(s) ==========")
    log(f"Base URL: {BASE_URL}")
    log(f"SOA1 API: {SOA1_API}")

    pdfs_to_use = UNIQUE_PDFS[:n]
    if len(pdfs_to_use) < n:
        log(f"WARNING: Only {len(pdfs_to_use)} unique PDFs available, cycling...")
        while len(pdfs_to_use) < n:
            pdfs_to_use.append(UNIQUE_PDFS[len(pdfs_to_use) % len(UNIQUE_PDFS)])

    log(f"PDFs to process: {[p.name for p in pdfs_to_use]}")

    total_start = time.time()
    results = []

    for i, pdf_path in enumerate(pdfs_to_use, 1):
        log(f"\n----- Document {i}/{n} -----")
        result = process_single_doc(pdf_path, i)
        results.append(result)

        if not result["success"]:
            log(f"Document {i} failed, continuing with remaining...")

    total_elapsed = time.time() - total_start

    log("\n========== TEST RESULTS ==========")
    log(f"Total time: {total_elapsed:.2f}s")
    log(f"Average per document: {total_elapsed / n:.2f}s")

    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    log(f"\nSuccess: {len(successful)}/{n}")
    if failed:
        log(f"Failed: {len(failed)}/{n}")
        for r in failed:
            log(f"  - {r['pdf_name']}: {r.get('error', 'unknown error')}")

    total_transactions = sum(r.get("transaction_count", 0) for r in successful)
    total_spent = sum(r.get("total_spent", 0) for r in successful)
    log(f"\nTotal transactions extracted: {total_transactions}")
    log(f"Total spending tracked: ${total_spent:.2f}")

    log("\n----- Timing Breakdown -----")
    for r in results:
        status = "✅" if r["success"] else "❌"
        timings = r.get("timings", {})
        total_doc_time = sum(timings.values())
        log(f"{status} [{r['index']}] {r['pdf_name'][:40]}...")
        log(
            f"    Upload: {timings.get('upload', 0):.2f}s | Stage-AB: {timings.get('stage_ab', 0):.2f}s | Consent: {timings.get('consent', 0):.2f}s | Analysis: {timings.get('analysis', 0):.2f}s | Total: {total_doc_time:.2f}s"
        )

        if r.get("step_timings"):
            steps = r["step_timings"]
            step_str = " | ".join([f"{k}: {v:.2f}s" for k, v in steps.items()])
            log(f"    Pipeline steps: {step_str}")

    log("\n----- Aggregate Timing -----")
    if successful:
        avg_upload = sum(r["timings"].get("upload", 0) for r in successful) / len(
            successful
        )
        avg_stage_ab = sum(r["timings"].get("stage_ab", 0) for r in successful) / len(
            successful
        )
        avg_analysis = sum(r["timings"].get("analysis", 0) for r in successful) / len(
            successful
        )
        log(f"Avg upload: {avg_upload:.2f}s")
        log(f"Avg stage-ab: {avg_stage_ab:.2f}s")
        log(f"Avg analysis: {avg_analysis:.2f}s")

    log("\n========== TEST COMPLETE ==========")
    return len(successful) == n


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    success = run_test(n)
    sys.exit(0 if success else 1)
