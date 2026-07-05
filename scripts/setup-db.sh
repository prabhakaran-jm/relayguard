#!/usr/bin/env bash
set -eu

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Starting CockroachDB"
docker compose -f infra/docker-compose.yml up -d

echo "==> Waiting for CockroachDB"
for i in $(seq 1 30); do
  if docker compose -f infra/docker-compose.yml exec -T cockroach \
    ./cockroach sql --insecure -e "SELECT 1" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "==> Applying schema"
python -m apps.cli.create_incident --apply-schema --title "Hackathon demo incident" | tail -1 > /tmp/relayguard_incident_id.txt
INCIDENT_ID="$(cat /tmp/relayguard_incident_id.txt)"
echo "Incident ID: $INCIDENT_ID"
