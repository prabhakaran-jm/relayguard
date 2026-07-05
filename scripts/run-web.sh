#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/apps/web"

if [[ ! -d node_modules ]]; then
  echo "Installing frontend dependencies..."
  npm install
else
  echo "node_modules present — run 'npm install' in apps/web if deps changed."
fi

if [[ -d .next ]]; then
  echo "Resetting .next cache for a clean dev session..."
  rm -rf .next
fi

echo ""
echo "Starting RelayGuard dashboard at http://localhost:3000"
npm run dev
