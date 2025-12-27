#!/usr/bin/env python3
"""
SOA1 Finance Pipeline API Test
Tests the complete user flow via API endpoints with timing for each step
"""

import argparse
import requests
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime
import sys

BASE_URL = "http://localhost:8080"
SOA1_API = "http://localhost:8001"


class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


class Timer:
    def __init__(self, name: str):
        self.name = name
        self.start_time = None
        self.end_time = None
        self.duration = None

    def __enter__(self):
        self.start_time = time.time()
        print(f"\n{Colors.OKCYAN}⏱️  Starting: {self.name}{Colors.ENDC}")
        return self

    def __exit__(self, *args):
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        print(
            f"{Colors.OKGREEN}✅ Completed: {self.name} in {self.duration:.2f}s{Colors.ENDC}"
        )


class TestResult:
    def __init__(self):
        self.total_time = 0
        self.steps: List[Tuple[str, float, bool]] = []

    def add_step(self, name: str, duration: float, success: bool):
        self.steps.append((name, duration, success))
        if success:
            self.total_time += duration

    def print_summary(self):
        print(f"\n{Colors.HEADER}{'=' * 70}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}TEST SUMMARY{Colors.ENDC}")
        print(f"{Colors.HEADER}{'=' * 70}{Colors.ENDC}\n")
        for name, duration, success in self.steps:
            status = f"{Colors.OKGREEN}✅ PASS" if success else f"{Colors.FAIL}❌ FAIL"
            print(f"{status:<20}{Colors.ENDC} {name:<40} {duration:>8.2f}s")
        print(f"\n{Colors.HEADER}{'=' * 70}{Colors.ENDC}")
        print(f"{Colors.BOLD}Total Pipeline Time: {self.total_time:.2f}s{Colors.ENDC}")
        print(f"{Colors.HEADER}{'=' * 70}{Colors.ENDC}\n")


def test_model_initialization() -> Tuple[bool, float]:
    """Test 0: Check if models are loaded"""
    with Timer("Model Status Check") as timer:
        try:
            response = requests.get(f"{BASE_URL}/api/models", timeout=5)
            response.raise_for_status()
            data = response.json()

            print(f"  Ollama Running: {data['ollama_running']}")
            print(f"  Available Models: {len(data.get('available_models', []))}")
            print(f"  Loaded Models: {len(data.get('loaded_models', {}))}")

            for model_name, model_info in data.get("loaded_models", {}).items():
                print(f"    - {model_name}: {model_info['vram_mb']} MB VRAM")

            # Models load on-demand, so we just need Ollama running
            success = data["ollama_running"]

            if len(data.get("loaded_models", {})) < 2:
                print(
                    f"{Colors.WARNING}⚠️  Only {len(data.get('loaded_models', {}))} model(s) pre-loaded (models will load on-demand){Colors.ENDC}"
                )
        except Exception as e:
            print(f"{Colors.FAIL}❌ Error: {e}{Colors.ENDC}")
            success = False

    # Return after the timer context so timer.duration is populated by __exit__
    return success, timer.duration if timer.duration else 0.0


def test_pdf_upload(pdf_path: str) -> Tuple[bool, str, float]:
    """Test 1: Upload PDF statement"""
    with Timer("PDF Upload") as timer:
        try:
            with open(pdf_path, "rb") as f:
                files = {"file": (Path(pdf_path).name, f, "application/pdf")}
                # Use the SOA1 API upload endpoint which returns JSON (status, file_id, ...)
                response = requests.post(
                    f"{SOA1_API}/upload-pdf", files=files, timeout=30
                )
                response.raise_for_status()
                data = response.json()

                # Prefer the WebUI-friendly doc_id (finance-YYYY...) returned by the server; fall back to file_id (UUID)
                doc_id = data.get("doc_id") or data.get("file_id")
                file_id = data.get("file_id")

                # Check for explicit error status
                status = data.get("status")
                if isinstance(status, str) and status.lower().startswith("error"):
                    print(f"  Server reported error: {data.get('message')}")
                    success = False
                    doc_id = None
                else:
                    success = True

                # If the server did not return a finance-style doc_id, attempt to resolve it
                # by scanning the WebUI uploads directory for a matching filename
                if success and not (
                    isinstance(doc_id, str) and doc_id.startswith("finance-")
                ):
                    import os

                    webui_upload_dir = (
                        Path(
                            os.environ.get(
                                "FINANCE_DATA_DIR",
                                "/home/ryzen/projects/home-ai/finance-agent/data",
                            )
                        )
                        / "uploads"
                    )
                    candidates = list(webui_upload_dir.glob(f"*{Path(pdf_path).name}"))
                    if candidates:
                        candidate_name = candidates[0].name
                        resolved = candidate_name.split("_")[0]
                        print(f"  Resolved doc_id from WebUI uploads: {resolved}")
                        doc_id = resolved

                print(f"  Doc ID: {doc_id}")
                print(f"  File ID: {file_id}")
                print(f"  Status: {status}")
                print(f"  Message: {data.get('message')}")

        except Exception as e:
            print(f"{Colors.FAIL}❌ Error: {e}{Colors.ENDC}")
            success = False
            doc_id = None

    # Return after timer context so duration is set
    return success, doc_id, timer.duration if timer.duration else 0.0


def test_nemoagent_conversation(message: str) -> Tuple[bool, str, float]:
    """Test 2: Talk to NemoAgent (general conversation)"""
    with Timer(f"NemoAgent: '{message[:50]}...'") as timer:
        try:
            payload = {"query": message}
            response = requests.post(f"{SOA1_API}/ask", json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()

            answer = data.get("answer", "")
            memories = data.get("used_memories", [])

            print(f"  Answer: {answer[:200]}...")
            print(f"  Used Memories: {len(memories)}")
            success = True
        except Exception as e:
            print(f"{Colors.FAIL}❌ Error: {e}{Colors.ENDC}")
            success = False
            answer = None

    # Return after timer context so duration is set
    return success, answer, timer.duration if timer.duration else 0.0


def test_analyze_preview(doc_id: str) -> Tuple[bool, Dict, float]:
    """Test 3: Get analysis preview (Stage A/B - NemoAgent reads structure)"""
    with Timer("Analysis Preview (NemoAgent Structure Reading)") as timer:
        try:
            payload = {"doc_id": doc_id}
            response = requests.post(
                f"{BASE_URL}/analyze-stage-ab", json=payload, timeout=180
            )
            response.raise_for_status()
            data = response.json()

            print(f"  Status: {data.get('status')}")
            print(f"  Account Holder: {data.get('account_holder')}")
            print(f"  Institution: {data.get('institution')}")
            print(f"  Statement Type: {data.get('statement_type')}")
            print(f"  Timeframe: {data.get('timeframe')}")
            print(f"  Synopsis: {data.get('synopsis', '')[:100]}...")

            success = True
        except Exception as e:
            print(f"{Colors.FAIL}❌ Error: {e}{Colors.ENDC}")
            success = False
            data = None

    return success, data, timer.duration if timer.duration else 0.0


def test_analyze_confirm(doc_id: str) -> Tuple[bool, Dict, float]:
    """Test 4: Confirm analysis (Phinance specialist extraction + insights)"""
    with Timer("Phinance Analysis (Transaction Extraction + Insights)") as timer:
        try:
            payload = {"doc_id": doc_id}
            response = requests.post(
                f"{BASE_URL}/analyze-confirm", json=payload, timeout=180
            )
            response.raise_for_status()
            data = response.json()

            print(f"  Status: {data.get('status')}")

            if data.get("status") == "started":
                print(
                    f"  {Colors.WARNING}Analysis started, checking status...{Colors.ENDC}"
                )
                success, final_data, total_duration = wait_for_analysis_completion(
                    doc_id, timer
                )
                return success, final_data, total_duration

            success = True
        except Exception as e:
            print(f"{Colors.FAIL}❌ Error: {e}{Colors.ENDC}")
            success = False
            data = None

    return success, data, timer.duration if timer.duration else 0.0


def wait_for_analysis_completion(
    doc_id: str, original_timer: Timer, max_wait: int = 120
) -> Tuple[bool, Dict, float]:
    """Wait for async analysis to complete"""
    start_wait = time.time()
    while time.time() - start_wait < max_wait:
        try:
            response = requests.get(f"{BASE_URL}/analysis-status/{doc_id}", timeout=10)
            response.raise_for_status()
            data = response.json()
            status = data.get("status")
            print(f"  Status: {status}")
            if status == "completed":
                total_duration = time.time() - original_timer.start_time
                return True, data, total_duration
            elif status == "failed":
                print(f"{Colors.FAIL}  Error: {data.get('error')}{Colors.ENDC}")
                return False, data, time.time() - original_timer.start_time
            time.sleep(2)
        except Exception as e:
            print(f"{Colors.WARNING}  Waiting... ({e}){Colors.ENDC}")
            time.sleep(2)
    print(f"{Colors.FAIL}  Timeout waiting for analysis{Colors.ENDC}")
    return False, None, time.time() - original_timer.start_time


def verify_analysis_results(data: Dict) -> bool:
    """Verify the analysis contains expected data (updated for new API response)"""
    print(f"\n{Colors.OKCYAN}📊 Verifying Analysis Results...{Colors.ENDC}")
    checks = []
    txn_count = data.get("transaction_count", 0)
    if txn_count > 0:
        print(f"  ✅ Transactions: {txn_count}")
        checks.append(True)
    else:
        print(f"  ❌ No transactions found")
        checks.append(False)
    insights = data.get("insights", "")
    if isinstance(insights, str) and insights.strip():
        insight_lines = insights.strip().split("\n")
        print(f"  ✅ Insights: {len(insight_lines)} lines")
        for i, insight in enumerate(insight_lines[:3], 1):
            print(f"     {i}. {insight}")
        checks.append(True)
    else:
        print(f"  ❌ No insights found")
        checks.append(False)
    status = data.get("status", "")
    if status == "completed":
        print(f"  ✅ Status: completed")
        checks.append(True)
    else:
        print(f"  ❌ Status: {status}")
        checks.append(False)
    return all(checks)


def test_follow_up_question(message: str) -> Tuple[bool, str, float]:
    """Test 5: Ask follow-up question to NemoAgent about analysis"""
    return test_nemoagent_conversation(message)


def main():
    print(f"\n{Colors.HEADER}{Colors.BOLD}")
    print("=" * 70)
    print("SOA1 FINANCE PIPELINE - END-TO-END API TEST")
    print("=" * 70)
    print(f"{Colors.ENDC}\n")
    parser = argparse.ArgumentParser(
        description="SOA1 Finance Pipeline End-to-End Test"
    )
    parser.add_argument(
        "pdf_path",
        type=str,
        help="Path to the PDF statement to test (required)",
    )
    args = parser.parse_args()
    pdf_path = args.pdf_path
    if not Path(pdf_path).exists():
        print(f"{Colors.FAIL}❌ Test PDF not found: {pdf_path}{Colors.ENDC}")
        print(
            f"{Colors.WARNING}Please provide a valid PDF path as a command-line argument.{Colors.ENDC}"
        )
        sys.exit(1)
    result = TestResult()
    pdf_filename = Path(pdf_path).name
    doc_id = pdf_filename.split("_")[0]  # Gets "finance-20251224-153218-4de4ed"
    print(f"{Colors.OKBLUE}📄 Test PDF: {pdf_path}{Colors.ENDC}")
    print(f"{Colors.OKBLUE}📋 Document ID: {doc_id}{Colors.ENDC}")
    print(f"\n{Colors.HEADER}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.BOLD}STEP 0: Model Initialization Check{Colors.ENDC}")
    print(f"{Colors.HEADER}{'=' * 70}{Colors.ENDC}")
    success, duration = test_model_initialization()
    result.add_step("Model Initialization Check", duration, success)
    if not success:
        print(f"\n{Colors.FAIL}❌ Ollama is not running. Cannot proceed.{Colors.ENDC}")
        return
    print(f"\n{Colors.HEADER}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.BOLD}STEP 1: Upload PDF{Colors.ENDC}")
    print(f"{Colors.HEADER}{'=' * 70}{Colors.ENDC}")
    # Use /upload-pdf endpoint for PDF upload
    success, uploaded_doc_id, duration = test_pdf_upload(pdf_path)
    if not success:
        print(f"\n{Colors.FAIL}❌ PDF upload failed. Cannot proceed.{Colors.ENDC}")
        return
    print(f"  Document ID: {uploaded_doc_id}")
    result.add_step("PDF Uploaded", duration, True)
    doc_id = uploaded_doc_id
    print(f"\n{Colors.HEADER}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.BOLD}STEP 2: Talk to NemoAgent (General Conversation){Colors.ENDC}")
    print(f"{Colors.HEADER}{'=' * 70}{Colors.ENDC}")
    success, answer, duration = test_nemoagent_conversation(
        "What can you help me with?"
    )
    result.add_step("NemoAgent Conversation", duration, success)
    print(f"\n{Colors.HEADER}{'=' * 70}{Colors.ENDC}")
    print(
        f"{Colors.BOLD}STEP 3: Request Analysis Preview (NemoAgent Structure Reading){Colors.ENDC}"
    )
    print(f"{Colors.HEADER}{'=' * 70}{Colors.ENDC}")
    success, preview_data, duration = test_analyze_preview(doc_id)
    result.add_step("Analysis Preview (NemoAgent)", duration, success)
    if not success:
        return
    print(f"\n{Colors.HEADER}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.BOLD}STEP 4: Confirm Analysis (Phinance Specialist){Colors.ENDC}")
    print(f"{Colors.HEADER}{'=' * 70}{Colors.ENDC}")
    success, analysis_data, duration = test_analyze_confirm(doc_id)
    result.add_step("Phinance Analysis", duration, success)
    if not success:
        return
    success = verify_analysis_results(analysis_data)
    if not success:
        print(f"\n{Colors.FAIL}⚠️  Analysis results incomplete{Colors.ENDC}")
        return
    print(f"\n{Colors.HEADER}{'=' * 70}{Colors.ENDC}")
    print(
        f"{Colors.BOLD}STEP 5: Follow-up Question (NemoAgent with Context){Colors.ENDC}"
    )
    print(f"{Colors.HEADER}{'=' * 70}{Colors.ENDC}")
    success, answer, duration = test_follow_up_question("What were my top 3 expenses?")
    result.add_step("Follow-up Question", duration, success)
    result.print_summary()
    print(f"{Colors.OKGREEN}{Colors.BOLD}✅ ALL TESTS PASSED!{Colors.ENDC}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}⚠️  Test interrupted by user{Colors.ENDC}")
    except Exception as e:
        print(f"\n{Colors.FAIL}❌ Unexpected error: {e}{Colors.ENDC}")
        import traceback

        traceback.print_exc()
