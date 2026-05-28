#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cleanup() {
  echo ""
  echo "Arrêt..."
  kill 0 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "→ Backend (port 8000)"
(cd "$ROOT/backend" && "$ROOT/.venv/bin/python" main.py) &
BACKEND_PID=$!

echo "→ Frontend (port 5173)"
(cd "$ROOT/frontend" && npm run dev) &
FRONTEND_PID=$!

wait $BACKEND_PID $FRONTEND_PID
