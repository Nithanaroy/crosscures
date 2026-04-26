#!/bin/bash
# CrossCures v2 -- Start both backend and frontend

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$SCRIPT_DIR"

echo "[START] Starting CrossCures v2..."

# Seed database if it doesn't exist yet
if [ ! -f "$SCRIPT_DIR/backend/crosscures.db" ]; then
    echo "[SEED] First run detected -- seeding demo database..."
    cd "$SCRIPT_DIR/backend"
    uv run crosscures-v2-seed
    echo "[SEED] Database seeded."
fi

# Start backend using uv workspace
echo "[BACKEND] Starting backend on port 8000..."
cd "$SCRIPT_DIR/backend"
uv run uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!

# Wait for backend to be ready
sleep 3

# Start frontend
echo "[FRONTEND] Starting frontend on port 3000..."
cd "$SCRIPT_DIR/frontend"

# Install frontend dependencies on first run
if [ ! -d "node_modules" ]; then
    echo "[FRONTEND] Installing frontend dependencies..."
    npm install
fi

npm run dev &
FRONTEND_PID=$!

echo ""
echo "[DONE] CrossCures v2 is running!"
echo "   Patient / Physician App: http://localhost:3000"
echo "   API Docs:                http://localhost:8000/docs"
echo ""
echo "Demo accounts:"
echo "   Patient:    patient@demo.com / demo1234"
echo "   Physician:  physician@demo.com / demo1234"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
