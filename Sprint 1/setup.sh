#!/bin/bash
# One-time setup for CareerConnect Sprint 1.
# Run this once after cloning the repo (or after pulling changes that touch
# requirements.txt / package.json).
#
# Usage:
#   cd "Sprint 1"
#   chmod +x setup.sh   (only needed the very first time)
#   ./setup.sh

set -e  # stop immediately if any command fails, instead of plowing ahead

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

echo "=== Setting up backend ==="
cd "$BACKEND_DIR"

if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  if command -v python >/dev/null 2>&1; then
       python -m venv venv
     else
       python3 -m venv venv
     fi
   fi

if [ -f "venv/bin/activate" ]; then
  source venv/bin/activate
else
  source venv/Scripts/activate
fi

pip install --upgrade pip > /dev/null
pip install -r requirements.txt

deactivate

echo "=== Setting up frontend ==="
cd "$FRONTEND_DIR"
npm install

echo ""
echo "Setup complete."
if ! grep -q "postgresql://postgres" "$BACKEND_DIR/.env" 2>/dev/null || grep -q "YOUR-SHARED-PASSWORD\|xxxxxxxxxxxx" "$BACKEND_DIR/.env" 2>/dev/null; then
  echo "REMINDER: backend/.env still needs a real DATABASE_URL before you can run the app."
fi
echo "Run './run.sh' from the Sprint 1 folder to start both servers."
