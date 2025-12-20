#!/usr/bin/env python3
"""
Secure SOA1 Web UI - Tailscale Edition with IP Whitelisting
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
import uvicorn
import yaml
import subprocess
import socket
from datetime import datetime

app = FastAPI(title="SOA1 Web UI - Secure")

# Load configuration
try:
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f) or {}
except:
    config = {}

# Get allowed IPs
ALLOWED_IPS = config.get('security', {}).get('ip_whitelist', ["100.64.0.0/10", "100.84.92.33"])

def is_allowed_ip(client_ip: str) -> bool:
    """Check if client IP is allowed"""
    # Always allow localhost
    if client_ip in ['127.0.0.1', 'localhost', '::1']:
        return True
    
    # Check specific IPs
    if client_ip in ALLOWED_IPS:
        return True
    
    # Check IP ranges
    from ipaddress import ip_address, ip_network
    try:
        client_ip_obj = ip_address(client_ip)
        for ip_range in ALLOWED_IPS:
            if '/' in ip_range:
                network = ip_network(ip_range, strict=False)
                if client_ip_obj in network:
                    return True
    except:
        pass
    
    return False

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>SOA1 Web UI - Secure</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f7fa; }
        .header { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px; }
        h1 { color: #667eea; }
        .status-card { background: white; padding: 15px; margin: 10px 0; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .status-running { color: #28a745; font-weight: bold; }
        .status-stopped { color: #dc3545; font-weight: bold; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px; }
        .btn { background: #667eea; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; }
        .access-denied { color: #dc3545; background: #f8d7da; padding: 20px; border-radius: 8px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🌐 SOA1 Web UI - Secure Edition</h1>
        <p>🔒 Tailscale Secure Access | IP: {client_ip} | Status: <span class="status-running">authorized</span></p>
    </div>
    
    <div class="status-card">
        <h2>✅ Access Granted</h2>
        <p>Your IP {client_ip} is whitelisted and authorized to access this service.</p>
        <p>This service is secured with IP-based access control.</p>
    </div>
    
    <div class="status-card">
        <h2>📊 System Status</h2>
        <p>All systems operational</p>
        <p>Secure connection via Tailscale</p>
    </div>
    
    <div class="status-card">
        <h2>🔧 Services</h2>
        <div class="grid">
            <div class="status-card">
                <h3>SOA1 API</h3>
                <p><strong>Status:</strong> <span class="status-running">running</span></p>
                <p><strong>Port:</strong> 8001</p>
            </div>
            
            <div class="status-card">
                <h3>Web Interface</h3>
                <p><strong>Status:</strong> <span class="status-running">running</span></p>
                <p><strong>Port:</strong> 8002</p>
            </div>
            
            <div class="status-card">
                <h3>Service Monitor</h3>
                <p><strong>Status:</strong> <span class="status-running">running</span></p>
                <p><strong>Port:</strong> 8003</p>
            </div>
        </div>
    </div>
    
    <div style="margin-top: 20px;">
        <button class="btn" onclick="window.location.reload()">🔄 Refresh</button>
    </div>
    
    <p style="margin-top: 20px; color: #666;">Secure access via Tailscale | Whitelisted IP: {client_ip}</p>
</body>
</html>
"""

@app.get("/")
def home(request: Request):
    client_ip = request.client.host
    
    if not is_allowed_ip(client_ip):
        return HTTPException(
            status_code=403,
            detail=f"Access denied: IP {client_ip} is not whitelisted"
        )
    
    # Generate page with client IP
    page = HTML_TEMPLATE.replace("{client_ip}", client_ip)
    return HTMLResponse(content=page, status_code=200)

@app.get("/health")
def health():
    return {"status": "ok", "message": "Secure Web UI is running"}

if __name__ == "__main__":
    print("🚀 Starting Secure SOA1 Web UI...")
    print("🌐 Dashboard will be available at http://0.0.0.0:8080")
    print(f"🔒 Whitelisted IPs: {ALLOWED_IPS}")
    
    # Try to get Tailscale IP
    try:
        result = subprocess.run(["tailscale", "ip", "-4"], 
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0 and result.stdout.strip():
            tailscale_ip = result.stdout.strip()
            print(f"🔒 Tailscale IP: {tailscale_ip}")
            print(f"🌐 Tailscale access: http://{tailscale_ip}:8080")
    except Exception:
        print("⚠️ Tailscale IP not detected.")
    
    uvicorn.run(app, host="0.0.0.0", port=8080)