#!/usr/bin/env bash
# Single PM2 process ("hslab-celery") running the Celery worker with an
# embedded beat scheduler (-B). One process is enough at this scale and
# keeps PM2's process count minimal — a separate beat process is the
# usual production recommendation for multi-worker setups, not needed
# here. Handles both the scheduled sync loop (Phase 3) and its
# fan-out/fan-in per-member tasks.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/backend"

if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

# shellcheck disable=SC1091
source venv/bin/activate
exec celery -A app.celery_app worker -B --loglevel=info
