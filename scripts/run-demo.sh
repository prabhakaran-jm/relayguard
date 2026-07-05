#!/usr/bin/env bash
# RelayGuard end-to-end demo: Worker A crash, Worker B failover, stale commit rejection.
set -eu

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

DB_TARGET="${RELAYGUARD_DB_TARGET:-local}"
export LEASE_TTL_SECONDS="${LEASE_TTL_SECONDS:-3}"
if [[ "$DB_TARGET" != "cloud" ]]; then
  export DATABASE_URL="${DATABASE_URL:-postgresql://root@localhost:26257/relayguard?sslmode=disable}"
fi

echo "=============================================="
echo " RelayGuard — crash-safe incident handoff demo"
echo "=============================================="
echo "Database target: $DB_TARGET"

if [[ "$DB_TARGET" == "cloud" ]]; then
  echo ""
  echo "==> Using CockroachDB Cloud (skipping local Docker)"
  INCIDENT_ID="$(python -m apps.cli.create_incident --apply-schema --title "Hackathon demo incident" | tail -1)"
  echo "$INCIDENT_ID" > /tmp/relayguard_incident_id.txt
  echo "Incident ID: $INCIDENT_ID"
else
  bash scripts/setup-db.sh
  INCIDENT_ID="$(cat /tmp/relayguard_incident_id.txt)"
fi

echo ""
echo "==> Step 1-5: Worker A claims, classifies memories, reserves action, then crashes"
export WORKER_ID=worker-a
export FAIL_AFTER=ACTION_RESERVED
set +e
python -m apps.cli.run_worker "$INCIDENT_ID"
WORKER_A_EXIT=$?
set -e
if [[ "$WORKER_A_EXIT" -ne 2 ]]; then
  echo "Expected Worker A exit code 2 (simulated crash), got $WORKER_A_EXIT"
  exit 1
fi
echo "Worker A crashed after reservation (exit $WORKER_A_EXIT)"

STATE_JSON="$(python scripts/demo_state.py "$INCIDENT_ID")"
INTENT_ID="$(echo "$STATE_JSON" | python -c "import sys,json; print(json.load(sys.stdin)['intent_id'])")"
WORKER_A_EPOCH="$(echo "$STATE_JSON" | python -c "import sys,json; print(json.load(sys.stdin)['lease_epoch'])")"
echo "Captured intent_id=$INTENT_ID worker_a_epoch=$WORKER_A_EPOCH"

echo ""
echo "==> Step 6-7: Waiting for lease expiry (${LEASE_TTL_SECONDS}s)..."
sleep $((LEASE_TTL_SECONDS + 1))

echo ""
echo "==> Step 8-9: Worker B claims with higher epoch and commits once"
export WORKER_ID=worker-b
unset FAIL_AFTER
python -m apps.cli.run_worker "$INCIDENT_ID"

echo ""
echo "==> Step 10: Worker A attempts stale commit (should be rejected)"
export WORKER_ID=worker-a
python -m apps.cli.stale_commit "$INCIDENT_ID" "$INTENT_ID" --worker-id worker-a --lease-epoch "$WORKER_A_EPOCH"

echo ""
echo "==> Step 11: Verify demo invariants"
bash scripts/verify-demo.sh "$INCIDENT_ID"

echo ""
echo "==> Step 12: Audit incident report"
python -m apps.cli.audit_incident --incident-id "$INCIDENT_ID"
