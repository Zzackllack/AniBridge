#!/usr/bin/env bash
set -e

echo "🚀 AniBridge Startup Script – Initializing Environment..."
echo "--------------------------------------------"

# Check Python
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ Python3 not found. Please install Python 3.11+"
    exit 1
fi
if ! command -v uv >/dev/null 2>&1; then
    echo "❌ uv not found. Install it first: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

echo "✅ Python3 detected: $(python3 --version)"

API_DIR="$(cd "$(dirname "$0")/../apps/api" && pwd)"

# Ensure Python version is >= 3.14 to match apps/api/pyproject.toml requires-python.
PYTHON_VERSION_OK=$(python3 -c 'import sys; print(int(sys.version_info >= (3, 14)))' || echo "0")
if [ "$PYTHON_VERSION_OK" != "1" ]; then
    echo "❌ Python 3.14+ is required, but found: $(python3 --version 2>&1 || echo "unknown version")"
    exit 1
fi

# Create virtual environment
echo "📦 Creating virtual environment..."
(
    cd "$API_DIR"
    uv venv
)

# Install dependencies
echo "📦 Installing dependencies..."
(
    cd "$API_DIR"
    uv sync --frozen
)

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
(
    cd "$API_DIR"
    uv run python -m app.main
)
