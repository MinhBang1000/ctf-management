#!/usr/bin/env bash
# Single PM2 process ("hslab-app") that runs the whole app stack:
# FastAPI backend (uvicorn) + Next.js frontend, together. If either dies,
# this script exits so PM2 restarts both together. See README.md.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

cleanup() {
  kill "${BACKEND_PID:-0}" "${FRONTEND_PID:-0}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

(
  cd "$ROOT_DIR/backend"
  # shellcheck disable=SC1091
  source venv/bin/activate
  exec uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT"
) &
BACKEND_PID=$!

(
  cd "$ROOT_DIR/frontend"
  exec npm run start -- --hostname 0.0.0.0 --port "$FRONTEND_PORT"
) &
FRONTEND_PID=$!

# If either process exits, stop the other and let PM2 restart hslab-app.
wait -n "$BACKEND_PID" "$FRONTEND_PID"
