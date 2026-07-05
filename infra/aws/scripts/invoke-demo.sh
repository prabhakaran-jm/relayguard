#!/usr/bin/env bash
# Invoke RelayGuard Lambda crash-safe handoff demo against CockroachDB Cloud
set -eu

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

FUNCTION_NAME="${RELAYGUARD_LAMBDA_FUNCTION_NAME:-relayguard-worker}"
AWS_REGION="${AWS_REGION:-us-east-1}"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

export RELAYGUARD_DB_TARGET=cloud
LEASE_TTL_SECONDS="${LEASE_TTL_SECONDS:-3}"
PYTHON="${ROOT}/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi

invoke_lambda() {
  local label="$1"
  local payload_file="$2"
  local response_file
  response_file="$(mktemp)"
  echo ""
  echo "==> Lambda invoke: $label"
  aws lambda invoke \
    --function-name "$FUNCTION_NAME" \
    --region "$AWS_REGION" \
    --cli-binary-format raw-in-base64-out \
    --payload "file://$payload_file" \
    "$response_file" >/dev/null
  python3 -c "import json,sys; label=sys.argv[1]; body=json.load(open(sys.argv[2])); \
print(json.dumps(body)) if body.get('ok') else sys.exit(f'Lambda returned error for {label}: {body.get(\"error\")}')" \
    "$label" "$response_file"
  rm -f "$response_file"
}

echo "=============================================="
echo " RelayGuard Lambda handoff demo (Cloud)"
echo "=============================================="
echo "Function: $FUNCTION_NAME"
echo "Region:   $AWS_REGION"

echo ""
echo "==> Creating incident on CockroachDB Cloud"
INCIDENT_ID="$("$PYTHON" -m apps.cli.create_incident --apply-schema --title "Lambda handoff demo" | tail -1)"
echo "Incident ID: $INCIDENT_ID"

PAYLOAD_A="$(mktemp)"
cat >"$PAYLOAD_A" <<JSON
{"mode":"run_worker","incident_id":"$INCIDENT_ID","worker_id":"worker-a","fail_after":"ACTION_RESERVED"}
JSON
WORKER_A_JSON="$(invoke_lambda "worker-a crash after reserve" "$PAYLOAD_A")"
rm -f "$PAYLOAD_A"

EXIT_CODE="$(echo "$WORKER_A_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['exit_code'])")"
if [[ "$EXIT_CODE" != "2" ]]; then
  echo "Expected worker-a exit_code 2, got $EXIT_CODE"
  exit 1
fi
INTENT_ID="$(echo "$WORKER_A_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('intent_id') or '')")"
WORKER_A_EPOCH="$(echo "$WORKER_A_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('lease_epoch') or '')")"
if [[ -z "$INTENT_ID" ]]; then
  echo "Lambda response missing intent_id"
  exit 1
fi
echo "Captured intent_id=$INTENT_ID worker_a_epoch=$WORKER_A_EPOCH"

echo ""
echo "==> Waiting for lease expiry (${LEASE_TTL_SECONDS}s)..."
sleep $((LEASE_TTL_SECONDS + 1))

PAYLOAD_B="$(mktemp)"
cat >"$PAYLOAD_B" <<JSON
{"mode":"run_worker","incident_id":"$INCIDENT_ID","worker_id":"worker-b"}
JSON
WORKER_B_JSON="$(invoke_lambda "worker-b commit" "$PAYLOAD_B")"
rm -f "$PAYLOAD_B"

EXIT_CODE="$(echo "$WORKER_B_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['exit_code'])")"
if [[ "$EXIT_CODE" != "0" ]]; then
  echo "Expected worker-b exit_code 0, got $EXIT_CODE"
  exit 1
fi

PAYLOAD_STALE="$(mktemp)"
cat >"$PAYLOAD_STALE" <<JSON
{"mode":"stale_commit","incident_id":"$INCIDENT_ID","worker_id":"worker-a","intent_id":"$INTENT_ID","lease_epoch":$WORKER_A_EPOCH}
JSON
STALE_JSON="$(invoke_lambda "worker-a stale commit" "$PAYLOAD_STALE")"
rm -f "$PAYLOAD_STALE"

REJECTED="$(echo "$STALE_JSON" | python3 -c "import json,sys; print('true' if json.load(sys.stdin).get('rejected') else 'false')")"
if [[ "$REJECTED" != "true" ]]; then
  echo "Expected stale commit rejection"
  exit 1
fi

echo ""
echo "==> Verify demo invariants"
"$PYTHON" -m apps.cli.verify_demo "$INCIDENT_ID"

echo ""
echo "==> Audit incident report"
"$PYTHON" -m apps.cli.audit_incident --incident-id "$INCIDENT_ID"

echo ""
echo "Lambda demo complete."
