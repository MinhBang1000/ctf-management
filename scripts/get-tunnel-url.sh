#!/usr/bin/env bash
# Prints the current public URL of the hslab-tunnel PM2 process.
#
# Quick Tunnel URLs are random and change every time the tunnel process
# restarts, so cloudflared's own log is the only source of truth — this
# reads it back out. See README.md "Finding your current Quick Tunnel URL".
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="$ROOT_DIR/logs/hslab-tunnel.log"

if [ ! -f "$LOG_FILE" ]; then
  echo "Log file not found: $LOG_FILE — is hslab-tunnel running? (pm2 list)" >&2
  exit 1
fi

URL="$(grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' "$LOG_FILE" | tail -n 1 || true)"

if [ -z "$URL" ]; then
  echo "No *.trycloudflare.com URL found in $LOG_FILE." >&2
  echo "If CLOUDFLARE_TUNNEL_TOKEN is set in .env, you're in Named Tunnel mode:" >&2
  echo "the fixed domain is configured in the Cloudflare Zero Trust dashboard, not printed here." >&2
  exit 1
fi

echo "$URL"
