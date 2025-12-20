#!/usr/bin/env python3
"""
SOA1 Web Interface
Simple web UI for interacting with SOA1 agent
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import os
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("web_interface")

# Create app
app = FastAPI(title="SOA1 Web Interface")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Configuration
SOA1_API_URL = "http://localhost:8001"

@app.get("/")
def home(request: Request):
    """Home page"""
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "title": "SOA1 - Home Assistant"}
    )

@app.get("/chat")
def chat(request: Request):
    """Chat interface"""
    return templates.TemplateResponse(
        "chat.html",
        {"request": request, "title": "SOA1 Chat"}
    )

@app.get("/status")
def status():
    """System status"""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "api": "running",
            "web_interface": "running"
        }
    }

if __name__ == "__main__":
    # Create necessary directories
    os.makedirs("static", exist_ok=True)
    os.makedirs("templates", exist_ok=True)
    
    # Create basic CSS
    with open("static/style.css", "w") as f:
        f.write("""
body {
    font-family: Arial, sans-serif;
    line-height: 1.6;
    margin: 0;
    padding: 20px;
    background-color: #f5f5f5;
}

.container {
    max-width: 800px;
    margin: 0 auto;
    background: white;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

header {
    background: #4a6fa5;
    color: white;
    padding: 10px 20px;
    border-radius: 8px 8px 0 0;
    margin-bottom: 20px;
}

button {
    background: #4a6fa5;
    color: white;
    border: none;
    padding: 10px 15px;
    border-radius: 4px;
    cursor: pointer;
}

button:hover {
    background: #3a5a8f;
}

#chat-box {
    height: 400px;
    border: 1px solid #ddd;
    padding: 10px;
    overflow-y: auto;
    margin-bottom: 10px;
    background: #f9f9f9;
}

.message {
    margin-bottom: 15px;
    padding: 10px;
    border-radius: 4px;
}

.user-message {
    background: #e3f2fd;
    text-align: right;
}

.bot-message {
    background: #f1f1f1;
    text-align: left;
}

.audio-player {
    margin-top: 10px;
}

.input-area {
    display: flex;
    gap: 10px;
}

#query-input {
    flex: 1;
    padding: 10px;
    border: 1px solid #ddd;
    border-radius: 4px;
}
""")
    
    # Create basic HTML templates
    with open("templates/index.html", "w") as f:
        f.write("""
<!DOCTYPE html>
<html>
<head>
    <title>{{ title }}</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <div class="container">
        <header>
            <h1>SOA1 - Home Assistant</h1>
        </header>
        
        <h2>Welcome to SOA1</h2>
        <p>Your local AI assistant is ready to help!</p>
        
        <div style="margin: 20px 0;">
            <a href="/chat">
                <button>Start Chat</button>
            </a>
            <a href="/status">
                <button>System Status</button>
            </a>
        </div>
        
        <h3>Features</h3>
        <ul>
            <li>Local-only AI processing</li>
            <li>Memory-based context</li>
            <li>Text-to-speech responses</li>
            <li>Document analysis (coming soon)</li>
        </ul>
    </div>
</body>
</html>
""")
    
    with open("templates/chat.html", "w") as f:
        f.write("""
<!DOCTYPE html>
<html>
<head>
    <title>{{ title }}</title>
    <link rel="stylesheet" href="/static/style.css">
    <script>
        async function sendQuery() {
            const query = document.getElementById('query-input').value;
            if (!query) return;

            // Add user message
            addMessage(query, 'user-message');
            document.getElementById('query-input').value = '';

            try {
                // Send to API
                const response = await fetch('/api/ask', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({query: query})
                });

                const data = await response.json();
                
                // Add bot response
                addMessage(data.answer, 'bot-message');
                
                // Add audio if available
                if (data.audio_path) {
                    const audioUrl = `/api/audio/${data.audio_path.split('/').pop()}`;
                    addAudioPlayer(audioUrl);
                }
                
            } catch (error) {
                addMessage('Error: ' + error.message, 'bot-message');
            }
        }

        function addMessage(text, className) {
            const chatBox = document.getElementById('chat-box');
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${className}`;
            messageDiv.innerHTML = `<strong>${className === 'user-message' ? 'You' : 'SOA1'}:</strong><br>${text.replace(/\n/g, '<br>')}`;
            chatBox.appendChild(messageDiv);
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        function addAudioPlayer(audioUrl) {
            const chatBox = document.getElementById('chat-box');
            const audioDiv = document.createElement('div');
            audioDiv.className = 'audio-player';
            audioDiv.innerHTML = `
                <audio controls>
                    <source src="${audioUrl}" type="audio/wav">
                    Your browser does not support the audio element.
                </audio>
            `;
            chatBox.appendChild(audioDiv);
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        function handleKeyPress(e) {
            if (e.key === 'Enter') {
                sendQuery();
            }
        }
    </script>
</head>
<body>
    <div class="container">
        <header>
            <h1>SOA1 Chat</h1>
        </header>
        
        <div id="chat-box"></div>
        
        <div class="input-area">
            <input 
                type="text" 
                id="query-input" 
                placeholder="Ask SOA1 anything..." 
                onkeypress="handleKeyPress(event)"
            >
            <button onclick="sendQuery()">Send</button>
        </div>
        
        <p style="margin-top: 20px; font-size: 0.9em; color: #666;">
            SOA1 is running locally on this server. All processing happens here - no cloud involved.
        </p>
    </div>
</body>
</html>
""")
    
    logger.info("Starting SOA1 Web Interface on http://0.0.0.0:8002")
    uvicorn.run(app, host="0.0.0.0", port=8002)