#!/usr/bin/env bash
set -eu

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

INCIDENT_ID="${1:-$(cat /tmp/relayguard_incident_id.txt 2>/dev/null || true)}"
if [[ -z "$INCIDENT_ID" ]]; then
  echo "Usage: $0 <incident_id>"
  exit 1
fi

export DATABASE_URL="${DATABASE_URL:-postgresql://root@localhost:26257/relayguard?sslmode=disable}"
python -m apps.cli.verify_demo "$INCIDENT_ID"
