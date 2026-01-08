#!/bin/bash

# setup_env.sh - Sets up the development environment for SOA1

set -e  # Exit on error

# Define paths
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_AI_DIR="$PROJECT_ROOT/home-ai"
VENV_DIR="$HOME_AI_DIR/venv"

echo "🚀 Setting up SOA1 Environment..."
echo "📂 Project Root: $PROJECT_ROOT"

# 1. Create Virtual Environment
if [ -d "$VENV_DIR" ]; then
    echo "✅ Virtual environment already exists at $VENV_DIR"
else
    echo "🔨 Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo "✅ Created venv."
fi

# 2. Activate and Install Requirements
source "$VENV_DIR/bin/activate"
echo "📦 Upgrading pip..."
pip install --upgrade pip

if [ -f "$HOME_AI_DIR/requirements.txt" ]; then
    echo "📦 Installing dependencies from $HOME_AI_DIR/requirements.txt..."
    pip install -r "$HOME_AI_DIR/requirements.txt"
else
    echo "⚠️  WARNING: $HOME_AI_DIR/requirements.txt not found!"
fi

# 3. Create Directory Structure (Ignored directories)
echo "📂 Creating project directory structure..."

DIRS=(
    "$PROJECT_ROOT/logs"
    "$PROJECT_ROOT/tmp"
    "$PROJECT_ROOT/data/raw"
    "$PROJECT_ROOT/data/processed"
    "$PROJECT_ROOT/reports"
    "$PROJECT_ROOT/models"
    "$HOME_AI_DIR/finance-agent/data/reports"
    "$HOME_AI_DIR/finance-agent/data/db"
)

for DIR in "${DIRS[@]}"; do
    if [ ! -d "$DIR" ]; then
        mkdir -p "$DIR"
        echo "   + Created $DIR"
    else
        echo "   . Exists $DIR"
    fi
done

# 4. Final Instructions
echo ""
echo "✅ Setup Complete!"
echo ""
echo "To activate the environment, run:"
echo "  source home-ai/venv/bin/activate"
echo ""
echo "To start the system:"
echo "  bash scripts/start-soa1.sh"
echo ""
