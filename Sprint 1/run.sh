#!/bin/bash
# Runs both the backend and frontend dev servers together, in one terminal.
# Assumes you've already run setup.sh at least once.
#
# Usage:
#   cd "Sprint 1"
#   chmod +x run.sh   (only needed the very first time)
#   ./run.sh
#
# Press Ctrl+C once to stop BOTH servers — normally you'd need to do this
# separately in two terminal tabs; this script handles that for you.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

# If anything goes wrong, or the user hits Ctrl+C, kill both background
# processes rather than leaving one orphaned and still holding its port.
cleanup() {
  echo ""
  echo "Stopping servers..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
  exit 0
}
trap cleanup INT TERM

echo "=== Starting backend (http://localhost:5000) ==="
cd "$BACKEND_DIR"
source venv/bin/activate
uvicorn app:app --reload --port 5000 &
BACKEND_PID=$!
deactivate

echo "=== Starting frontend ==="
cd "$FRONTEND_DIR"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "Both servers running. Press Ctrl+C to stop both."

# Wait for either process to exit (or for Ctrl+C to trigger cleanup above)
wait
