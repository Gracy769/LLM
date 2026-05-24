#!/bin/bash
# start.sh — launch the AI Compiler server + open frontend

set -e
cd "$(dirname "$0")"

echo "Installing dependencies..."
pip install -r requirements.txt -q

if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo ""
  echo "⚠️  ANTHROPIC_API_KEY not set."
  echo "    Export it: export ANTHROPIC_API_KEY=sk-ant-..."
  echo ""
  exit 1
fi

echo ""
echo "Starting AI Compiler backend on http://localhost:8000"
echo "Open frontend: frontend/index.html in your browser"
echo "API docs:      http://localhost:8000/docs"
echo ""
echo "Ctrl+C to stop."
echo ""

python -m uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
