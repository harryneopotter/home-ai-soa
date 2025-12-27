#!/usr/bin/env python3
"""
Multi-PDF Integration Test with Comprehensive Timing and Logging
Tests N PDFs sequentially, capturing detailed metrics for each.
"""

import requests
import time
import json
import sys
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

# Configuration
WEBUI_URL = "http://localhost:8080"
SOA1_API_URL = "http://localhost:8001"
TEST_PDF_DIR = Path("/home/ryzen/projects/home-ai/finance-agent/data/uploads")
LOG_DIR = Path("/home/ryzen/projects/test_logs")
NUM_PDFS = 4  # Number of PDFs to test


@dataclass
class StepTiming:
    step: str
    start_time: float = 0
    end_time: float = 0
    duration_ms: float = 0
    success: bool = True
    error: Optional[str] = None


@dataclass
class PDFTestResult:
    pdf_name: str
    doc_id: str = ""
    total_duration_ms: float = 0
    steps: List[StepTiming] = field(default_factory=list)
    transaction_count: int = 0
    anomaly_count: int = 0
    analysis_timing: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None


def log(msg: str):
    """Print timestamped log message."""
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}] {msg}")


def time_step(name: str) -> StepTiming:
    """Create a timing step."""
    return StepTiming(step=name, start_time=time.time())


def complete_step(step: StepTiming, success: bool = True, error: str = None):
    """Complete a timing step."""
    step.end_time = time.time()
    step.duration_ms = (step.end_time - step.start_time) * 1000
    step.success = success
    step.error = error
    return step


def upload_pdf(pdf_path: Path) -> tuple[str, StepTiming]:
    """Upload a PDF and return doc_id."""
    step = time_step("upload")
    try:
        with open(pdf_path, "rb") as f:
            files = {"file": (pdf_path.name, f, "application/pdf")}
            resp = requests.post(
                f"{WEBUI_URL}/upload", files=files, allow_redirects=False, timeout=30
            )

        # Upload returns 303 redirect with doc_id in Location header
        if resp.status_code == 303:
            location = resp.headers.get("Location", "")
            # Parse doc_id from: /?upload=success&doc={doc_id}
            import re

            match = re.search(r"doc=([^&]+)", location)
            if match:
                doc_id = match.group(1)
                complete_step(step)
                return doc_id, step

        complete_step(
            step, success=False, error=f"Unexpected status {resp.status_code}"
        )
        return "", step
    except Exception as e:
        complete_step(step, success=False, error=str(e))
        return "", step


def stage_ab(doc_id: str) -> StepTiming:
    """Run Stage A/B (structure preview)."""
    step = time_step("stage_ab")
    try:
        resp = requests.post(
            f"{WEBUI_URL}/analyze-stage-ab", json={"doc_id": doc_id}, timeout=60
        )
        resp.raise_for_status()
        complete_step(step)
        return step
    except Exception as e:
        complete_step(step, success=False, error=str(e))
        return step


def grant_consent(doc_id: str) -> StepTiming:
    """Grant consent for analysis."""
    step = time_step("consent")
    try:
        resp = requests.post(
            f"{SOA1_API_URL}/api/consent",
            json={"doc_id": doc_id, "confirm": True, "specialist": "phinance"},
            timeout=10,
        )
        resp.raise_for_status()
        complete_step(step)
        return step
    except Exception as e:
        complete_step(step, success=False, error=str(e))
        return step


def start_analysis(doc_id: str) -> StepTiming:
    """Start the analysis (analyze-confirm)."""
    step = time_step("start_analysis")
    try:
        resp = requests.post(
            f"{WEBUI_URL}/analyze-confirm", json={"doc_id": doc_id}, timeout=10
        )
        resp.raise_for_status()
        complete_step(step)
        return step
    except Exception as e:
        complete_step(step, success=False, error=str(e))
        return step


def wait_for_completion(
    doc_id: str, timeout: int = 120
) -> tuple[Dict[str, Any], StepTiming]:
    """Poll for analysis completion."""
    step = time_step("analysis_wait")
    start = time.time()
    result = {}

    try:
        while time.time() - start < timeout:
            resp = requests.get(f"{WEBUI_URL}/analysis-status/{doc_id}", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status", "")
                if status == "completed":
                    result = data
                    complete_step(step)
                    return result, step
                elif status == "failed":
                    complete_step(
                        step, success=False, error=data.get("error", "Analysis failed")
                    )
                    return result, step
            time.sleep(1)

        complete_step(step, success=False, error="Timeout waiting for completion")
        return result, step
    except Exception as e:
        complete_step(step, success=False, error=str(e))
        return result, step


def get_timing(doc_id: str) -> Dict[str, Any]:
    """Get detailed timing from the timing endpoint."""
    try:
        resp = requests.get(f"{WEBUI_URL}/analysis-timing/{doc_id}", timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return {}


def test_single_pdf(pdf_path: Path, index: int) -> PDFTestResult:
    """Run full test on a single PDF."""
    result = PDFTestResult(pdf_name=pdf_path.name)
    total_start = time.time()

    log(f"[PDF {index + 1}/{NUM_PDFS}] Starting: {pdf_path.name}")

    # Step 1: Upload
    doc_id, step = upload_pdf(pdf_path)
    result.steps.append(step)
    result.doc_id = doc_id
    if not step.success:
        result.success = False
        result.error = f"Upload failed: {step.error}"
        log(f"  ❌ Upload failed: {step.error}")
        return result
    log(f"  ✓ Upload: {step.duration_ms:.0f}ms → doc_id={doc_id[:20]}...")

    # Step 2: Stage A/B
    step = stage_ab(doc_id)
    result.steps.append(step)
    if not step.success:
        result.success = False
        result.error = f"Stage A/B failed: {step.error}"
        log(f"  ❌ Stage A/B failed: {step.error}")
        return result
    log(f"  ✓ Stage A/B: {step.duration_ms:.0f}ms")

    # Step 3: Consent
    step = grant_consent(doc_id)
    result.steps.append(step)
    if not step.success:
        result.success = False
        result.error = f"Consent failed: {step.error}"
        log(f"  ❌ Consent failed: {step.error}")
        return result
    log(f"  ✓ Consent: {step.duration_ms:.0f}ms")

    # Step 4: Start Analysis
    step = start_analysis(doc_id)
    result.steps.append(step)
    if not step.success:
        result.success = False
        result.error = f"Start analysis failed: {step.error}"
        log(f"  ❌ Start analysis failed: {step.error}")
        return result
    log(f"  ✓ Start analysis: {step.duration_ms:.0f}ms")

    # Step 5: Wait for completion
    analysis_result, step = wait_for_completion(doc_id)
    result.steps.append(step)
    if not step.success:
        result.success = False
        result.error = f"Analysis failed: {step.error}"
        log(f"  ❌ Analysis wait failed: {step.error}")
        return result

    result.transaction_count = analysis_result.get("transaction_count", 0)
    log(
        f"  ✓ Analysis complete: {step.duration_ms:.0f}ms ({result.transaction_count} transactions)"
    )

    # Get detailed timing
    timing = get_timing(doc_id)
    result.analysis_timing = timing.get("timing", {})
    result.anomaly_count = len(timing.get("anomalies", []))

    # Log internal timing
    if result.analysis_timing.get("steps"):
        log(f"  📊 Internal timing:")
        for s in result.analysis_timing["steps"]:
            log(f"     - {s['step']}: {s['duration_ms']:.0f}ms")
        log(f"     - Total: {result.analysis_timing.get('total_ms', 0):.0f}ms")

    if result.anomaly_count > 0:
        log(f"  ⚠️  {result.anomaly_count} anomalies detected")

    result.total_duration_ms = (time.time() - total_start) * 1000
    log(f"  ✅ PDF complete: {result.total_duration_ms:.0f}ms total")

    return result


def main():
    """Run multi-PDF test."""
    log("=" * 60)
    log(f"MULTI-PDF INTEGRATION TEST - {NUM_PDFS} PDFs")
    log("=" * 60)

    # Find unique test PDFs (avoid duplicates with same base name)
    all_pdfs = sorted(TEST_PDF_DIR.glob("*.pdf"))
    seen_names = set()
    test_pdfs = []
    for pdf in all_pdfs:
        # Extract base name (remove doc_id prefixes)
        base = pdf.name
        for prefix in ["finance-2025", "Apple Card"]:
            if prefix in base:
                base = base[base.find("Apple Card") :] if "Apple Card" in base else base
                break
        if base not in seen_names:
            seen_names.add(base)
            test_pdfs.append(pdf)
        if len(test_pdfs) >= NUM_PDFS:
            break

    if len(test_pdfs) < NUM_PDFS:
        log(f"⚠️  Only found {len(test_pdfs)} unique PDFs, using what's available")

    log(f"Testing {len(test_pdfs)} PDFs:")
    for i, pdf in enumerate(test_pdfs):
        log(f"  {i + 1}. {pdf.name}")
    log("")

    # Run tests
    results: List[PDFTestResult] = []
    test_start = time.time()

    for i, pdf in enumerate(test_pdfs):
        result = test_single_pdf(pdf, i)
        results.append(result)
        log("")

    total_test_time = (time.time() - test_start) * 1000

    # Summary
    log("=" * 60)
    log("TEST SUMMARY")
    log("=" * 60)

    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    log(f"Results: {len(successful)}/{len(results)} successful")
    log(f"Total test time: {total_test_time:.0f}ms ({total_test_time / 1000:.1f}s)")
    log("")

    # Timing breakdown
    log("Per-PDF Timing:")
    log("-" * 60)
    for r in results:
        status = "✅" if r.success else "❌"
        log(f"{status} {r.pdf_name[:40]:<40} {r.total_duration_ms:>8.0f}ms")
        if r.analysis_timing.get("steps"):
            for s in r.analysis_timing["steps"]:
                log(f"   └─ {s['step']:<25} {s['duration_ms']:>8.0f}ms")

    log("")

    # Aggregate stats
    if successful:
        total_transactions = sum(r.transaction_count for r in successful)
        total_anomalies = sum(r.anomaly_count for r in successful)
        avg_time = sum(r.total_duration_ms for r in successful) / len(successful)

        # Extract internal timing averages
        step_times = {}
        for r in successful:
            for s in r.analysis_timing.get("steps", []):
                step_name = s["step"]
                if step_name not in step_times:
                    step_times[step_name] = []
                step_times[step_name].append(s["duration_ms"])

        log("Aggregate Statistics:")
        log(f"  Total transactions processed: {total_transactions}")
        log(f"  Total anomalies detected: {total_anomalies}")
        log(f"  Average time per PDF: {avg_time:.0f}ms")
        log("")
        log("Average Internal Step Timing:")
        for step, times in step_times.items():
            avg = sum(times) / len(times)
            log(f"  {step:<25} {avg:>8.0f}ms (n={len(times)})")

    if failed:
        log("")
        log("Failed PDFs:")
        for r in failed:
            log(f"  ❌ {r.pdf_name}: {r.error}")

    # Save detailed results
    LOG_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = LOG_DIR / f"multi_pdf_test_{timestamp}.json"

    output = {
        "timestamp": datetime.now().isoformat(),
        "num_pdfs": len(results),
        "successful": len(successful),
        "failed": len(failed),
        "total_test_time_ms": total_test_time,
        "results": [asdict(r) for r in results],
    }

    with open(log_file, "w") as f:
        json.dump(output, f, indent=2, default=str)

    log("")
    log(f"Detailed results saved to: {log_file}")

    # Check GPU status at end
    log("")
    log("Final GPU Status:")
    import subprocess

    gpu_result = subprocess.run(["ollama", "ps"], capture_output=True, text=True)
    for line in gpu_result.stdout.strip().split("\n"):
        log(f"  {line}")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
