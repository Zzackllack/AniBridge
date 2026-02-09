#!/usr/bin/env bash
set -e

echo "🚀 AniBridge Startup Script – Initializing Environment..."
echo "--------------------------------------------"

# Check Python
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ Python3 not found. Please install Python 3.10+"
    exit 1
fi
if ! command -v uv >/dev/null 2>&1; then
    echo "❌ uv not found. Install it first: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

echo "✅ Python3 detected: $(python3 --version)"

# Create virtual environment
echo "📦 Creating virtual environment..."
uv venv
source .venv/bin/activate

echo "✅ Virtual environment activated."

# Install dependencies
echo "📦 Installing dependencies..."
uv sync --frozen

echo "✅ Dependencies installed."

# Export environment variables
echo "⚙️ Setting environment variables..."
export LOG_LEVEL=DEBUG
export INDEXER_API_KEY="devkey"
export INDEXER_NAME="AniBridge"
export TORZNAB_CAT_ANIME=5070
export DOWNLOAD_DIR="./downloads"

echo "✅ Environment variables set."

# Startup message to Codex / LLM
echo "💡 Hey Codex, the environment is ready."
echo "💡 Python venv is active."
echo "💡 All dependencies are installed."
echo "💡 You can now start the AniBridge FastAPI server."

# Start FastAPI
echo "🚀 Launching AniBridge..."
uv run python -m app.main
