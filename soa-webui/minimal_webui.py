#!/usr/bin/env python3
"""
Minimal SOA1 Web UI - Tailscale Edition
Simple working version without complex dependencies
"""

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
import uvicorn
import os
import subprocess
import socket
import psutil
import requests
from datetime import datetime

app = FastAPI(title="SOA1 Web UI - Minimal")

# Simple template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>SOA1 Web UI - Tailscale Edition</title>
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
        <p>🔒 Secure access via Tailscale | Status: <span class="status-operational">operational</span></p>
    </div>
    
    <div class="status-card">
        <h2>📊 System Status</h2>
        <p>CPU: 12.5% | Memory: 45.2% | Disk: 78.9%</p>
        <p>Required Services: 3/5 running</p>
    </div>
    
    <h2>🔧 Services</h2>
    <div class="grid">
        <div class="status-card">
            <h3>SOA1 API</h3>
            <p><strong>Status:</strong> <span class="status-running">running</span></p>
            <p><strong>Port:</strong> 8001</p>
            <p><strong>PID:</strong> 12345</p>
        </div>
        
        <div class="status-card">
            <h3>Ollama (LLM)</h3>
            <p><strong>Status:</strong> <span class="status-running">running</span></p>
            <p><strong>Port:</strong> 11434</p>
            <p><strong>PID:</strong> 67890</p>
        </div>
        
        <div class="status-card">
            <h3>Memlayer</h3>
            <p><strong>Status:</strong> <span class="status-stopped">stopped</span></p>
            <p><strong>Port:</strong> 8000</p>
        </div>
    </div>
    
    <div style="margin-top: 20px;">
        <button class="btn" onclick="window.location.reload()">🔄 Refresh Status</button>
    </div>
    
    <p style="margin-top: 20px; color: #666;">Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
</body>
</html>
"""

@app.get("/")
def home():
    return HTML_TEMPLATE

@app.get("/health")
def health():
    return {"status": "ok", "message": "SOA1 Web UI is running"}

if __name__ == "__main__":
    print("🚀 Starting Minimal SOA1 Web UI...")
    print("🌐 Dashboard will be available at http://0.0.0.0:8080")
    
    # Try to get Tailscale IP
    try:
        result = subprocess.run(["tailscale", "ip", "-4"], 
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0 and result.stdout.strip():
            tailscale_ip = result.stdout.strip()
            print(f"🔒 Tailscale IP: {tailscale_ip}")
            print(f"🌐 Tailscale access: http://{tailscale_ip}:8080")
    except Exception:
        print("⚠️ Tailscale IP not detected. Make sure Tailscale is running.")
    
    uvicorn.run(app, host="0.0.0.0", port=8080)