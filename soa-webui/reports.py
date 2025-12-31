from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import os

router = APIRouter()

# Determine reports directory (default to canonical finance-agent path)
BASE_DIR = Path(__file__).resolve().parents[1]
FINANCE_REPORTS_DIR = (
    Path(
        os.environ.get(
            "FINANCE_DATA_DIR", str(BASE_DIR / "home-ai" / "finance-agent" / "data")
        )
    )
    / "reports"
)

_seeded_jobs: Dict[str, Dict[str, Any]] = {}


def _load_json_if_exists(path: Path) -> Optional[Dict[str, Any]]:
    try:
        if path.exists() and path.is_file():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def seed_analysis_jobs_from_reports(
    force: bool = False, limit: Optional[int] = None
) -> int:
    """Scan FINANCE_REPORTS_DIR and create lightweight seeded job records.

    This is intentionally read-only and fast: we create minimal job entries that
    the monitoring UI can display after restarts. Returns the number of jobs seeded.
    """
    if not FINANCE_REPORTS_DIR.exists() or not FINANCE_REPORTS_DIR.is_dir():
        return 0

    seeded = 0
    report_dirs = sorted(
        [d for d in FINANCE_REPORTS_DIR.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )

    for d in report_dirs:
        doc_id = d.name
        if doc_id in _seeded_jobs and not force:
            continue

        analysis = (
            _load_json_if_exists(d / "analysis.json")
            or _load_json_if_exists(d / "dashboard" / "analysis.json")
            or {}
        )
        tx = (
            _load_json_if_exists(d / "transactions.json")
            or _load_json_if_exists(d / "dashboard" / "transactions.json")
            or {}
        )

        transactions = tx.get("transactions", []) if isinstance(tx, dict) else []

        # Transaction count
        tx_count = (
            analysis.get("transaction_count")
            or (analysis.get("summary") or {}).get("numtransactions")
            or len(transactions)
        )

        total_spent = analysis.get("total_spent") or (
            analysis.get("summary") or {}
        ).get("totalspending")

        # Completed timestamp
        extraction_time = tx.get("extraction_time") if isinstance(tx, dict) else None
        started_at = None
        completed_at = None
        if extraction_time:
            try:
                completed_at = datetime.fromisoformat(extraction_time)
                started_at = completed_at
            except Exception:
                completed_at = None
                started_at = None
        else:
            try:
                mtime = d.stat().st_mtime
                completed_at = datetime.utcfromtimestamp(mtime)
                started_at = completed_at
            except Exception:
                pass

        # Anomaly heuristics
        anomalies: List[Dict[str, Any]] = []
        if isinstance(analysis.get("by_category"), dict) and total_spent:
            sum_cats = sum(analysis.get("by_category", {}).values())
            if abs((total_spent or 0) - sum_cats) > 0.05 * max(total_spent or 1, 1):
                anomalies.append(
                    {
                        "type": "category_mismatches",
                        "description": f"Total spent (${total_spent:.2f}) does not match sum of categories (${sum_cats:.2f})",
                        "severity": "medium",
                    }
                )

        # Large transactions
        large = [t for t in transactions if abs(t.get("amount", 0)) >= 500]
        if large:
            anomalies.append(
                {
                    "type": "large_transactions",
                    "description": f"{len(large)} transactions >= $500",
                    "severity": "medium",
                }
            )

        # Duplicates
        seen = {}
        dups = []
        for t in transactions:
            key = (t.get("date"), t.get("merchant"), float(t.get("amount") or 0))
            seen[key] = seen.get(key, 0) + 1
            if seen[key] > 1:
                dups.append(
                    {
                        "type": "duplicate_transactions",
                        "description": f"Duplicate transaction detected: {key}",
                        "severity": "low",
                    }
                )
        if dups:
            anomalies.extend(dups)

        job = {
            "doc_id": doc_id,
            "status": "completed",
            "started_at": started_at.isoformat() if started_at else None,
            "completed_at": completed_at.isoformat() if completed_at else None,
            "error": None,
            "transaction_count": tx_count,
            "duration_s": 0.0,
            "step_timings": {"seeded_from_report": 0.0},
            "pipeline_ms": 0.0,
            "anomaly_count": len(anomalies),
            "anomalies": anomalies,
            "seeded": True,
            "seed_source": "reports",
        }

        _seeded_jobs[doc_id] = job
        seeded += 1
        if limit and seeded >= limit:
            break

    return seeded


@router.post("/api/analysis/seed")
async def api_seed(force: bool = False, limit: Optional[int] = None):
    seeded = seed_analysis_jobs_from_reports(force=force, limit=limit)
    return {"seeded": seeded}


@router.get("/api/reports")
async def api_reports():
    reports: List[Dict[str, Any]] = []
    if not FINANCE_REPORTS_DIR.exists() or not FINANCE_REPORTS_DIR.is_dir():
        return {"reports": reports, "total": 0}

    for d in sorted(
        FINANCE_REPORTS_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True
    ):
        if not d.is_dir():
            continue
        analysis = _load_json_if_exists(d / "analysis.json") or {}
        reports.append(
            {
                "doc_id": d.name,
                "transaction_count": analysis.get("transaction_count")
                or (analysis.get("summary") or {}).get("numtransactions"),
                "total_spent": analysis.get("total_spent")
                or (analysis.get("summary") or {}).get("totalspending"),
                "has_dashboard": (d / "dashboard").exists(),
                "last_modified": d.stat().st_mtime,
            }
        )

    return {"reports": reports, "total": len(reports)}


@router.get("/reports")
async def reports_page(request: Request):
    # Simple page listing reports
    try:
        from soa_webui.main import check_access

        if not check_access(request.client.host):
            raise HTTPException(status_code=403, detail="Access denied: IP not allowed")
    except Exception:
        # fallback permissive if check_access not available
        pass

    reports = api_reports()["reports"]
    from fastapi.templating import Jinja2Templates

    templates = Jinja2Templates(
        directory=str(Path(__file__).resolve().parents[0] / "templates")
    )
    return templates.TemplateResponse(
        "reports.html", {"request": request, "reports": reports}
    )


@router.get("/reports/{doc_id}/dashboard/{filename}")
async def serve_report_file(request: Request, doc_id: str, filename: str):
    try:
        from soa_webui.main import check_access

        if not check_access(request.client.host):
            raise HTTPException(status_code=403, detail="Access denied: IP not allowed")
    except Exception:
        pass

    report_dir = FINANCE_REPORTS_DIR / doc_id
    dashboard_dir = report_dir / "dashboard"
    candidates = [dashboard_dir / filename, report_dir / filename]

    for p in candidates:
        try:
            if p.exists() and p.is_file():
                resolved = p.resolve()
                if str(resolved).startswith(str(FINANCE_REPORTS_DIR.resolve())):
                    return FileResponse(str(resolved), media_type="application/json")
        except Exception:
            pass

    raise HTTPException(status_code=404, detail="File not found")


@router.get("/api/analysis/jobs")
async def get_analysis_jobs():
    # Try to collect live jobs from main if available (best-effort), and merge with seeded jobs
    jobs: List[Dict[str, Any]] = []
    try:
        import soa_webui.main as mainmod

        if hasattr(mainmod, "_analysis_jobs"):
            for k, v in mainmod._analysis_jobs.items():
                # Attempt to normalize
                job = {
                    "doc_id": k,
                    "status": v.status.value
                    if hasattr(v, "status")
                    else v.get("status"),
                    "started_at": v.started_at.isoformat()
                    if getattr(v, "started_at", None)
                    else v.get("started_at"),
                    "completed_at": v.completed_at.isoformat()
                    if getattr(v, "completed_at", None)
                    else v.get("completed_at"),
                    "error": getattr(v, "error", None) or v.get("error"),
                    "transaction_count": (
                        len(v.result.transactions)
                        if getattr(v, "result", None)
                        and getattr(v.result, "transactions", None) is not None
                        else v.get("transaction_count")
                    ),
                }
                # timings & anomalies best-effort
                if hasattr(v, "timings"):
                    step_timings = {}
                    total_ms = 0
                    for t in v.timings:
                        if getattr(t, "duration_ms", None) is not None:
                            step_timings[getattr(t, "step")] = round(
                                getattr(t, "duration_ms"), 1
                            )
                            total_ms += getattr(t, "duration_ms")
                    if step_timings:
                        job["step_timings"] = step_timings
                        job["pipeline_ms"] = round(total_ms, 1)
                if hasattr(v, "anomalies"):
                    job["anomaly_count"] = len(v.anomalies)
                    job["anomalies"] = v.anomalies
                jobs.append(job)
    except Exception:
        pass

    # Merge seeded jobs, preferring live jobs
    for doc_id, sj in _seeded_jobs.items():
        if not any(j.get("doc_id") == doc_id for j in jobs):
            jobs.append(sj)

    # sort
    jobs.sort(key=lambda x: x.get("started_at") or "", reverse=True)
    return {"jobs": jobs, "total": len(jobs)}


@router.get("/api/reports/consolidated")
async def api_consolidated_reports():
    """Generate a consolidated report across all analyzed documents."""
    if not FINANCE_REPORTS_DIR.exists() or not FINANCE_REPORTS_DIR.is_dir():
        return {"error": "No reports directory found", "reports": []}

    all_transactions: List[Dict[str, Any]] = []
    all_analyses: List[Dict[str, Any]] = []
    total_spent = 0.0
    by_category: Dict[str, float] = {}
    by_month: Dict[str, float] = {}
    merchant_totals: Dict[str, float] = {}
    doc_summaries: List[Dict[str, Any]] = []

    for d in sorted(FINANCE_REPORTS_DIR.iterdir(), key=lambda x: x.stat().st_mtime):
        if not d.is_dir():
            continue

        doc_id = d.name
        analysis = _load_json_if_exists(d / "analysis.json") or {}
        tx_data = _load_json_if_exists(d / "transactions.json")

        transactions = []
        if isinstance(tx_data, list):
            transactions = tx_data
        elif isinstance(tx_data, dict):
            transactions = tx_data.get("transactions", [])
            if not transactions and isinstance(tx_data, dict):
                transactions = [tx_data] if "date" in tx_data else []

        doc_total = analysis.get("total_spent", 0) or 0
        doc_tx_count = analysis.get("transaction_count", len(transactions))

        doc_summaries.append(
            {
                "doc_id": doc_id,
                "total_spent": doc_total,
                "transaction_count": doc_tx_count,
                "date_range": analysis.get("date_range", {}),
            }
        )

        total_spent += doc_total

        for cat, amt in (analysis.get("by_category") or {}).items():
            by_category[cat] = by_category.get(cat, 0) + (amt or 0)

        for tx in transactions:
            tx_copy = dict(tx)
            tx_copy["source_doc"] = doc_id
            all_transactions.append(tx_copy)

            date_str = tx.get("date", "")
            if date_str and "/" in date_str:
                parts = date_str.split("/")
                if len(parts) >= 2:
                    month_key = f"{parts[0]}/{parts[2] if len(parts) > 2 else '2025'}"
                    amt = float(tx.get("amount", 0) or 0)
                    by_month[month_key] = by_month.get(month_key, 0) + amt

            merchant = tx.get("merchant", "Unknown")
            amt = float(tx.get("amount", 0) or 0)
            merchant_totals[merchant] = merchant_totals.get(merchant, 0) + amt

        if analysis:
            all_analyses.append(analysis)

    top_merchants = sorted(
        [{"name": k, "total": round(v, 2)} for k, v in merchant_totals.items()],
        key=lambda x: x["total"],
        reverse=True,
    )[:15]

    sorted_categories = dict(
        sorted(by_category.items(), key=lambda x: x[1], reverse=True)
    )

    month_order = [
        "01",
        "02",
        "03",
        "04",
        "05",
        "06",
        "07",
        "08",
        "09",
        "10",
        "11",
        "12",
    ]
    sorted_months = {}
    for m in month_order:
        for k, v in by_month.items():
            if k.startswith(m + "/"):
                sorted_months[k] = round(v, 2)

    all_insights = []
    all_recommendations = []
    for a in all_analyses:
        all_insights.extend(a.get("insights", []))
        all_recommendations.extend(a.get("recommendations", []))

    return {
        "consolidated": True,
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_documents": len(doc_summaries),
            "total_transactions": len(all_transactions),
            "total_spent": round(total_spent, 2),
            "currency": "USD",
        },
        "by_category": {k: round(v, 2) for k, v in sorted_categories.items()},
        "by_month": sorted_months,
        "top_merchants": top_merchants,
        "document_summaries": doc_summaries,
        "insights": list(set(all_insights))[:10],
        "recommendations": list(set(all_recommendations))[:10],
        "transactions": all_transactions,
    }


@router.get("/analysis-timing/{doc_id}")
async def analysis_timing(doc_id: str):
    # If seeded job exists, return its timing/anomalies
    if doc_id in _seeded_jobs:
        job = _seeded_jobs[doc_id]
        return {
            "doc_id": doc_id,
            "status": job.get("status"),
            "timing": {
                "steps": [
                    {"step": k, "duration_ms": v}
                    for k, v in (job.get("step_timings") or {}).items()
                ],
                "total_ms": job.get("pipeline_ms", 0),
            },
            "events": [],
            "anomalies": job.get("anomalies", []),
        }

    # Try to fetch from live jobs in main
    try:
        import soa_webui.main as mainmod

        if hasattr(mainmod, "_analysis_jobs") and doc_id in mainmod._analysis_jobs:
            v = mainmod._analysis_jobs[doc_id]
            return {
                "doc_id": doc_id,
                "status": v.status.value,
                "timing": v.get_timing_summary(),
                "events": v.events,
                "anomalies": v.anomalies,
            }
    except Exception:
        pass

    raise HTTPException(status_code=404, detail=f"No analysis found for {doc_id}")
