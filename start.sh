#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== TradeIQ — Trading Recommendation App ==="
echo ""

if [ ! -f "$ROOT/.env" ]; then
  echo "ERROR: .env not found. Run:"
  echo "  cp .env.example .env"
  echo "  # then edit .env and add your ANTHROPIC_API_KEY"
  exit 1
fi

# Backend
echo "[1/3] Installing backend dependencies..."
cd "$ROOT/backend"
pip install -r requirements.txt -q

echo "[2/3] Starting FastAPI backend on http://127.0.0.1:8000 ..."
uvicorn main:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!
sleep 2

# Frontend
echo "[3/3] Installing frontend dependencies and starting dev server..."
cd "$ROOT/frontend"
npm install --silent
npm run dev &
FRONTEND_PID=$!

echo ""
echo "  ✓ Backend:  http://127.0.0.1:8000"
echo "  ✓ Frontend: http://localhost:5173"
echo "  ✓ API Docs: http://127.0.0.1:8000/docs"
echo ""
echo "  Scheduled runs: 9:00 AM, 9:45 AM, 12:00 PM, 3:00 PM, 6:00 PM Eastern"
echo "  Or hit the 'Run Analysis' button on any tab for an immediate run."
echo ""
echo "Press Ctrl+C to stop both servers."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
