#!/usr/bin/env python3
"""
E2E Latency Test: 10 PDF Pipeline Test with Detailed Logging

Tests the complete finance pipeline with 10 PDFs, logging:
- Every prompt sent to LLM
- Every response received
- Input/output data at each stage
- Timestamps and latency for each operation

Run: python3 test_scripts/e2e_10pdf_latency_test.py
"""

import requests
import time
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

BASE_URL = "http://localhost:8080"
SOA1_API = "http://localhost:8001"
UPLOADS_DIR = Path("/home/ryzen/projects/home-ai/finance-agent/data/uploads")
LOG_DIR = Path("/home/ryzen/projects/test_logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

TEST_PDFS = [
    "finance-20251231-135146-d632a5_Apple Card Statement - April 2025.pdf",
    "finance-20251231-135155-d63f84_Apple Card Statement - August 2025.pdf",
    "finance-20251231-135208-d6fa74_Apple Card Statement - February 2025.pdf",
    "finance-20251231-135219-74f527_Apple Card Statement - January 2025.pdf",
    "finance-20251231-135229-0967fe_Apple Card Statement - July 2025.pdf",
    "finance-20251231-135238-e83b4c_Apple Card Statement - June 2025.pdf",
    "finance-20251231-135250-fa8020_Apple Card Statement - March 2025.pdf",
    "finance-20251231-135259-84fe14_Apple Card Statement - May 2025.pdf",
    "finance-20260101-172317-7e874f_Apple Card Statement - September 2025.pdf",
    "finance-20260101-172318-681950_Apple Card Statement - October 2025.pdf",
]


class LatencyLogger:
    def __init__(self, test_id: str):
        self.test_id = test_id
        self.log_file = LOG_DIR / f"e2e_latency_{test_id}.jsonl"
        self.summary_file = LOG_DIR / f"e2e_summary_{test_id}.json"
        self.events: List[Dict] = []
        self.start_time = time.time()

    def log(self, event_type: str, data: Dict[str, Any]):
        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "elapsed_ms": int((time.time() - self.start_time) * 1000),
            "event": event_type,
            **data,
        }
        self.events.append(event)
        with open(self.log_file, "a") as f:
            f.write(json.dumps(event) + "\n")
        return event

    def save_summary(self, summary: Dict):
        with open(self.summary_file, "w") as f:
            json.dump(summary, f, indent=2)


def ts():
    return datetime.utcnow().isoformat() + "Z"


def timed_request(
    method: str, url: str, logger: LatencyLogger, step_name: str, **kwargs
) -> tuple[Optional[requests.Response], float, Dict]:
    request_data = {
        "step": step_name,
        "method": method,
        "url": url,
    }
    if "json" in kwargs:
        request_data["request_payload"] = kwargs["json"]
    if "files" in kwargs:
        request_data["request_files"] = list(kwargs["files"].keys())

    logger.log(f"{step_name}_request", request_data)

    t0 = time.time()
    try:
        if method == "GET":
            resp = requests.get(url, timeout=kwargs.get("timeout", 300))
        elif method == "POST":
            resp = requests.post(url, **kwargs)
        else:
            raise ValueError(f"Unknown method: {method}")
        duration = time.time() - t0

        response_data = {
            "step": step_name,
            "status_code": resp.status_code,
            "duration_ms": int(duration * 1000),
        }
        try:
            response_data["response_body"] = resp.json()
        except:
            response_data["response_text"] = resp.text[:500]

        logger.log(f"{step_name}_response", response_data)
        return resp, duration, response_data

    except Exception as e:
        duration = time.time() - t0
        error_data = {
            "step": step_name,
            "error": str(e),
            "duration_ms": int(duration * 1000),
        }
        logger.log(f"{step_name}_error", error_data)
        return None, duration, error_data


def process_single_pdf(pdf_path: Path, pdf_index: int, logger: LatencyLogger) -> Dict:
    result = {
        "pdf_index": pdf_index,
        "pdf_name": pdf_path.name,
        "stages": {},
        "success": False,
        "total_duration_ms": 0,
    }
    pdf_start = time.time()

    print(f"\n{'=' * 60}")
    print(f"[{pdf_index + 1}/10] Processing: {pdf_path.name[:50]}...")
    print(f"{'=' * 60}")

    # Stage 1: Upload
    print("  📤 Uploading...")
    with open(pdf_path, "rb") as f:
        files = {"file": (pdf_path.name, f, "application/pdf")}
        resp, duration, data = timed_request(
            "POST",
            f"{SOA1_API}/upload-pdf",
            logger,
            f"pdf{pdf_index}_upload",
            files=files,
            timeout=120,
        )

    if not resp or resp.status_code != 200:
        result["stages"]["upload"] = {
            "success": False,
            "duration_ms": int(duration * 1000),
            "error": data.get("error"),
        }
        return result

    upload_data = resp.json()
    doc_id = upload_data.get("doc_id")
    result["doc_id"] = doc_id
    result["stages"]["upload"] = {
        "success": True,
        "duration_ms": int(duration * 1000),
        "doc_id": doc_id,
        "agent_response": upload_data.get("agent_response", "")[:200],
    }
    print(f"  ✅ Upload: {duration:.2f}s | doc_id={doc_id}")

    # Stage 2: Stage A/B (structure preview)
    print("  📋 Stage A/B preview...")
    resp, duration, data = timed_request(
        "POST",
        f"{BASE_URL}/analyze-stage-ab",
        logger,
        f"pdf{pdf_index}_stage_ab",
        json={"doc_id": doc_id},
        timeout=180,
    )

    if resp and resp.status_code == 200:
        ab_data = resp.json()
        result["stages"]["stage_ab"] = {
            "success": True,
            "duration_ms": int(duration * 1000),
            "institution": ab_data.get("institution"),
            "statement_type": ab_data.get("statement_type"),
        }
        print(f"  ✅ Stage A/B: {duration:.2f}s | {ab_data.get('institution')}")
    else:
        result["stages"]["stage_ab"] = {
            "success": False,
            "duration_ms": int(duration * 1000),
        }

    # Stage 3: Grant consent
    print("  🔐 Granting consent...")
    resp, duration, data = timed_request(
        "POST",
        f"{SOA1_API}/api/consent",
        logger,
        f"pdf{pdf_index}_consent",
        json={"doc_id": doc_id, "confirm": True, "specialist": "phinance"},
        timeout=30,
    )

    if resp and resp.status_code == 200:
        result["stages"]["consent"] = {
            "success": True,
            "duration_ms": int(duration * 1000),
        }
        print(f"  ✅ Consent: {duration:.2f}s")
    else:
        result["stages"]["consent"] = {
            "success": False,
            "duration_ms": int(duration * 1000),
        }

    # Stage 4: Confirm analysis and wait
    print("  🔍 Running analysis (hybrid pipeline)...")
    resp, duration, data = timed_request(
        "POST",
        f"{BASE_URL}/analyze-confirm",
        logger,
        f"pdf{pdf_index}_analyze_start",
        json={"doc_id": doc_id},
        timeout=30,
    )

    analysis_start = time.time()
    max_wait = 300
    poll_count = 0
    final_status = None

    while time.time() - analysis_start < max_wait:
        poll_count += 1
        resp, poll_duration, poll_data = timed_request(
            "GET",
            f"{BASE_URL}/analysis-status/{doc_id}",
            logger,
            f"pdf{pdf_index}_poll_{poll_count}",
            timeout=10,
        )

        if resp and resp.status_code == 200:
            status_data = resp.json()
            status = status_data.get("status")
            print(f"    Poll {poll_count}: {status} ({poll_duration:.2f}s)")

            if status == "completed":
                final_status = status_data
                break
            elif status == "failed":
                final_status = status_data
                break

        time.sleep(2)

    analysis_duration = time.time() - analysis_start

    if final_status and final_status.get("status") == "completed":
        result["stages"]["analysis"] = {
            "success": True,
            "duration_ms": int(analysis_duration * 1000),
            "poll_count": poll_count,
            "transaction_count": final_status.get("transaction_count", 0),
        }
        print(
            f"  ✅ Analysis: {analysis_duration:.2f}s | {final_status.get('transaction_count', 0)} transactions"
        )

        # Stage 5: Verify reports
        reports_dir = Path(
            f"/home/ryzen/projects/home-ai/finance-agent/data/reports/{doc_id}"
        )
        analysis_file = reports_dir / "analysis.json"

        if analysis_file.exists():
            with open(analysis_file) as f:
                analysis_json = json.load(f)

            hidden_drains = analysis_json.get("hidden_drains", [])
            result["stages"]["reports"] = {
                "success": True,
                "hidden_drains_count": len(hidden_drains),
                "total_spent": analysis_json.get("total_spent"),
                "insights_count": len(analysis_json.get("insights", [])),
            }
            print(
                f"  ✅ Reports: {len(hidden_drains)} hidden drains, ${analysis_json.get('total_spent', 0):.2f} total"
            )

            logger.log(
                f"pdf{pdf_index}_analysis_output",
                {
                    "doc_id": doc_id,
                    "total_spent": analysis_json.get("total_spent"),
                    "transaction_count": analysis_json.get("transaction_count"),
                    "categories": analysis_json.get("categories"),
                    "hidden_drains": hidden_drains,
                    "insights": analysis_json.get("insights"),
                    "recommendations": analysis_json.get("recommendations"),
                },
            )
        else:
            result["stages"]["reports"] = {
                "success": False,
                "error": "analysis.json not found",
            }

        result["success"] = True
    else:
        result["stages"]["analysis"] = {
            "success": False,
            "duration_ms": int(analysis_duration * 1000),
            "poll_count": poll_count,
            "error": final_status.get("error") if final_status else "timeout",
        }

    result["total_duration_ms"] = int((time.time() - pdf_start) * 1000)
    return result


def main():
    test_id = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    logger = LatencyLogger(test_id)

    print("\n" + "=" * 70)
    print("E2E LATENCY TEST: 10 PDF PIPELINE")
    print(f"Test ID: {test_id}")
    print(f"Log file: {logger.log_file}")
    print("=" * 70)

    # Check services
    print("\n🔍 Checking services...")
    try:
        resp = requests.get(f"{BASE_URL}/api/status", timeout=5)
        status = resp.json()
        print(f"  WebUI: {status.get('webui', {}).get('status')}")
        print(f"  SOA1: {status.get('soa1_api', {}).get('status')}")
        print(f"  Ollama: {status.get('ollama', {}).get('status')}")
    except Exception as e:
        print(f"  ❌ Service check failed: {e}")
        return

    logger.log(
        "test_start",
        {
            "test_id": test_id,
            "pdf_count": len(TEST_PDFS),
            "services_status": status,
        },
    )

    results = []
    test_start = time.time()

    for i, pdf_name in enumerate(TEST_PDFS):
        pdf_path = UPLOADS_DIR / pdf_name
        if not pdf_path.exists():
            print(f"\n⚠️  PDF not found: {pdf_name}")
            continue

        result = process_single_pdf(pdf_path, i, logger)
        results.append(result)

        logger.log(
            f"pdf{i}_complete",
            {
                "pdf_name": pdf_name,
                "success": result["success"],
                "total_duration_ms": result["total_duration_ms"],
            },
        )

    total_duration = time.time() - test_start

    # Summary
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    avg_upload = (
        sum(r["stages"].get("upload", {}).get("duration_ms", 0) for r in results)
        / len(results)
        if results
        else 0
    )
    avg_analysis = (
        sum(r["stages"].get("analysis", {}).get("duration_ms", 0) for r in results)
        / len(results)
        if results
        else 0
    )
    avg_total = (
        sum(r["total_duration_ms"] for r in results) / len(results) if results else 0
    )

    summary = {
        "test_id": test_id,
        "timestamp": ts(),
        "total_pdfs": len(TEST_PDFS),
        "successful": len(successful),
        "failed": len(failed),
        "total_duration_s": round(total_duration, 2),
        "avg_upload_ms": round(avg_upload),
        "avg_analysis_ms": round(avg_analysis),
        "avg_total_per_pdf_ms": round(avg_total),
        "results": results,
    }

    logger.log("test_complete", summary)
    logger.save_summary(summary)

    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"  Total PDFs:     {len(TEST_PDFS)}")
    print(f"  Successful:     {len(successful)}")
    print(f"  Failed:         {len(failed)}")
    print(f"  Total Duration: {total_duration:.2f}s")
    print(f"\n  Avg Upload:     {avg_upload:.0f}ms")
    print(f"  Avg Analysis:   {avg_analysis:.0f}ms")
    print(f"  Avg Per PDF:    {avg_total:.0f}ms ({avg_total / 1000:.2f}s)")
    print(f"\n  Log file:       {logger.log_file}")
    print(f"  Summary file:   {logger.summary_file}")
    print("=" * 70)

    if failed:
        print("\n❌ FAILED PDFs:")
        for r in failed:
            print(f"  - {r['pdf_name']}")

    return summary


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted")
        sys.exit(1)
