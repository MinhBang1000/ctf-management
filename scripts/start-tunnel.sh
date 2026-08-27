#!/usr/bin/env bash
# Single PM2 process ("hslab-tunnel") exposing the app to the internet.
#
# Mode is auto-detected from .env, per PRD §3.6 requirement #2:
#   - CLOUDFLARE_TUNNEL_TOKEN set  -> Named Tunnel (fixed domain)
#   - CLOUDFLARE_TUNNEL_TOKEN unset -> Quick Tunnel (random *.trycloudflare.com,
#     changes every restart, no Cloudflare account needed)
# No code changes needed to switch — just fill in .env. See README.md.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

FRONTEND_PORT="${FRONTEND_PORT:-3000}"

if [ -n "${CLOUDFLARE_TUNNEL_TOKEN:-}" ]; then
  echo "[hslab-tunnel] CLOUDFLARE_TUNNEL_TOKEN is set -> starting Named Tunnel"
  exec cloudflared tunnel run --token "$CLOUDFLARE_TUNNEL_TOKEN"
else
  echo "[hslab-tunnel] No CLOUDFLARE_TUNNEL_TOKEN -> starting Quick Tunnel"
  exec cloudflared tunnel --url "http://localhost:${FRONTEND_PORT}"
fi
