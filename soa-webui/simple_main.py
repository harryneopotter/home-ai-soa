#!/usr/bin/env python3
"""
SOA1 Web UI - Simple Tailscale Edition
Lightweight web interface for monitoring SOA1 services
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import os
import yaml
import logging
import psutil
import requests
import socket
from datetime import datetime
from typing import Optional, Dict, List
from pydantic import BaseModel

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("soa-webui")

# Configuration
CONFIG_FILE = "config.yaml"

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
            with open(CONFIG_FILE, 'r') as f:
                config = yaml.safe_load(f) or {}
                
            self.server.update(config.get('server', {}))
            self.services.update(config.get('services', {}))
            self.tailscale.update(config.get('tailscale', {}))
            self.security.update(config.get('security', {}))
            self.features.update(config.get('features', {}))
            
            logger.info("Configuration loaded successfully")
        except Exception as e:
            logger.warning(f"Could not load config: {e}")

# Load configuration
config = Config()

# Create FastAPI app
app = FastAPI(
    title="SOA1 Web UI - Tailscale Edition",
    description="Web interface for monitoring SOA1 services via Tailscale",
    version="1.0.0"
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def get_tailscale_ip() -> Optional[str]:
    """Get the Tailscale IP address"""
    try:
        import subprocess
        result = subprocess.run(["tailscale", "ip", "-4"], 
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    
    try:
        addrs = psutil.net_if_addrs()
        for interface, addresses in addrs.items():
            for addr in addresses:
                if 'tailscale' in interface.lower() and addr.family == socket.AF_INET:
                    return addr.address
    except Exception:
        pass
    
    return None

def is_allowed_ip(client_ip: str) -> bool:
    """Check if client IP is allowed (Tailscale range)"""
    allowed_ranges = config.security.get('ip_whitelist', ["100.64.0.0/10"])
    
    # Always allow localhost
    if client_ip in ['127.0.0.1', 'localhost', '::1']:
        return True
    
    # Check if IP is in allowed ranges
    from ipaddress import ip_address, ip_network
    
    try:
        client_ip_obj = ip_address(client_ip)
        for ip_range in allowed_ranges:
            if '/' in ip_range:
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
        {"name": "soa1_api", "display": "SOA1 API", "port": 8001, "url": config.services.get("api", "http://localhost:8001"), "required": True},
        {"name": "soa1_web", "display": "SOA1 Web Interface", "port": 8002, "url": config.services.get("web_interface", "http://localhost:8002"), "required": False},
        {"name": "service_monitor", "display": "Service Monitor", "port": 8003, "url": config.services.get("service_monitor", "http://localhost:8003"), "required": False},
        {"name": "memlayer", "display": "Memlayer", "port": 8000, "url": config.services.get("memlayer", "http://localhost:8000"), "required": True},
        {"name": "ollama", "display": "Ollama (LLM)", "port": 11434, "url": "http://localhost:11434", "required": True},
    ]
    
    for service_def in service_definitions:
        service = ServiceStatus(
            name=service_def["name"],
            display_name=service_def["display"],
            port=service_def["port"],
            url=service_def["url"],
            required=service_def["required"]
        )
        
        try:
            # Check if process is running
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if service.name in cmdline or str(service.port) in cmdline:
                        service.pid = proc.info['pid']
                        service.cpu_usage = proc.cpu_percent(interval=0.1)
                        service.memory_usage = proc.memory_info().rss / 1024 / 1024  # MB
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
    """Get overall system status"""
    status = SystemStatus()
    
    try:
        # CPU usage
        status.cpu_usage = psutil.cpu_percent(interval=1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        status.memory_usage = memory.percent
        
        # Disk usage
        disk = psutil.disk_usage('/')
        status.disk_usage = disk.percent
        
        # Uptime
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        status.uptime = str(uptime).split('.')[0]
        
        # Tailscale IP
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
    """Main dashboard"""
    client_ip = request.client.host
    
    if not check_access(client_ip):
        raise HTTPException(status_code=403, detail="Access denied: IP not allowed")
    
    services = get_service_status()
    system_status = get_system_status()
    
    # Calculate overall status
    required_services = [s for s in services if s.required]
    running_required = [s for s in required_services if s.status == "running"]
    overall_status = "operational" if len(running_required) == len(required_services) else "degraded"
    
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": "SOA1 Web UI - Tailscale Edition",
            "services": services,
            "system_status": system_status,
            "overall_status": overall_status,
            "required_count": len(required_services),
            "running_required": len(running_required),
            "tailscale_enabled": config.tailscale.get("enabled", True),
            "tailscale_ip": system_status.tailscale_ip,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    )

@app.get("/api/services")
def api_services():
    """API endpoint for service status"""
    services = get_service_status()
    system_status = get_system_status()
    
    return {
        "services": [{
            "name": s.name,
            "display_name": s.display_name,
            "status": s.status,
            "port": s.port,
            "url": s.url,
            "pid": s.pid,
            "cpu_usage": s.cpu_usage,
            "memory_usage": s.memory_usage,
            "error": s.error,
            "required": s.required
        } for s in services],
        "system": {
            "cpu_usage": system_status.cpu_usage,
            "memory_usage": system_status.memory_usage,
            "disk_usage": system_status.disk_usage,
            "uptime": system_status.uptime,
            "tailscale_ip": system_status.tailscale_ip
        }
    }

@app.get("/health")
def health():
    """Health check endpoint"""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "tailscale_ip": get_tailscale_ip()
    }

# Create simple template
os.makedirs("templates", exist_ok=True)
with open("templates/index.html", "w") as f:
    f.write("""<!DOCTYPE html>
<html>
<head>
    <title>{{ title }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f7fa; }
        .header { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px; }
        h1 { color: #667eea; }
        .status-card { background: white; padding: 15px; margin: 10px 0; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .status-running { color: #28a745; font-weight: bold; }
        .status-stopped { color: #dc3545; font-weight: bold; }
        .status-error { color: #ffc107; font-weight: bold; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px; }
        .btn { background: #667eea; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; }
        .btn:hover { background: #764ba2; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🌐 SOA1 Web UI - Tailscale Edition</h1>
        {% if tailscale_ip %}
        <p>🔒 Tailscale: {{ tailscale_ip }} | Status: <span class="status-{{ overall_status }}">{{ overall_status }}</span></p>
        {% endif %}
    </div>
    
    <div class="status-card">
        <h2>📊 System Status</h2>
        <p>CPU: {{ "%.1f"|format(system_status.cpu_usage) }}% | Memory: {{ "%.1f"|format(system_status.memory_usage) }}% | Disk: {{ "%.1f"|format(system_status.disk_usage) }}%</p>
        <p>Required Services: {{ running_required }}/{{ required_count }} running</p>
    </div>
    
    <h2>🔧 Services</h2>
    <div class="grid">
        {% for service in services %}
        <div class="status-card">
            <h3>{{ service.display_name }} {% if not service.required %}(optional){% endif %}</h3>
            <p><strong>Status:</strong> <span class="status-{{ service.status }}">{{ service.status }}</span></p>
            {% if service.port %}<p><strong>Port:</strong> {{ service.port }}</p>{% endif %}
            {% if service.pid %}<p><strong>PID:</strong> {{ service.pid }}</p>{% endif %}
            {% if service.cpu_usage > 0 %}<p><strong>CPU:</strong> {{ "%.1f"|format(service.cpu_usage) }}%</p>{% endif %}
            {% if service.memory_usage > 0 %}<p><strong>Memory:</strong> {{ "%.1f"|format(service.memory_usage) }} MB</p>{% endif %}
            {% if service.error %}<p><strong>Error:</strong> {{ service.error }}</p>{% endif %}
        </div>
        {% endfor %}
    </div>
    
    <div style="margin-top: 20px;">
        <button class="btn" onclick="window.location.reload()">🔄 Refresh Status</button>
        <button class="btn" onclick="window.location='/api/services'" style="margin-left: 10px;">📋 JSON API</button>
    </div>
    
    <p style="margin-top: 20px; color: #666;">Last updated: {{ last_updated }}</p>
</body>
</html>""")

if __name__ == "__main__":
    logger.info("🚀 Starting SOA1 Web UI - Simple Tailscale Edition...")
    logger.info(f"🌐 Dashboard will be available at http://{config.server['host']}:{config.server['port']}")
    
    # Get Tailscale IP
    tailscale_ip = get_tailscale_ip()
    if tailscale_ip:
        logger.info(f"🔒 Tailscale IP: {tailscale_ip}")
        logger.info(f"🌐 Tailscale access: http://{tailscale_ip}:{config.server['port']}")
    else:
        logger.warning("⚠️ Tailscale IP not detected. Make sure Tailscale is running.")
    
    uvicorn.run(
        app,
        host=config.server["host"],
        port=config.server["port"],
        reload=False
    )