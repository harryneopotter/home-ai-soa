#!/usr/bin/env python3
"""
SOA1 Web UI - Tailscale Edition
Main web application for monitoring and controlling SOA1 services
"""

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer
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
    description="Web interface for monitoring and controlling SOA1 services via Tailscale",
    version="1.0.0"
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def get_tailscale_ip() -> Optional[str]:
    """Get the Tailscale IP address"""
    try:
        # Try to get Tailscale IP using tailscale command
        import subprocess
        result = subprocess.run(["tailscale", "ip", "-4"], 
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    
    try:
        # Fallback: check for Tailscale interface
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
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
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

# Create default templates
create_default_templates()

if __name__ == "__main__":
    logger.info("🚀 Starting SOA1 Web UI - Tailscale Edition...")
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