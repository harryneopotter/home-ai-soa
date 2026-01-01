#!/usr/bin/env python3
"""
SOA1 Web UI - Tailscale Edition
Main web application for monitoring and controlling SOA1 services
"""

from fastapi import FastAPI, Request, HTTPException, Depends, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer
import uvicorn
import os
from pathlib import Path
import yaml
import logging
import psutil
import requests
import socket
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum
import json
from pydantic import BaseModel

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("soa-webui")

# Configuration
CONFIG_FILE = "config.yaml"

# Security
security = HTTPBearer()


class ServiceStatus(BaseModel):
    name: str
    display_name: str
    port: int
    url: str
    status: str = "unknown"
    pid: Optional[int] = None
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    error: Optional[str] = None
    required: bool = True


class SystemStatus(BaseModel):
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    uptime: str = ""
    tailscale_ip: Optional[str] = None


class Config:
    def __init__(self):
        self.server = {"host": "0.0.0.0", "port": 8080}
        self.services = {}
        self.tailscale = {"enabled": True, "allowed_ips": ["100.64.0.0/10"]}
        self.security = {"ip_whitelist": ["100.64.0.0/10"]}
        self.features = {"service_control": True, "monitoring": True}
        self.load_config()

    def load_config(self):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = yaml.safe_load(f) or {}

            self.server.update(config.get("server", {}))
            self.services.update(config.get("services", {}))
            self.tailscale.update(config.get("tailscale", {}))
            self.security.update(config.get("security", {}))
            self.features.update(config.get("features", {}))

            logger.info("Configuration loaded successfully")
        except Exception as e:
            logger.warning(f"Could not load config: {e}")


# Load configuration
config = Config()

# Create FastAPI app
app = FastAPI(
    title="SOA1 Web UI - Tailscale Edition",
    description="Web interface for monitoring and controlling SOA1 services via Tailscale",
    version="1.0.0",
)

# Mount static files (use absolute path so startup works regardless of CWD)
STATIC_DIR = Path(__file__).resolve().parent / "static"
if not STATIC_DIR.exists():
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Load reports router from file location (robust to import style/package layout)
try:
    import importlib.util

    reports_path = Path(__file__).resolve().parent / "reports.py"
    if reports_path.exists():
        spec = importlib.util.spec_from_file_location(
            "soa_webui.reports", str(reports_path)
        )
        reports_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(reports_mod)
        app.include_router(reports_mod.router)
        logger.info("Reports router loaded from %s", reports_path)
    else:
        logger.info("Reports file not found; report endpoints disabled")
except Exception as exc:
    logger.info("Reports module import failed: %s", exc)


def get_tailscale_ip() -> Optional[str]:
    """Get the Tailscale IP address"""
    try:
        # Try to get Tailscale IP using tailscale command
        import subprocess

        result = subprocess.run(
            ["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass

    try:
        # Fallback: check for Tailscale interface
        addrs = psutil.net_if_addrs()
        for interface, addresses in addrs.items():
            for addr in addresses:
                if "tailscale" in interface.lower() and addr.family == socket.AF_INET:
                    return addr.address
    except Exception:
        pass

    return None


def is_allowed_ip(client_ip: str) -> bool:
    """Check if client IP is allowed (Tailscale range)"""
    allowed_ranges = config.security.get("ip_whitelist", ["100.64.0.0/10"])

    # Always allow localhost
    if client_ip in ["127.0.0.1", "localhost", "::1"]:
        return True

    # Check if IP is in allowed ranges
    from ipaddress import ip_address, ip_network

    try:
        client_ip_obj = ip_address(client_ip)
        for ip_range in allowed_ranges:
            if "/" in ip_range:
                network = ip_network(ip_range, strict=False)
                if client_ip_obj in network:
                    return True
            elif client_ip == ip_range:
                return True
    except Exception:
        pass

    return False


def get_service_status() -> List[ServiceStatus]:
    """Get status of all SOA1 services"""
    services = []

    # Define services to monitor
    service_definitions = [
        {
            "name": "soa1_api",
            "display": "SOA1 API",
            "port": 8001,
            "url": config.services.get("api", "http://localhost:8001"),
            "required": True,
        },
        {
            "name": "soa1_web",
            "display": "SOA1 Web Interface",
            "port": 8002,
            "url": config.services.get("web_interface", "http://localhost:8002"),
            "required": False,
        },
        {
            "name": "service_monitor",
            "display": "Service Monitor",
            "port": 8003,
            "url": config.services.get("service_monitor", "http://localhost:8003"),
            "required": False,
        },
        {
            "name": "memlayer",
            "display": "Memlayer",
            "port": 8000,
            "url": config.services.get("memlayer", "http://localhost:8000"),
            "required": True,
        },
        {
            "name": "ollama",
            "display": "Ollama (LLM)",
            "port": 11434,
            "url": "http://localhost:11434",
            "required": True,
        },
    ]

    for service_def in service_definitions:
        service = ServiceStatus(
            name=service_def["name"],
            display_name=service_def["display"],
            port=service_def["port"],
            url=service_def["url"],
            required=service_def["required"],
        )

        try:
            # Check if process is running
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    cmdline = " ".join(proc.info["cmdline"] or [])
                    if service.name in cmdline or str(service.port) in cmdline:
                        service.pid = proc.info["pid"]
                        service.cpu_usage = proc.cpu_percent(interval=0.1)
                        service.memory_usage = (
                            proc.memory_info().rss / 1024 / 1024
                        )  # MB
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # Try to connect to the service
            if service.pid:
                try:
                    response = requests.get(f"{service.url}/health", timeout=2)
                    if response.status_code == 200:
                        service.status = "running"
                    else:
                        service.status = "unresponsive"
                except requests.RequestException:
                    service.status = "unresponsive"
            else:
                service.status = "stopped"

        except Exception as e:
            service.status = "error"
            service.error = str(e)

        services.append(service)

    return services


def get_system_status() -> SystemStatus:
    global FINANCE_REPORTS_DIR
    if "FINANCE_REPORTS_DIR" not in globals():
        from pathlib import Path

        FINANCE_REPORTS_DIR = Path("home-ai/finance-agent/data/reports")

    status = SystemStatus()

    try:
        status.cpu_usage = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        status.memory_usage = memory.percent
        disk = psutil.disk_usage("/")
        status.disk_usage = disk.percent
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        status.uptime = str(uptime).split(".")[0]
        status.tailscale_ip = get_tailscale_ip()
    except Exception as e:
        logger.error(f"Error getting system status: {e}")

    return status


def check_access(client_ip: str):
    """Check if client IP is allowed to access"""
    if not config.tailscale.get("enabled", True):
        return True

    return is_allowed_ip(client_ip)


@app.get("/")
def home(request: Request):
    """User Chat & Upload Interface"""
    client_ip = request.client.host

    if not check_access(client_ip):
        raise HTTPException(status_code=403, detail="Access denied: IP not allowed")

    services = get_service_status()
    system_status = get_system_status()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": "SOA1 Assistant",
            "services": services,
            "system_status": system_status,
            "tailscale_ip": system_status.tailscale_ip,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )


@app.get("/dashboard/{doc_id}")
def analysis_dashboard(request: Request, doc_id: str):
    """Detailed Analysis Dashboard for a specific document"""
    client_ip = request.client.host

    if not check_access(client_ip):
        raise HTTPException(status_code=403, detail="Access denied: IP not allowed")

    return templates.TemplateResponse(
        "analysis_dashboard.html",
        {
            "request": request,
            "doc_id": doc_id,
        },
    )


@app.get("/dashboard/consolidated")
def consolidated_dashboard(request: Request):
    """Consolidated dashboard showing all analyzed documents"""
    client_ip = request.client.host

    if not check_access(client_ip):
        raise HTTPException(status_code=403, detail="Access denied: IP not allowed")

    return templates.TemplateResponse(
        "consolidated_dashboard.html",
        {"request": request},
    )


@app.get("/services")
def services_page(request: Request):
    """Detailed services page"""
    client_ip = request.client.host

    if not check_access(client_ip):
        raise HTTPException(status_code=403, detail="Access denied: IP not allowed")

    services = get_service_status()
    system_status = get_system_status()

    return templates.TemplateResponse(
        "services.html",
        {
            "request": request,
            "title": "SOA1 Services",
            "services": services,
            "system_status": system_status,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )


@app.get("/status")
def status_page(request: Request):
    """System status page"""
    client_ip = request.client.host

    if not check_access(client_ip):
        raise HTTPException(status_code=403, detail="Access denied: IP not allowed")

    system_status = get_system_status()
    services = get_service_status()

    # Get detailed system info
    try:
        # Network info
        net_io = psutil.net_io_counters()

        # Disk info
        disk_partitions = psutil.disk_partitions()

        # Process count
        process_count = len(psutil.pids())

    except Exception as e:
        logger.error(f"Error getting detailed system info: {e}")
        net_io = None
        disk_partitions = []
        process_count = 0

    return templates.TemplateResponse(
        "status.html",
        {
            "request": request,
            "title": "System Status",
            "system_status": system_status,
            "services": services,
            "net_io": net_io,
            "disk_partitions": disk_partitions,
            "process_count": process_count,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )


@app.get("/api/services")
def api_services():
    """API endpoint for service status"""
    services = get_service_status()
    system_status = get_system_status()

    return {
        "services": [
            {
                "name": s.name,
                "display_name": s.display_name,
                "status": s.status,
                "port": s.port,
                "url": s.url,
                "pid": s.pid,
                "cpu_usage": s.cpu_usage,
                "memory_usage": s.memory_usage,
                "error": s.error,
                "required": s.required,
            }
            for s in services
        ],
        "system": {
            "cpu_usage": system_status.cpu_usage,
            "memory_usage": system_status.memory_usage,
            "disk_usage": system_status.disk_usage,
            "uptime": system_status.uptime,
            "tailscale_ip": system_status.tailscale_ip,
        },
    }


@app.get("/health")
def health():
    """Health check endpoint"""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "tailscale_ip": get_tailscale_ip(),
    }


@app.get("/api/status")
def api_status():
    """Comprehensive status check for all services"""
    import subprocess

    status = {
        "webui": {"status": "online"},
        "soa1_api": {"status": "offline"},
        "ollama": {"status": "offline"},
        "models": {"status": "offline", "loaded": []},
    }

    try:
        r = requests.get("http://localhost:8001/health", timeout=2)
        status["soa1_api"]["status"] = "online" if r.ok else "offline"
    except:
        pass

    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        if r.ok:
            status["ollama"]["status"] = "online"
    except:
        pass

    try:
        result = subprocess.run(
            ["ollama", "ps"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")[1:]
            loaded = []
            for line in lines:
                if line.strip():
                    parts = line.split()
                    if parts:
                        loaded.append(parts[0])
            status["models"]["loaded"] = loaded
            status["models"]["status"] = "online" if loaded else "offline"
    except:
        pass

    return status


# =============================================================================
# Finance Analysis Endpoints
# =============================================================================

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys

sys.path.insert(0, "/home/ryzen/projects")

# Thread pool for parallel PDF processing (limit to 2 concurrent to avoid GPU contention)
_pdf_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="pdf_analysis")

try:
    from home_ai.finance_agent.src import storage as fa_storage

    FA_STORAGE_AVAILABLE = True
except ImportError:
    FA_STORAGE_AVAILABLE = False
    logger.warning("Finance storage module not available")

_analysis_jobs: Dict[str, Dict[str, Any]] = {}
_analysis_lock = threading.Lock()


class AnalyzeRequest(BaseModel):
    doc_id: str


def _get_job(doc_id: str) -> Optional[Dict[str, Any]]:
    with _analysis_lock:
        if doc_id in _analysis_jobs:
            return _analysis_jobs[doc_id].copy()
    if FA_STORAGE_AVAILABLE:
        try:
            fa_storage.init_db()
            job = fa_storage.load_job_by_doc_id(doc_id)
            if job:
                with _analysis_lock:
                    _analysis_jobs[doc_id] = dict(job)
                return dict(job)
        except Exception as e:
            logger.error(f"Failed to load job from DB: {e}")
    return None


def _save_job(job: Dict[str, Any]):
    doc_id = job.get("doc_id")
    with _analysis_lock:
        _analysis_jobs[doc_id] = job.copy()
    if FA_STORAGE_AVAILABLE:
        try:
            fa_storage.init_db()
            fa_storage.save_analysis_job(job)
        except Exception as e:
            logger.error(f"Failed to save job to DB: {e}")


def _run_phinance_analysis(job: Dict[str, Any], pdf_path: str):
    doc_id = job["doc_id"]
    job_id = job["job_id"]
    logger.info(f"Starting phinance analysis for {doc_id}")

    if FA_STORAGE_AVAILABLE:
        fa_storage.init_db()
        if fa_storage.has_transactions_for_doc(doc_id):
            logger.info(f"Skipping {doc_id} - transactions already cached")
            cached_txs = fa_storage.get_transactions_by_doc(doc_id)
            job["status"] = "completed"
            job["completed_at"] = datetime.utcnow().isoformat()
            job["transaction_count"] = len(cached_txs)
            job["from_cache"] = True
            _save_job(job)
            return

    try:
        job["status"] = "running"
        job["started_at"] = datetime.utcnow().isoformat()
        _save_job(job)

        import asyncio
        from pathlib import Path as PathLib
        from home_ai.finance_agent.src.parser import FinanceStatementParser

        async def run_parser():
            parser = FinanceStatementParser()
            pdf_path_obj = PathLib(pdf_path)
            identity = await parser.get_identity_context(pdf_path_obj, doc_id)
            summary = await parser.get_structural_summary(identity, pdf_path_obj)
            result = await parser.extract_transactions(identity, summary, pdf_path_obj)
            return result

        result = asyncio.run(run_parser())
        transactions = result.transactions
        logger.info(f"Parsed {len(transactions)} transactions from {pdf_path}")

        reports_dir = Path(
            f"/home/ryzen/projects/home-ai/finance-agent/data/reports/{doc_id}"
        )
        reports_dir.mkdir(parents=True, exist_ok=True)

        with open(reports_dir / "transactions.json", "w") as f:
            json.dump(transactions, f, indent=2, default=str)

        if result.phinance_structured_response:
            with open(reports_dir / "analysis.json", "w") as f:
                json.dump(result.phinance_structured_response, f, indent=2, default=str)

        job["status"] = "completed"
        job["completed_at"] = datetime.utcnow().isoformat()
        job["transaction_count"] = len(transactions)
        job["reports_dir"] = str(reports_dir)

        _save_job(job)
        logger.info(
            f"Analysis completed for {doc_id}: {len(transactions)} transactions"
        )

    except Exception as e:
        logger.error(f"Analysis failed for {doc_id}: {e}")
        job["status"] = "failed"
        job["error"] = str(e)
        job["completed_at"] = datetime.utcnow().isoformat()
        _save_job(job)


@app.post("/analyze-stage-ab")
async def analyze_stage_ab(req: AnalyzeRequest):
    """Stage A/B: Extract metadata and structure preview from uploaded document."""
    doc_id = req.doc_id
    logger.info(f"Stage A/B analysis requested for {doc_id}")

    uploads_dir = Path("/home/ryzen/projects/home-ai/finance-agent/data/uploads")
    pdf_files = list(uploads_dir.glob(f"{doc_id}*.pdf"))

    if not pdf_files:
        pdf_files = list(uploads_dir.glob(f"*{doc_id}*.pdf"))

    if not pdf_files:
        raise HTTPException(
            status_code=404, detail=f"PDF not found for doc_id: {doc_id}"
        )

    pdf_path = pdf_files[0]

    try:
        import fitz

        doc = fitz.open(str(pdf_path))
        pages = len(doc)
        first_page_text = doc[0].get_text()[:2000] if pages > 0 else ""
        doc.close()
    except Exception as e:
        logger.error(f"Failed to read PDF: {e}")
        pages = 0
        first_page_text = ""

    institution = "Unknown"
    statement_type = "unknown"
    if "apple card" in first_page_text.lower():
        institution = "Apple Card"
        statement_type = "apple_card"
    elif "chase" in first_page_text.lower():
        institution = "Chase"
        statement_type = "bank_statement"

    job_id = f"job-{doc_id}-{datetime.utcnow().strftime('%H%M%S')}"
    job = {
        "job_id": job_id,
        "doc_id": doc_id,
        "status": "pending",
        "consent_given": 0,
        "filename": pdf_path.name,
        "pages": pages,
        "institution": institution,
        "statement_type": statement_type,
        "pdf_path": str(pdf_path),
    }
    _save_job(job)

    return {
        "doc_id": doc_id,
        "filename": pdf_path.name,
        "pages": pages,
        "institution": institution,
        "statement_type": statement_type,
        "synopsis": f"Document appears to be a {institution} statement with {pages} pages.",
        "key_sections": ["Transactions", "Summary", "Account Details"],
        "timeframe": None,
    }


@app.post("/analyze-confirm")
async def analyze_confirm(req: AnalyzeRequest):
    """Confirm and start full analysis after user consent."""
    doc_id = req.doc_id
    logger.info(f"Analysis confirmation for {doc_id}")

    job = _get_job(doc_id)

    if not job:
        uploads_dir = Path("/home/ryzen/projects/home-ai/finance-agent/data/uploads")
        pdf_files = list(uploads_dir.glob(f"*{doc_id}*.pdf"))
        if not pdf_files:
            raise HTTPException(
                status_code=404, detail="Job record not found; upload required"
            )

        pdf_path = pdf_files[0]
        job_id = f"job-{doc_id}-{datetime.utcnow().strftime('%H%M%S')}"
        job = {
            "job_id": job_id,
            "doc_id": doc_id,
            "status": "pending",
            "consent_given": 1,
            "pdf_path": str(pdf_path),
        }
        _save_job(job)

    if job.get("consent_given") != 1:
        if FA_STORAGE_AVAILABLE:
            try:
                fa_storage.init_db()
                db_job = fa_storage.load_job_by_doc_id(doc_id)
                if db_job and db_job.get("consent_given") == 1:
                    job["consent_given"] = 1
                    _save_job(job)
            except Exception:
                pass

    if job.get("consent_given") != 1:
        return {
            "status": "consent_required",
            "message": "Consent required before analysis",
        }

    if job.get("status") == "running":
        return {"status": "already_running", "job_id": job.get("job_id")}

    if job.get("status") == "completed":
        return {"status": "already_completed", "job_id": job.get("job_id")}

    pdf_path = job.get("pdf_path")
    if not pdf_path:
        uploads_dir = Path("/home/ryzen/projects/home-ai/finance-agent/data/uploads")
        pdf_files = list(uploads_dir.glob(f"*{doc_id}*.pdf"))
        if pdf_files:
            pdf_path = str(pdf_files[0])
            job["pdf_path"] = pdf_path

    if not pdf_path or not Path(pdf_path).exists():
        raise HTTPException(status_code=404, detail="PDF file not found")

    thread = threading.Thread(target=_run_phinance_analysis, args=(job, pdf_path))
    thread.start()

    return {"status": "started", "job_id": job.get("job_id"), "doc_id": doc_id}


class BatchAnalyzeRequest(BaseModel):
    doc_ids: List[str]
    max_concurrent: int = 2


@app.post("/analyze-batch")
async def analyze_batch(req: BatchAnalyzeRequest):
    """Process multiple PDFs in parallel with controlled concurrency."""
    doc_ids = req.doc_ids
    max_concurrent = min(req.max_concurrent, 4)

    if not doc_ids:
        raise HTTPException(status_code=400, detail="No doc_ids provided")

    uploads_dir = Path("/home/ryzen/projects/home-ai/finance-agent/data/uploads")
    results = []
    jobs_to_process = []

    for doc_id in doc_ids:
        if FA_STORAGE_AVAILABLE:
            fa_storage.init_db()
            if fa_storage.has_transactions_for_doc(doc_id):
                results.append(
                    {
                        "doc_id": doc_id,
                        "status": "cached",
                        "message": "Transactions already extracted",
                    }
                )
                continue

        pdf_files = list(uploads_dir.glob(f"*{doc_id}*.pdf"))
        if not pdf_files:
            results.append(
                {"doc_id": doc_id, "status": "error", "error": "PDF not found"}
            )
            continue

        pdf_path = str(pdf_files[0])
        job_id = f"job-{doc_id}-{datetime.utcnow().strftime('%H%M%S')}"
        job = {
            "job_id": job_id,
            "doc_id": doc_id,
            "status": "queued",
            "consent_given": 1,
            "pdf_path": pdf_path,
        }
        _save_job(job)
        jobs_to_process.append((job, pdf_path))
        results.append({"doc_id": doc_id, "job_id": job_id, "status": "queued"})

    if jobs_to_process:

        def process_single(args):
            job, pdf_path = args
            _run_phinance_analysis(job, pdf_path)
            return job["doc_id"]

        for job, pdf_path in jobs_to_process:
            _pdf_executor.submit(process_single, (job, pdf_path))

    return {
        "batch_id": f"batch-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
        "total": len(doc_ids),
        "queued": len(jobs_to_process),
        "cached": sum(1 for r in results if r.get("status") == "cached"),
        "errors": sum(1 for r in results if r.get("status") == "error"),
        "results": results,
    }


@app.get("/api/transactions")
async def get_transactions_paginated(
    page: int = 1,
    page_size: int = 50,
    doc_id: Optional[str] = None,
    category: Optional[str] = None,
    merchant: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Paginated transactions endpoint with filtering for lazy loading."""
    reports_base = Path("/home/ryzen/projects/home-ai/finance-agent/data/reports")
    all_transactions = []

    if doc_id:
        report_dirs = [reports_base / doc_id]
    else:
        report_dirs = [d for d in reports_base.iterdir() if d.is_dir()]

    for report_dir in report_dirs:
        tx_file = report_dir / "transactions.json"
        if tx_file.exists():
            try:
                with open(tx_file) as f:
                    txs = json.load(f)
                    for tx in txs:
                        tx["source_doc"] = report_dir.name
                    all_transactions.extend(txs)
            except Exception as e:
                logger.warning(f"Failed to load {tx_file}: {e}")

    if category:
        cat_lower = category.lower()
        all_transactions = [
            t
            for t in all_transactions
            if cat_lower in (t.get("category") or "").lower()
        ]

    if merchant:
        merch_lower = merchant.lower()
        all_transactions = [
            t
            for t in all_transactions
            if merch_lower in (t.get("merchant") or "").lower()
        ]

    if date_from:
        all_transactions = [
            t for t in all_transactions if (t.get("date") or "") >= date_from
        ]

    if date_to:
        all_transactions = [
            t for t in all_transactions if (t.get("date") or "") <= date_to
        ]

    all_transactions.sort(key=lambda x: x.get("date", ""), reverse=True)

    total = len(all_transactions)
    total_pages = (total + page_size - 1) // page_size
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_data = all_transactions[start_idx:end_idx]

    return {
        "transactions": page_data,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }


@app.get("/analysis-status/{doc_id}")
async def analysis_status(doc_id: str):
    """Get the current status of an analysis job."""
    job = _get_job(doc_id)
    if not job:
        raise HTTPException(status_code=404, detail="Analysis job not found")

    response = {
        "doc_id": doc_id,
        "job_id": job.get("job_id"),
        "status": job.get("status", "unknown"),
    }

    if job.get("status") == "completed":
        response["completed_at"] = job.get("completed_at")
        response["transaction_count"] = job.get("transaction_count", 0)
        response["reports_dir"] = job.get("reports_dir")
    elif job.get("status") == "failed":
        response["error"] = job.get("error")
    elif job.get("status") == "running":
        response["started_at"] = job.get("started_at")

    return response


@app.post("/api/chat")
async def api_chat(request: Request):
    """Proxy chat requests to SOA1 API."""
    try:
        body = await request.json()
        soa1_url = config.services.get("api", "http://localhost:8001")
        resp = requests.post(f"{soa1_url}/api/chat", json=body, timeout=120)
        return resp.json()
    except Exception as e:
        logger.error(f"Chat proxy error: {e}")
        return {
            "response": "Sorry, I encountered an error processing your request.",
            "error": str(e),
        }


@app.post("/api/proxy/upload")
async def api_proxy_upload(file: UploadFile = File(...)):
    """Proxy file upload to SOA1 API."""
    try:
        soa1_url = config.services.get("api", "http://localhost:8001")

        # Read file content
        content = await file.read()

        # Prepare files dict for requests
        files = {"file": (file.filename, content, file.content_type)}

        # Forward to SOA1 API
        resp = requests.post(f"{soa1_url}/upload-pdf", files=files, timeout=120)

        # Return response
        return resp.json()
    except Exception as e:
        logger.error(f"Upload proxy error: {e}")
        return {"status": "error", "message": f"Proxy upload failed: {str(e)}"}


# =============================================================================
# End Finance Analysis Endpoints
# =============================================================================


# Create default templates if they don't exist
def create_default_templates():
    """Create default HTML templates"""
    template_dir = "templates"
    os.makedirs(template_dir, exist_ok=True)

    # Main template
    main_template = """<!DOCTYPE html>
<html>
<head>
    <title>{{ title }}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        header {{
            background: white;
            padding: 20px 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        h1 {{
            color: #667eea;
            font-size: 28px;
            font-weight: 600;
        }}
        
        .tailscale-info {{
            background: #f8f9fa;
            padding: 10px 20px;
            border-radius: 25px;
            font-size: 14px;
            color: #666;
        }}
        
        .system-info {{
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }}
        
        .status-badge {{
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 14px;
            margin-left: 10px;
        }}
        
        .status-operational {{
            background: #d4edda;
            color: #155724;
        }}
        
        .status-degraded {{
            background: #fff3cd;
            color: #856404;
        }}
        
        .status-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        
        .status-item {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
        }}
        
        .status-label {{
            font-size: 14px;
            color: #666;
            margin-bottom: 8px;
        }}
        
        .status-value {{
            font-size: 24px;
            font-weight: 600;
            color: #333;
        }}
        
        .services-section {{
            margin-top: 30px;
        }}
        
        h2 {{
            color: white;
            font-size: 24px;
            margin-bottom: 20px;
        }}
        
        .service-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }}
        
        .service-card {{
            background: white;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
            transition: transform 0.3s ease;
        }}
        
        .service-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        }}
        
        .service-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}
        
        .service-name {{
            font-size: 18px;
            font-weight: 600;
            color: #333;
        }}
        
        .service-required {{
            font-size: 12px;
            background: #e3f2fd;
            color: #1976d2;
            padding: 4px 8px;
            border-radius: 10px;
        }}
        
        .service-status {{
            font-size: 14px;
            font-weight: 600;
            padding: 6px 12px;
            border-radius: 20px;
        }}
        
        .status-running {{
            background: #d4edda;
            color: #155724;
        }}
        
        .status-stopped {{
            background: #f8d7da;
            color: #721c24;
        }}
        
        .status-error {{
            background: #fff3cd;
            color: #856404;
        }}
        
        .status-unknown {{
            background: #e2e3e5;
            color: #383d41;
        }}
        
        .service-details {{
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #eee;
        }}
        
        .detail-row {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 14px;
            color: #666;
        }}
        
        .nav-buttons {{
            display: flex;
            gap: 10px;
            margin-top: 20px;
        }}
        
        .btn {{
            padding: 12px 24px;
            border: none;
            border-radius: 25px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 14px;
        }}
        
        .btn-primary {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        
        .btn-secondary {{
            background: white;
            color: #667eea;
            border: 2px solid #667eea;
        }}
        
        .btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }}
        
        .last-updated {{
            text-align: center;
            margin-top: 30px;
            color: white;
            font-size: 14px;
            opacity: 0.8;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🌐 SOA1 Web UI - Tailscale Edition</h1>
            {% if tailscale_ip %}
            <div class="tailscale-info">
                🔒 Tailscale: {{ tailscale_ip }} | Status: <span class="status-badge status-{{ overall_status }}">{{ overall_status }}</span>
            </div>
            {% endif %}
        </header>
        
        <div class="system-info">
            <h2>📊 System Overview</h2>
            <div class="status-grid">
                <div class="status-item">
                    <div class="status-label">CPU Usage</div>
                    <div class="status-value">{{ "%.1f"|format(system_status.cpu_usage) }}%</div>
                </div>
                <div class="status-item">
                    <div class="status-label">Memory Usage</div>
                    <div class="status-value">{{ "%.1f"|format(system_status.memory_usage) }}%</div>
                </div>
                <div class="status-item">
                    <div class="status-label">Disk Usage</div>
                    <div class="status-value">{{ "%.1f"|format(system_status.disk_usage) }}%</div>
                </div>
                <div class="status-item">
                    <div class="status-label">Required Services</div>
                    <div class="status-value">{{ running_required }}/{{ required_count }}</div>
                </div>
            </div>
        </div>
        
        <div class="services-section">
            <h2>🔧 SOA1 Services</h2>
            <div class="service-grid">
                {% for service in services %}
                <div class="service-card">
                    <div class="service-header">
                        <div>
                            <div class="service-name">{{ service.display_name }}</div>
                            {% if not service.required %}
                            <div class="service-required">Optional</div>
                            {% endif %}
                        </div>
                        <div class="service-status status-{{ service.status }}">{{ service.status }}</div>
                    </div>
                    
                    <div class="service-details">
                        {% if service.port %}
                        <div class="detail-row">
                            <span>Port:</span>
                            <span>{{ service.port }}</span>
                        </div>
                        {% endif %}
                        
                        {% if service.pid %}
                        <div class="detail-row">
                            <span>PID:</span>
                            <span>{{ service.pid }}</span>
                        </div>
                        {% endif %}
                        
                        {% if service.cpu_usage > 0 %}
                        <div class="detail-row">
                            <span>CPU:</span>
                            <span>{{ "%.1f"|format(service.cpu_usage) }}%</span>
                        </div>
                        {% endif %}
                        
                        {% if service.memory_usage > 0 %}
                        <div class="detail-row">
                            <span>Memory:</span>
                            <span>{{ "%.1f"|format(service.memory_usage) }} MB</span>
                        </div>
                        {% endif %}
                        
                        {% if service.error %}
                        <div class="detail-row" style="color: #dc3545;">
                            <span>Error:</span>
                            <span>{{ service.error }}</span>
                        </div>
                        {% endif %}
                    </div>
                </div>
                {% endfor %}
            </div>
            
            <div class="nav-buttons">
                <button class="btn btn-primary" onclick="window.location.reload()">🔄 Refresh Status</button>
                <button class="btn btn-secondary" onclick="window.location='/services'">📋 Services Page</button>
                <button class="btn btn-secondary" onclick="window.location='/status'">📊 System Status</button>
            </div>
        </div>
        
        <div class="last-updated">
            Last updated: {{ last_updated }}
        </div>
    </div>
</body>
</html>"""

    with open(f"{template_dir}/index.html", "w") as f:
        f.write(main_template)

    # Services template
    services_template = """<!DOCTYPE html>
<html>
<head>
    <title>{{ title }}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        header {{
            background: white;
            padding: 20px 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        h1 {{
            color: #667eea;
            font-size: 28px;
            font-weight: 600;
        }}
        
        .back-btn {{
            background: #f8f9fa;
            padding: 10px 20px;
            border-radius: 25px;
            text-decoration: none;
            color: #667eea;
            font-weight: 600;
        }}
        
        .service-table {{
            background: white;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        
        th, td {{
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        
        th {{
            background: #f8f9fa;
            font-weight: 600;
            color: #333;
        }}
        
        tr:hover {{
            background: #f8f9fa;
        }}
        
        .status-badge {{
            padding: 6px 12px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 12px;
        }}
        
        .status-running {{
            background: #d4edda;
            color: #155724;
        }}
        
        .status-stopped {{
            background: #f8d7da;
            color: #721c24;
        }}
        
        .status-error {{
            background: #fff3cd;
            color: #856404;
        }}
        
        .status-unknown {{
            background: #e2e3e5;
            color: #383d41;
        }}
        
        .nav-buttons {{
            display: flex;
            gap: 10px;
            margin-top: 20px;
        }}
        
        .btn {{
            padding: 12px 24px;
            border: none;
            border-radius: 25px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 14px;
        }}
        
        .btn-primary {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        
        .btn-secondary {{
            background: white;
            color: #667eea;
            border: 2px solid #667eea;
        }}
        
        .last-updated {{
            text-align: center;
            margin-top: 30px;
            color: white;
            font-size: 14px;
            opacity: 0.8;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔧 SOA1 Services</h1>
            <a href="/" class="back-btn">← Back to Dashboard</a>
        </header>
        
        <div class="service-table">
            <table>
                <thead>
                    <tr>
                        <th>Service</th>
                        <th>Status</th>
                        <th>Port</th>
                        <th>PID</th>
                        <th>CPU</th>
                        <th>Memory</th>
                        <th>Required</th>
                    </tr>
                </thead>
                <tbody>
                    {% for service in services %}
                    <tr>
                        <td>{{ service.display_name }}</td>
                        <td><span class="status-badge status-{{ service.status }}">{{ service.status }}</span></td>
                        <td>{{ service.port }}</td>
                        <td>{{ service.pid if service.pid else '-' }}</td>
                        <td>{{ "%.1f"|format(service.cpu_usage) if service.cpu_usage > 0 else '-' }}%</td>
                        <td>{{ "%.1f"|format(service.memory_usage) if service.memory_usage > 0 else '-' }} MB</td>
                        <td>{{ 'Yes' if service.required else 'No' }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        <div class="nav-buttons">
            <button class="btn btn-primary" onclick="window.location.reload()">🔄 Refresh</button>
            <button class="btn btn-secondary" onclick="window.location='/'">🏠 Dashboard</button>
            <button class="btn btn-secondary" onclick="window.location='/status'">📊 System Status</button>
        </div>
        
        <div class="last-updated">
            Last updated: {{ last_updated }}
        </div>
    </div>
</body>
</html>"""

    with open(f"{template_dir}/services.html", "w") as f:
        f.write(services_template)

    # Status template
    status_template = """<!DOCTYPE html>
<html>
<head>
    <title>{{ title }}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        header {{
            background: white;
            padding: 20px 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        h1 {{
            color: #667eea;
            font-size: 28px;
            font-weight: 600;
        }}
        
        .back-btn {{
            background: #f8f9fa;
            padding: 10px 20px;
            border-radius: 25px;
            text-decoration: none;
            color: #667eea;
            font-weight: 600;
        }}
        
        .status-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .status-card {{
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            text-align: center;
        }}
        
        .status-label {{
            font-size: 14px;
            color: #666;
            margin-bottom: 10px;
        }}
        
        .status-value {{
            font-size: 32px;
            font-weight: 600;
            color: #333;
        }}
        
        .system-info {{
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }}
        
        .info-row {{
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #eee;
        }}
        
        .info-row:last-child {{
            border-bottom: none;
        }}
        
        .info-label {{
            color: #666;
            font-weight: 500;
        }}
        
        .info-value {{
            color: #333;
            font-weight: 600;
        }}
        
        .nav-buttons {{
            display: flex;
            gap: 10px;
            margin-top: 20px;
        }}
        
        .btn {{
            padding: 12px 24px;
            border: none;
            border-radius: 25px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 14px;
        }}
        
        .btn-primary {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        
        .btn-secondary {{
            background: white;
            color: #667eea;
            border: 2px solid #667eea;
        }}
        
        .last-updated {{
            text-align: center;
            margin-top: 30px;
            color: white;
            font-size: 14px;
            opacity: 0.8;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 System Status</h1>
            <a href="/" class="back-btn">← Back to Dashboard</a>
        </header>
        
        <div class="status-cards">
            <div class="status-card">
                <div class="status-label">CPU Usage</div>
                <div class="status-value">{{ "%.1f"|format(system_status.cpu_usage) }}%</div>
            </div>
            <div class="status-card">
                <div class="status-label">Memory Usage</div>
                <div class="status-value">{{ "%.1f"|format(system_status.memory_usage) }}%</div>
            </div>
            <div class="status-card">
                <div class="status-label">Disk Usage</div>
                <div class="status-value">{{ "%.1f"|format(system_status.disk_usage) }}%</div>
            </div>
            <div class="status-card">
                <div class="status-label">Uptime</div>
                <div class="status-value">{{ system_status.uptime }}</div>
            </div>
        </div>
        
        <div class="system-info">
            <h2 style="margin-bottom: 15px;">📋 System Information</h2>
            
            <div class="info-row">
                <span class="info-label">Tailscale IP:</span>
                <span class="info-value">{{ system_status.tailscale_ip if system_status.tailscale_ip else 'Not connected' }}</span>
            </div>
            
            <div class="info-row">
                <span class="info-label">Total Processes:</span>
                <span class="info-value">{{ process_count }}</span>
            </div>
            
            <div class="info-row">
                <span class="info-label">System Load:</span>
                <span class="info-value">Coming soon</span>
            </div>
        </div>
        
        <div class="nav-buttons">
            <button class="btn btn-primary" onclick="window.location.reload()">🔄 Refresh</button>
            <button class="btn btn-secondary" onclick="window.location='/'">🏠 Dashboard</button>
            <button class="btn btn-secondary" onclick="window.location='/services'">🔧 Services</button>
        </div>
        
        <div class="last-updated">
            Last updated: {{ last_updated }}
        </div>
    </div>
</body>
</html>"""

    with open(f"{template_dir}/status.html", "w") as f:
        f.write(status_template)


# Create default config if it doesn't exist
if not os.path.exists(CONFIG_FILE):
    default_config = """
# SOA1 Web UI Configuration
# Tailscale Edition

# Server settings
server:
  host: "0.0.0.0"  # Listen on all interfaces for Tailscale
  port: 8080       # Port for web UI

# SOA1 Services
services:
  api: "http://localhost:8001"
  web_interface: "http://localhost:8002"
  service_monitor: "http://localhost:8003"
  memlayer: "http://localhost:8000"

# Tailscale settings
tailscale:
  enabled: true
  # Allow only specific Tailscale IPs (optional)
  allowed_ips:
    - "100.64.0.0/10"  # Tailscale IP range

# Security
security:
  # IP-based access control (Tailscale IPs only)
  ip_whitelist:
    - "100.64.0.0/10"

# Features
features:
  service_control: true
  monitoring: true
  logging: true
"""
    with open(CONFIG_FILE, "w") as f:
        f.write(default_config)

# Create default templates - DISABLED: using existing templates in templates/ dir
# create_default_templates()

if __name__ == "__main__":
    logger.info("🚀 Starting SOA1 Web UI - Tailscale Edition...")
    logger.info(
        f"🌐 Dashboard will be available at http://{config.server['host']}:{config.server['port']}"
    )

    # Get Tailscale IP
    tailscale_ip = get_tailscale_ip()
    if tailscale_ip:
        logger.info(f"🔒 Tailscale IP: {tailscale_ip}")
        logger.info(
            f"🌐 Tailscale access: http://{tailscale_ip}:{config.server['port']}"
        )
    else:
        logger.warning("⚠️ Tailscale IP not detected. Make sure Tailscale is running.")

    uvicorn.run(
        app, host=config.server["host"], port=config.server["port"], reload=False
    )
