#!/usr/bin/env python3
"""
SOA1 Service Monitor Web Interface
Comprehensive dashboard to monitor all services required for SOA1 operation
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import os
import subprocess
import socket
import psutil
import logging
from datetime import datetime
import yaml
import requests
from typing import Dict, List, Optional

# Set up logging
from .utils.logging_utils import setup_logging

logger = setup_logging("service_monitor")

# Create app
app = FastAPI(title="SOA1 Service Monitor")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Configuration
CONFIG_FILE = "config.yaml"
SERVICE_MONITOR_PORT = 8003


class ServiceStatus:
    """Service status information"""

    def __init__(self, name: str, required: bool = True):
        self.name = name
        self.required = required
        self.status = "unknown"
        self.port = None
        self.pid = None
        self.cpu_usage = 0.0
        self.memory_usage = 0.0
        self.last_checked = None
        self.error = None
        self.url = None


class SystemStatus:
    """System status information"""

    def __init__(self):
        self.cpu_usage = 0.0
        self.memory_usage = 0.0
        self.disk_usage = 0.0
        self.uptime = ""
        self.last_checked = None


def check_service_status(service: ServiceStatus) -> ServiceStatus:
    """Check the status of a service"""
    try:
        if service.name == "nginx":
            return check_nginx_service(service)
        elif service.name == "ollama":
            return check_ollama_service(service)
        elif service.name == "pulseaudio":
            return check_pulseaudio_service(service)
        elif service.name == "soa1_api":
            return check_soa1_api_service(service)
        elif service.name == "memlayer":
            return check_memlayer_service(service)
        elif service.name == "redis":
            return check_redis_service(service)
        else:
            service.status = "unknown"
            service.last_checked = datetime.now().isoformat()
            return service
    except Exception as e:
        service.status = "error"
        service.error = str(e)
        service.last_checked = datetime.now().isoformat()
        return service


def check_nginx_service(service: ServiceStatus) -> ServiceStatus:
    """Check Nginx service status"""
    service.port = 80
    service.url = f"http://localhost:{service.port}"

    try:
        # Check if Nginx process is running
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if "nginx" in proc.info["name"]:
                    service.pid = proc.info["pid"]
                    service.cpu_usage = proc.cpu_percent(interval=0.1)
                    service.memory_usage = proc.memory_info().rss / 1024 / 1024  # MB
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if service.pid:
            # Try to connect to Nginx
            try:
                response = requests.get(
                    f"{service.url}", timeout=2, allow_redirects=False
                )
                if response.status_code < 400:
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

    service.last_checked = datetime.now().isoformat()
    return service


def check_ollama_service(service: ServiceStatus) -> ServiceStatus:
    """Check Ollama service status"""
    service.port = 11434
    service.url = f"http://localhost:{service.port}"

    try:
        # Check if process is running
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if "ollama" in " ".join(proc.info["cmdline"] or []):
                    service.pid = proc.info["pid"]
                    service.cpu_usage = proc.cpu_percent(interval=0.1)
                    service.memory_usage = proc.memory_info().rss / 1024 / 1024  # MB
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if service.pid:
            # Try to connect to the API
            try:
                response = requests.get(f"{service.url}/api/tags", timeout=2)
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

    service.last_checked = datetime.now().isoformat()
    return service


def check_pulseaudio_service(service: ServiceStatus) -> ServiceStatus:
    """Check PulseAudio service status"""
    service.required = False  # Not strictly required but nice to have

    try:
        # Check if process is running
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if "pulseaudio" in " ".join(proc.info["cmdline"] or []):
                    service.pid = proc.info["pid"]
                    service.cpu_usage = proc.cpu_percent(interval=0.1)
                    service.memory_usage = proc.memory_info().rss / 1024 / 1024  # MB
                    service.status = "running"
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if not service.pid:
            service.status = "stopped"

    except Exception as e:
        service.status = "error"
        service.error = str(e)

    service.last_checked = datetime.now().isoformat()
    return service


def check_soa1_api_service(service: ServiceStatus) -> ServiceStatus:
    """Check SOA1 API service status"""
    try:
        # Load config to get port
        with open(CONFIG_FILE, "r") as f:
            config = yaml.safe_load(f)
            service.port = config["server"]["port"]
            service.url = f"http://localhost:{service.port}"
    except Exception as e:
        service.status = "config_error"
        service.error = f"Cannot read config: {e}"
        service.last_checked = datetime.now().isoformat()
        return service

    try:
        # Check if process is running
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if "api.py" in " ".join(proc.info["cmdline"] or []):
                    service.pid = proc.info["pid"]
                    service.cpu_usage = proc.cpu_percent(interval=0.1)
                    service.memory_usage = proc.memory_info().rss / 1024 / 1024  # MB
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if service.pid:
            # Try to connect to the API
            try:
                response = requests.get(f"{service.url}/status", timeout=2)
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

    service.last_checked = datetime.now().isoformat()
    return service


def check_memlayer_service(service: ServiceStatus) -> ServiceStatus:
    """Check Memlayer service status"""
    service.port = 8000
    service.url = f"http://localhost:{service.port}"

    try:
        # Check if process is running
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if "memlayer" in " ".join(proc.info["cmdline"] or []):
                    service.pid = proc.info["pid"]
                    service.cpu_usage = proc.cpu_percent(interval=0.1)
                    service.memory_usage = proc.memory_info().rss / 1024 / 1024  # MB
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if service.pid:
            # Try to connect to the API
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

    service.last_checked = datetime.now().isoformat()
    return service


def check_redis_service(service: ServiceStatus) -> ServiceStatus:
    """Check Redis service status"""
    service.port = 6379

    try:
        # Check if process is running
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if "redis" in " ".join(proc.info["cmdline"] or []):
                    service.pid = proc.info["pid"]
                    service.cpu_usage = proc.cpu_percent(interval=0.1)
                    service.memory_usage = proc.memory_info().rss / 1024 / 1024  # MB
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if service.pid:
            # Try to connect to Redis
            try:
                import redis

                r = redis.Redis(host="localhost", port=service.port, socket_timeout=2)
                if r.ping():
                    service.status = "running"
                else:
                    service.status = "unresponsive"
            except Exception:
                service.status = "unresponsive"
        else:
            service.status = "stopped"

    except Exception as e:
        service.status = "error"
        service.error = str(e)

    service.last_checked = datetime.now().isoformat()
    return service


def get_system_status() -> SystemStatus:
    """Get overall system status"""
    status = SystemStatus()

    try:
        # CPU usage
        status.cpu_usage = psutil.cpu_percent(interval=1)

        # Memory usage
        memory = psutil.virtual_memory()
        status.memory_usage = memory.percent

        # Disk usage
        disk = psutil.disk_usage("/")
        status.disk_usage = disk.percent

        # Uptime
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        status.uptime = str(uptime).split(".")[0]

        status.last_checked = datetime.now().isoformat()

    except Exception as e:
        logger.error(f"Error getting system status: {e}")

    return status


@app.get("/")
def home(request: Request):
    """Home page with service status dashboard"""
    # Define all services to monitor
    services = {
        "nginx": ServiceStatus("Nginx (Web Server)", required=True),
        "ollama": ServiceStatus("Ollama (LLM)", required=True),
        "soa1_api": ServiceStatus("SOA1 API", required=True),
        "memlayer": ServiceStatus("Memlayer", required=True),
        "pulseaudio": ServiceStatus("PulseAudio", required=False),
        "redis": ServiceStatus("Redis", required=False),
    }

    # Check all services
    for service_name, service in services.items():
        services[service_name] = check_service_status(service)

    # Get system status
    system_status = get_system_status()

    # Calculate overall status
    required_services = [s for s in services.values() if s.required]
    running_required = [s for s in required_services if s.status == "running"]

    overall_status = (
        "operational" if len(running_required) == len(required_services) else "degraded"
    )

    return templates.TemplateResponse(
        "service_dashboard.html",
        {
            "request": request,
            "title": "SOA1 Service Monitor",
            "services": services,
            "system_status": system_status,
            "overall_status": overall_status,
            "required_count": len(required_services),
            "running_required": len(running_required),
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )


@app.get("/services")
def services_api():
    """API endpoint for service status"""
    services = {
        "nginx": check_service_status(
            ServiceStatus("Nginx (Web Server)", required=True)
        ),
        "ollama": check_service_status(ServiceStatus("Ollama (LLM)", required=True)),
        "soa1_api": check_service_status(ServiceStatus("SOA1 API", required=True)),
        "memlayer": check_service_status(ServiceStatus("Memlayer", required=True)),
        "pulseaudio": check_service_status(ServiceStatus("PulseAudio", required=False)),
        "redis": check_service_status(ServiceStatus("Redis", required=False)),
    }

    system_status = get_system_status()

    return {
        "services": {
            name: {
                "status": s.status,
                "port": s.port,
                "pid": s.pid,
                "cpu_usage": s.cpu_usage,
                "memory_usage": s.memory_usage,
                "error": s.error,
                "last_checked": s.last_checked,
            }
            for name, s in services.items()
        },
        "system": {
            "cpu_usage": system_status.cpu_usage,
            "memory_usage": system_status.memory_usage,
            "disk_usage": system_status.disk_usage,
            "uptime": system_status.uptime,
            "last_checked": system_status.last_checked,
        },
    }


# -----------------------------
# Monitoring API endpoints
# -----------------------------
from .utils.file_utils import tail_lines
from .utils.logging_utils import sanitize_text
from pathlib import Path
import importlib
import sys
import json

# Finance data directories (configurable via FINANCE_DATA_DIR env var)
FINANCE_DATA_DIR = Path(
    os.environ.get(
        "FINANCE_DATA_DIR",
        str(Path(__file__).resolve().parents[1] / "finance-agent" / "data"),
    )
)
FINANCE_UPLOAD_DIR = FINANCE_DATA_DIR / "uploads"
FINANCE_REPORTS_DIR = FINANCE_DATA_DIR / "reports"


def _import_fa_storage():
    """Import the finance-agent storage module robustly."""
    try:
        from home_ai.finance_agent.src import storage as fa_storage

        return fa_storage
    except Exception:
        try:
            # Add the finance-agent src directory to sys.path and import
            fa_src_path = Path(__file__).resolve().parents[1] / "finance-agent" / "src"
            if str(fa_src_path) not in sys.path:
                sys.path.insert(0, str(fa_src_path))
            fa_storage = importlib.import_module("storage")
            return fa_storage
        except Exception as exc:
            logger.warning("Could not import finance storage module: %s", exc)
            return None


def _load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning("Could not load config: %s", e)
        return {}


def is_allowed_ip(client_ip: str) -> bool:
    """Check if client IP is allowed via config.yaml ip_whitelist or localhost."""
    if client_ip in ["127.0.0.1", "localhost", "::1"]:
        return True

    config = _load_config()
    allowed_ranges = config.get("security", {}).get("ip_whitelist", ["100.64.0.0/10"])

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


@app.get("/monitor/summary")
def monitor_summary(request: Request):
    """Return aggregated system and finance job summary."""
    client_ip = request.client.host
    if not is_allowed_ip(client_ip):
        raise HTTPException(status_code=403, detail="Access denied: IP not allowed")

    services = services_api().get("services", {})
    system = get_system_status()

    fa_storage = _import_fa_storage()
    jobs = []
    try:
        if fa_storage:
            jobs = fa_storage.get_all_jobs()
    except Exception as exc:
        logger.warning("Failed to query finance jobs: %s", exc)

    counts = {
        "total": len(jobs),
        "pending": sum(1 for j in jobs if j.get("status") == "pending"),
        "running": sum(1 for j in jobs if j.get("status") == "running"),
        "completed": sum(1 for j in jobs if j.get("status") == "completed"),
        "failed": sum(1 for j in jobs if j.get("status") == "failed"),
    }

    # Last report timestamp
    latest_report_ts = None
    try:
        if FINANCE_REPORTS_DIR.exists():
            report_dirs = sorted(
                [d for d in FINANCE_REPORTS_DIR.iterdir() if d.is_dir()],
                key=lambda d: d.stat().st_mtime,
                reverse=True,
            )
            if report_dirs:
                latest_dir = report_dirs[0]
                latest_report_ts = latest_dir.stat().st_mtime
    except Exception as exc:
        logger.warning("Failed to determine latest report: %s", exc)

    return {
        "services": services,
        "system": {
            "cpu_usage": system.cpu_usage,
            "memory_usage": system.memory_usage,
            "disk_usage": system.disk_usage,
            "uptime": system.uptime,
            "last_checked": system.last_checked,
        },
        "finance": {
            "uploads_dir": str(FINANCE_UPLOAD_DIR),
            "reports_dir": str(FINANCE_REPORTS_DIR),
            "jobs_summary": counts,
            "latest_report_mtime": latest_report_ts,
        },
    }


@app.get("/monitor/logs")
def monitor_logs(request: Request):
    """List available monitor log files."""
    client_ip = request.client.host
    if not is_allowed_ip(client_ip):
        raise HTTPException(status_code=403, detail="Access denied: IP not allowed")

    log_dir = getattr(logger, "_monitor_log_dir", None)
    if not log_dir:
        log_dir = os.environ.get("MONITOR_LOG_DIR") or str(
            Path(__file__).resolve().parents[2] / "soa-webui" / "logs"
        )
    log_dir = Path(log_dir)

    files = []
    try:
        if log_dir.exists():
            for f in sorted(
                log_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True
            ):
                if f.is_file():
                    files.append(
                        {
                            "name": f.name,
                            "path": str(f),
                            "size": f.stat().st_size,
                            "mtime": f.stat().st_mtime,
                        }
                    )
    except Exception as exc:
        logger.warning("Failed to list logs: %s", exc)

    return {"log_dir": str(log_dir), "files": files}


@app.get("/monitor/logs/tail")
def monitor_logs_tail(request: Request, service: str, lines: int = 200):
    """Return the last `lines` lines from a service log."""
    client_ip = request.client.host
    if not is_allowed_ip(client_ip):
        raise HTTPException(status_code=403, detail="Access denied: IP not allowed")

    lines = min(max(1, int(lines)), 2000)

    log_dir = getattr(logger, "_monitor_log_dir", None)
    if not log_dir:
        log_dir = os.environ.get("MONITOR_LOG_DIR") or str(
            Path(__file__).resolve().parents[2] / "soa-webui" / "logs"
        )
    log_path = Path(log_dir) / f"{service}.log"

    if not log_path.exists():
        raise HTTPException(status_code=404, detail=f"Log for {service} not found")

    try:
        lines_out = tail_lines(log_path, lines)
        # Sanitize the returned lines as an extra safety
        sanitized = [sanitize_text(l) for l in lines_out]
        return {"service": service, "lines": sanitized}
    except Exception as exc:
        logger.warning("Failed to tail log %s: %s", service, exc)
        raise HTTPException(status_code=500, detail="Failed to read log file")


@app.get("/monitor/finance/files")
def monitor_finance_files(request: Request):
    """List uploaded finance files."""
    client_ip = request.client.host
    if not is_allowed_ip(client_ip):
        raise HTTPException(status_code=403, detail="Access denied: IP not allowed")

    files = []
    try:
        if FINANCE_UPLOAD_DIR.exists():
            for p in sorted(
                FINANCE_UPLOAD_DIR.iterdir(),
                key=lambda x: x.stat().st_mtime,
                reverse=True,
            ):
                if p.is_file():
                    files.append(
                        {
                            "name": p.name,
                            "path": str(p),
                            "size": p.stat().st_size,
                            "mtime": p.stat().st_mtime,
                            "doc_id": p.name.split("_")[0],
                        }
                    )
    except Exception as exc:
        logger.warning("Failed to list finance files: %s", exc)

    return {"uploads_dir": str(FINANCE_UPLOAD_DIR), "files": files}


@app.get("/monitor/finance/jobs")
def monitor_finance_jobs(request: Request):
    """Return stored finance analysis jobs and counts."""
    client_ip = request.client.host
    if not is_allowed_ip(client_ip):
        raise HTTPException(status_code=403, detail="Access denied: IP not allowed")

    fa_storage = _import_fa_storage()
    if not fa_storage:
        raise HTTPException(status_code=500, detail="Finance storage not available")

    try:
        jobs = fa_storage.get_all_jobs()
        # Sanitize textual fields
        jobs_sanitized = []
        for j in jobs:
            js = {
                k: (sanitize_text(v) if isinstance(v, str) else v) for k, v in j.items()
            }
            jobs_sanitized.append(js)

        counts = {
            "total": len(jobs_sanitized),
            "pending": sum(1 for j in jobs_sanitized if j.get("status") == "pending"),
            "running": sum(1 for j in jobs_sanitized if j.get("status") == "running"),
            "completed": sum(
                1 for j in jobs_sanitized if j.get("status") == "completed"
            ),
            "failed": sum(1 for j in jobs_sanitized if j.get("status") == "failed"),
        }

        return {"jobs": jobs_sanitized, "counts": counts}
    except Exception as exc:
        logger.warning("Failed to read finance jobs: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to read jobs")


@app.get("/monitor/finance/debug")
def monitor_finance_debug(request: Request, doc_id: str, lines: int = 200):
    """Debug info for a single document (files, job record, reports, and logs)."""
    client_ip = request.client.host
    if not is_allowed_ip(client_ip):
        raise HTTPException(status_code=403, detail="Access denied: IP not allowed")

    lines = min(max(1, int(lines)), 2000)

    result = {"doc_id": doc_id}

    # Find matching upload
    try:
        matching = (
            list(FINANCE_UPLOAD_DIR.glob(f"{doc_id}_*"))
            if FINANCE_UPLOAD_DIR.exists()
            else []
        )
        result["matching_uploads"] = [str(p) for p in matching]
    except Exception as exc:
        result["matching_uploads_error"] = str(exc)

    fa_storage = _import_fa_storage()
    if fa_storage:
        try:
            job = fa_storage.load_job_by_doc_id(doc_id)
            result["job_record"] = (
                {
                    k: (sanitize_text(v) if isinstance(v, str) else v)
                    for k, v in job.items()
                }
                if job
                else None
            )
        except Exception as exc:
            result["job_error"] = str(exc)
    else:
        result["job_error"] = "finance storage not available"

    # Reports
    try:
        report_dir = FINANCE_REPORTS_DIR / doc_id
        if report_dir.exists():
            analysis_file = report_dir / "analysis.json"
            tx_file = report_dir / "transactions.json"
            result["reports"] = {
                "analysis_exists": analysis_file.exists(),
                "transactions_exists": tx_file.exists(),
            }
            if analysis_file.exists():
                try:
                    with open(analysis_file, "r", encoding="utf-8") as f:
                        a = json.load(f)
                        # keep only a few keys
                        result["analysis_preview"] = {
                            "doc_id": a.get("doc_id"),
                            "transaction_count": a.get("transaction_count")
                            or len(a.get("transactions", [])),
                            "insights": a.get("insights", [])[:5]
                            if isinstance(a.get("insights", []), list)
                            else [],
                        }
                except Exception as exc:
                    result["analysis_read_error"] = str(exc)
        else:
            result["reports"] = None
    except Exception as exc:
        result["reports_error"] = str(exc)

    # Tail relevant logs (soa-webui, api, service_monitor, finance)
    log_dir = getattr(logger, "_monitor_log_dir", None)
    if not log_dir:
        log_dir = os.environ.get("MONITOR_LOG_DIR") or str(
            Path(__file__).resolve().parents[2] / "soa-webui" / "logs"
        )
    log_dir = Path(log_dir)

    log_tails = {}
    for candidate in ["soa-webui", "api", "service_monitor", "finance"]:
        p = log_dir / f"{candidate}.log"
        if p.exists():
            try:
                log_tails[candidate] = [sanitize_text(l) for l in tail_lines(p, lines)]
            except Exception as exc:
                log_tails[candidate] = [f"error reading log: {exc}"]

    result["logs_tail"] = log_tails

    return result


@app.get("/start-services")
def start_services():
    """Attempt to start required services"""
    results = {}

    # Try to start Ollama
    try:
        result = subprocess.run(
            ["ollama", "serve"], capture_output=True, text=True, timeout=5
        )
        results["ollama"] = {
            "success": result.returncode == 0,
            "message": "Ollama started" if result.returncode == 0 else result.stderr,
        }
    except Exception as e:
        results["ollama"] = {"success": False, "message": str(e)}

    # Try to start SOA1 API
    try:
        result = subprocess.run(
            ["python3", "api.py"],
            cwd="/home/ryzen/projects/home-ai/soa1",
            capture_output=True,
            text=True,
            timeout=5,
        )
        results["soa1_api"] = {
            "success": result.returncode == 0,
            "message": "SOA1 API started" if result.returncode == 0 else result.stderr,
        }
    except Exception as e:
        results["soa1_api"] = {"success": False, "message": str(e)}

    return {"results": results}


@app.get("/health")
def health():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    logger.info("Starting SOA1 Service Monitor...")
    logger.info(
        f"Dashboard will be available at http://localhost:{SERVICE_MONITOR_PORT}"
    )

    # Create templates directory if it doesn't exist
    os.makedirs("templates", exist_ok=True)

    # Create a basic template if it doesn't exist
    template_path = "templates/service_dashboard.html"
    if not os.path.exists(template_path):
        with open(template_path, "w") as f:
            f.write("""<!DOCTYPE html>
<html>
<head>
    <title>{{ title }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .service-card { border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }
        .status-running { background-color: #d4edda; }
        .status-stopped { background-color: #f8d7da; }
        .status-error { background-color: #fff3cd; }
        .status-unknown { background-color: #e2e3e5; }
        .system-info { background-color: #f8f9fa; padding: 15px; border-radius: 5px; }
    </style>
</head>
<body>
    <h1>🌐 SOA1 Service Monitor</h1>
    <div class="system-info">
        <h3>📊 System Status</h3>
        <p>Overall: <strong>{{ overall_status }}</strong></p>
        <p>Required Services: {{ running_required }}/{{ required_count }} running</p>
        <p>CPU: {{ system_status.cpu_usage }}% | Memory: {{ system_status.memory_usage }}% | Disk: {{ system_status.disk_usage }}%</p>
        <p>Uptime: {{ system_status.uptime }}</p>
        <p>Last updated: {{ last_updated }}</p>
    </div>
    
    <h3>🔧 Service Status</h3>
    {% for name, service in services.items() %}
    <div class="service-card status-{{ service.status }}">
        <h4>{{ service.name }} {% if not service.required %}(optional){% endif %}</h4>
        <p><strong>Status:</strong> {{ service.status }}</p>
        {% if service.port %}<p><strong>Port:</strong> {{ service.port }}</p>{% endif %}
        {% if service.pid %}<p><strong>PID:</strong> {{ service.pid }}</p>{% endif %}
        {% if service.cpu_usage > 0 %}<p><strong>CPU:</strong> {{ "%.1f"|format(service.cpu_usage) }}%</p>{% endif %}
        {% if service.memory_usage > 0 %}<p><strong>Memory:</strong> {{ "%.1f"|format(service.memory_usage) }} MB</p>{% endif %}
        {% if service.error %}<p><strong>Error:</strong> {{ service.error }}</p>{% endif %}
        {% if service.url %}<p><strong>URL:</strong> <a href="{{ service.url }}" target="_blank">{{ service.url }}</a></p>{% endif %}
    </div>
    {% endfor %}
    
    <div style="margin-top: 20px;">
        <button onclick="window.location.reload()">🔄 Refresh Status</button>
        <button onclick="window.location='/services'" style="margin-left: 10px;">📋 JSON API</button>
    </div>
</body>
</html>""")

    uvicorn.run(app, host="0.0.0.0", port=SERVICE_MONITOR_PORT, reload=False)
