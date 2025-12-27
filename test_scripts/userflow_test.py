#!/usr/bin/env python3
"""
Userflow test harness for SOA1 finance pipeline.
- Uploads a PDF via /upload
- Requests stage A/B (structure preview)
- Confirms analysis (/analyze-confirm) and polls /analysis-status until completed
- Verifies reports (transactions.json, analysis.json) exist and records mtimes
- Calls /api/chat to get a short tidbit answer
- Logs per-step timestamps and durations to JSONL in /home/ryzen/projects/test_logs

Run: python3 test_scripts/userflow_test.py
"""

import requests
import time
import json
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, parse_qs

BASE_URL = "http://localhost:8080"
SOA1_API = "http://localhost:8001"

TEST_LOG_DIR = Path("/home/ryzen/projects/test_logs")
TEST_LOG_DIR.mkdir(parents=True, exist_ok=True)

SAMPLE_PDF = Path(
    "/home/ryzen/projects/home-ai/finance-agent/data/uploads/finance-20251224-153218-4de4ed_Apple Card Statement - September 2025.pdf"
)


def ts():
    return datetime.utcnow().isoformat() + "Z"


def write_log(entry):
    fn = TEST_LOG_DIR / f"userflow_{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.jsonl"
    # Append single-line JSON (create if missing)
    with open(fn, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return fn


def upload_pdf(pdf_path: Path):
    t0 = time.time()
    with open(pdf_path, "rb") as f:
        files = {"file": (pdf_path.name, f, "application/pdf")}
        r = requests.post(f"{SOA1_API}/upload-pdf", files=files, timeout=60)
    t1 = time.time()

    result = {
        "step": "upload",
        "ok": False,
        "status_code": r.status_code,
        "duration": t1 - t0,
        "ts": ts(),
    }

    doc_id = None
    if r.status_code == 200:
        try:
            data = r.json()
            doc_id = data.get("doc_id")
            result["response"] = data
        except Exception:
            pass
    result["doc_id"] = doc_id
    result["ok"] = doc_id is not None

    return result


def analyze_stage_ab(doc_id: str):
    t0 = time.time()
    payload = {"doc_id": doc_id}
    r = requests.post(f"{BASE_URL}/analyze-stage-ab", json=payload, timeout=180)
    t1 = time.time()
    out = {
        "step": "stage_ab",
        "ok": False,
        "status_code": r.status_code,
        "duration": t1 - t0,
        "ts": ts(),
    }
    try:
        data = r.json()
        out["ok"] = True
        out["data"] = data
    except Exception as e:
        out["error"] = str(e)
    return out


def grant_consent(doc_id: str):
    """Call SOA1 API /api/consent to grant consent for analysis."""
    t0 = time.time()
    payload = {"doc_id": doc_id, "confirm": True, "specialist": "phinance"}
    r = requests.post(f"{SOA1_API}/api/consent", json=payload, timeout=30)
    t1 = time.time()
    out = {
        "step": "grant_consent",
        "ok": False,
        "status_code": r.status_code,
        "duration": t1 - t0,
        "ts": ts(),
    }
    try:
        data = r.json()
        out["ok"] = r.status_code == 200 and data.get("confirmed", False)
        out["data"] = data
    except Exception as e:
        out["error"] = str(e)
    return out


def analyze_confirm_and_wait(doc_id: str, poll_interval=2, max_wait=300):
    t0 = time.time()
    payload = {"doc_id": doc_id}
    r = requests.post(f"{BASE_URL}/analyze-confirm", json=payload, timeout=10)
    t_confirm = time.time()
    out = {
        "step": "analyze_confirm",
        "ok": False,
        "status_code": r.status_code if r is not None else None,
        "duration_request": t_confirm - t0,
        "ts_confirm": ts(),
    }
    try:
        data = r.json()
        out["response"] = data
    except Exception as e:
        out["response_error"] = str(e)

    # If started, poll analysis-status until completed
    started_at = time.time()
    poll_start = time.time()
    final = None
    while time.time() - poll_start < max_wait:
        rr = requests.get(f"{BASE_URL}/analysis-status/{doc_id}", timeout=10)
        now = time.time()
        try:
            sdata = rr.json()
        except Exception:
            sdata = {"raw_status": rr.text}
        out.setdefault("polls", []).append(
            {"ts": ts(), "status_code": rr.status_code, "body": sdata}
        )
        status = sdata.get("status")
        if status == "completed":
            final = {
                "completed": True,
                "ts": ts(),
                "duration_total": now - t0,
                "data": sdata,
            }
            out["ok"] = True
            out["final"] = final
            break
        elif status == "failed":
            final = {
                "completed": False,
                "ts": ts(),
                "duration_total": now - t0,
                "data": sdata,
            }
            out["ok"] = False
            out["final"] = final
            break
        time.sleep(poll_interval)

    if final is None:
        out["ok"] = False
        out["timeout"] = True
    return out


def check_reports_for_doc(doc_id: str):
    reports_dir = (
        Path(__file__).resolve().parents[1]
        / "home-ai"
        / "finance-agent"
        / "data"
        / "reports"
        / doc_id
    )
    result = {
        "step": "check_reports",
        "doc_id": doc_id,
        "exists": False,
        "files": {},
        "ts": ts(),
    }
    if not reports_dir.exists():
        result["reason"] = "reports_dir_missing"
        return result
    result["exists"] = True
    for fname in ("transactions.json", "analysis.json"):
        fpath = reports_dir / fname
        if fpath.exists():
            result["files"][fname] = {
                "mtime": fpath.stat().st_mtime,
                "iso_mtime": datetime.utcfromtimestamp(
                    fpath.stat().st_mtime
                ).isoformat()
                + "Z",
                "size": fpath.stat().st_size,
            }
        else:
            result["files"][fname] = None
    return result


def chat_follow_up(question: str):
    t0 = time.time()
    payload = {"message": question}
    r = requests.post(f"{BASE_URL}/api/chat", json=payload, timeout=120)
    t1 = time.time()
    out = {
        "step": "chat_followup",
        "ok": False,
        "status_code": r.status_code,
        "duration": t1 - t0,
        "ts": ts(),
    }
    try:
        data = r.json()
        out["ok"] = True
        out["response"] = data
    except Exception as e:
        out["error"] = str(e)
    return out


def main():
    logfile = None
    run_entry = {"run_started": ts(), "steps": []}

    if not SAMPLE_PDF.exists():
        print("Sample PDF not found:", SAMPLE_PDF)
        return

    print("Uploading sample PDF via /upload...")
    up = upload_pdf(SAMPLE_PDF)
    run_entry["steps"].append(up)
    logfile = write_log({"event": "upload_result", "data": up})
    if not up.get("ok"):
        print("Upload failed or doc_id not parsed; aborting. Response:", up)
        return

    doc_id = up.get("doc_id")
    print("Stage A/B (structure preview)...")
    st = analyze_stage_ab(doc_id)
    run_entry["steps"].append(st)
    write_log({"event": "stage_ab", "data": st})

    print("Granting consent via /api/consent...")
    consent = grant_consent(doc_id)
    run_entry["steps"].append(consent)
    write_log({"event": "grant_consent", "data": consent})
    if not consent.get("ok"):
        print("Consent grant failed; aborting. Response:", consent)
        return

    print("Confirm analysis and wait for completion...")
    ac = analyze_confirm_and_wait(doc_id)
    run_entry["steps"].append(ac)
    write_log({"event": "analyze_confirm_and_wait", "data": ac})

    # Check reports
    rep = check_reports_for_doc(doc_id)
    run_entry["steps"].append(rep)
    write_log({"event": "reports_check", "data": rep})

    # Chat follow-up (if analysis completed)
    if ac.get("ok"):
        cf = chat_follow_up("What is a quick insight from my recent analysis?")
        run_entry["steps"].append(cf)
        write_log({"event": "chat_followup", "data": cf})
    else:
        print("Analysis did not complete successfully; skipping chat follow-up.")

    run_entry["run_completed"] = ts()
    write_log({"event": "run_summary", "data": run_entry})
    print("Logs written to", logfile)


if __name__ == "__main__":
    main()
