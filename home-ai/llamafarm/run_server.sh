#!/bin/bash

# LlamaFarm Server Startup Script
# Runs the LlamaFarm server directly without Go CLI

echo "🚀 Starting LlamaFarm Server..."

# Activate virtual environment
cd /home/ryzen/projects/llamafarm
source venv/bin/activate

# Install any missing dependencies
echo "📦 Checking dependencies..."
pip install -q python-dotenv pydantic-settings fastapi uvicorn || echo "⚠️ Some dependencies may be missing"

# Navigate to server directory
cd LlamaFarm/server

echo "🎯 Starting LlamaFarm server on port 8000..."
echo "📍 Access at: http://localhost:8000"
echo "📍 Health check: http://localhost:8000/health"

# Start the server
python3 main.py

echo "❌ Server stopped"
