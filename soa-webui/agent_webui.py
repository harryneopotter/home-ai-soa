#!/usr/bin/env python3
"""
SOA1 Agent Web UI - Complete Interaction Interface
Enhanced web UI with full agent interaction capabilities
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import yaml
import subprocess
import socket
import requests
import json
import logging
from datetime import datetime
from typing import Optional, Dict, List

# Configure logging for agent web UI
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('agent_webui.log'),
        logging.StreamHandler()
    ]
)
agent_logger = logging.getLogger("agent_webui")

app = FastAPI(title="SOA1 Agent Web UI")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Load configuration
try:
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f) or {}
except:
    config = {}

# Configuration
SOA1_API_URL = config.get('services', {}).get('api', 'http://localhost:8001')
ALLOWED_IPS = config.get('security', {}).get('ip_whitelist', ["100.64.0.0/10", "100.84.92.33"])

def is_allowed_ip(client_ip: str) -> bool:
    """Check if client IP is allowed"""
    if client_ip in ['127.0.0.1', 'localhost', '::1']:
        return True
    if client_ip in ALLOWED_IPS:
        return True
    
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

def get_tailscale_ip() -> Optional[str]:
    """Get the Tailscale IP address"""
    try:
        result = subprocess.run(["tailscale", "ip", "-4"], 
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except:
        pass
    return None

def ask_agent(query: str) -> Dict:
    """Ask the SOA1 agent a question via API"""
    try:
        response = requests.post(
            f"{SOA1_API_URL}/ask",
            json={"query": query},
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
        else:
            return {
                "error": f"API Error: {response.status_code}",
                "query": query
            }
    except Exception as e:
        return {
            "error": f"Connection Error: {str(e)}",
            "query": query
        }

# HTML Template with Agent Interaction
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>SOA1 Agent Web UI</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        header {
            background: white;
            padding: 20px 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        h1 {
            color: #667eea;
            font-size: 28px;
            font-weight: 600;
        }
        
        .tailscale-info {
            background: #f8f9fa;
            padding: 10px 20px;
            border-radius: 25px;
            font-size: 14px;
            color: #666;
        }
        
        .status-card {
            background: white;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
            margin-bottom: 20px;
        }
        
        .status-running { color: #28a745; font-weight: bold; }
        .status-stopped { color: #dc3545; font-weight: bold; }
        
        .chat-container {
            background: white;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            padding: 20px;
            margin-top: 30px;
        }
        
        .chat-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        
        .chat-messages {
            height: 400px;
            overflow-y: auto;
            border: 1px solid #eee;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
            background: #f8f9fa;
        }
        
        .message {
            margin-bottom: 15px;
            padding: 12px 15px;
            border-radius: 10px;
            max-width: 80%;
        }
        
        .user-message {
            background: #667eea;
            color: white;
            margin-left: auto;
            border-bottom-right-radius: 2px;
        }
        
        .agent-message {
            background: #e3f2fd;
            color: #1976d2;
            margin-right: auto;
            border-bottom-left-radius: 2px;
        }
        
        .chat-input {
            display: flex;
            gap: 10px;
        }
        
        .chat-input input {
            flex: 1;
            padding: 12px 20px;
            border: 2px solid #eee;
            border-radius: 25px;
            font-size: 16px;
            outline: none;
        }
        
        .chat-input input:focus {
            border-color: #667eea;
        }
        
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 25px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 14px;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .btn-secondary {
            background: white;
            color: #667eea;
            border: 2px solid #667eea;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }
        
        .system-info {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 10px;
            margin-top: 20px;
        }
        
        .last-updated {
            text-align: center;
            margin-top: 30px;
            color: white;
            font-size: 14px;
            opacity: 0.8;
        }
        
        .loading {
            color: #667eea;
            font-style: italic;
        }
        
        .error {
            color: #dc3545;
            background: #f8d7da;
            padding: 10px;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🤖 SOA1 Agent Web UI</h1>
            <div class="tailscale-info">
                🔒 Tailscale: {client_ip} | Status: <span class="status-running">authorized</span>
            </div>
        </header>
        
        <div class="status-card">
            <h2>✅ Access Granted</h2>
            <p>Your IP {client_ip} is whitelisted and authorized to interact with SOA1 Agent.</p>
        </div>
        
        <div class="chat-container">
            <div class="chat-header">
                <h2>💬 Chat with SOA1 Agent</h2>
            </div>
            
            <div class="chat-messages" id="chatMessages">
                <div class="message agent-message">
                    <strong>SOA1:</strong> Hello! I'm SOA1, your personal AI assistant. How can I help you today?
                </div>
            </div>
            
            <div class="chat-input">
                <input type="text" id="userQuery" placeholder="Ask SOA1 anything..." 
                       onkeypress="if(event.key === 'Enter') askQuestion()">
                <button class="btn btn-primary" onclick="askQuestion()">📤 Send</button>
            </div>
            
            <div class="system-info">
                <p><strong>Agent Status:</strong> <span class="status-running">Online</span></p>
                <p><strong>API Endpoint:</strong> <code>{api_url}</code></p>
                <p><strong>Connection:</strong> Secure via Tailscale</p>
            </div>
        </div>
        
        <div class="last-updated">
            SOA1 Agent Web UI | Secure Access | Last updated: {timestamp}
        </div>
    </div>
    
    <script>
        function addMessage(text, isUser = false) {
            const messagesDiv = document.getElementById('chatMessages');
            const messageDiv = document.createElement('div');
            messageDiv.className = isUser ? 'message user-message' : 'message agent-message';
            
            if (isUser) {
                messageDiv.innerHTML = `<strong>You:</strong> ${text}`;
            } else {
                messageDiv.innerHTML = `<strong>SOA1:</strong> ${text}`;
            }
            
            messagesDiv.appendChild(messageDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
        
        async function askQuestion() {
            const queryInput = document.getElementById('userQuery');
            const query = queryInput.value.trim();
            
            if (!query) return;
            
            // Add user message
            addMessage(query, true);
            queryInput.value = '';
            
            // Add loading indicator
            addMessage('Thinking...', false);
            
            try {
                const response = await fetch('/api/ask', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({query: query})
                });
                
                const data = await response.json();
                
                // Remove loading message
                const messages = document.querySelectorAll('.message');
                if (messages.length > 0) {
                    messages[messages.length - 1].remove();
                }
                
                if (data.error) {
                    addMessage(`Error: ${data.error}`, false);
                } else if (data.answer) {
                    addMessage(data.answer, false);
                } else {
                    addMessage('No response received from agent.', false);
                }
                
            } catch (error) {
                // Remove loading message
                const messages = document.querySelectorAll('.message');
                if (messages.length > 0) {
                    messages[messages.length - 1].remove();
                }
                
                addMessage(`Error: ${error.message}`, false);
            }
        }
        
        // Auto-focus on input
        document.addEventListener('DOMContentLoaded', function() {
            document.getElementById('userQuery').focus();
        });
    </script>
</body>
</html>
"""

@app.get("/")
def home(request: Request):
    """Main dashboard with agent interaction"""
    client_ip = request.client.host
    
    if not is_allowed_ip(client_ip):
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: IP {client_ip} is not whitelisted"
        )
    
    # Get current time for timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Generate page with client IP and API URL
    page = HTML_TEMPLATE.replace("{client_ip}", client_ip)
    page = page.replace("{api_url}", SOA1_API_URL)
    page = page.replace("{timestamp}", timestamp)
    
    return HTMLResponse(content=page, status_code=200)

@app.post("/api/ask")
async def api_ask(request: Request):
    """API endpoint to ask the agent"""
    client_ip = request.client.host
    
    if not is_allowed_ip(client_ip):
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: IP {client_ip} is not whitelisted"
        )
    
    try:
        data = await request.json()
        query = data.get('query', '')
        
        if not query:
            agent_logger.warning(f"No query provided from IP: {client_ip}")
            return {"error": "No query provided"}
        
        agent_logger.info(f"Asking agent: {query}")
        
        # Ask the agent
        result = ask_agent(query)
        agent_logger.info(f"Agent response: {result}")
        
        return result
        
    except Exception as e:
        agent_logger.error(f"Agent request error: {str(e)}", exc_info=True)
        return {"error": f"Invalid request: {str(e)}"}

@app.get("/health")
def health():
    """Health check endpoint"""
    return {"status": "ok", "message": "SOA1 Agent Web UI is running"}

if __name__ == "__main__":
    print("🚀 Starting SOA1 Agent Web UI with Interaction...")
    print("🌐 Dashboard will be available at http://0.0.0.0:8081")
    
    # Get Tailscale IP
    tailscale_ip = get_tailscale_ip()
    if tailscale_ip:
        print(f"🔒 Tailscale IP: {tailscale_ip}")
        print(f"🌐 Tailscale access: http://{tailscale_ip}:8081")
    else:
        print("⚠️ Tailscale IP not detected.")
    
    print(f"🤖 Agent API: {SOA1_API_URL}")
    print("💬 Features: Full agent interaction, chat interface, secure access")
    print("📋 Note: Service monitoring UI runs on port 8080, agent UI on port 8081")
    
    uvicorn.run(app, host="0.0.0.0", port=8081)