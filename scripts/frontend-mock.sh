#!/usr/bin/env bash
# Start the frontend dev server with mocked API endpoints.
# No backend required -- all /api/* requests return deterministic fixture data.
set -euo pipefail

cd "$(dirname "$0")/../app/frontend"

echo "Starting frontend in mock mode (no backend needed)..."
echo "Open http://localhost:5173 in your browser."
echo ""

VITE_MOCK=1 npx vite
