#!/usr/bin/env bash
# RelayGuard Bedrock selector demo — same crash handoff with ACTION_SELECTOR=bedrock.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

EVIDENCE_DIR="$ROOT/docs/evidence"
mkdir -p "$EVIDENCE_DIR"
LOG_FILE="$EVIDENCE_DIR/bedrock_selector_run.txt"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

PYTHON="${ROOT}/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi

REGION="${AWS_REGION:-us-east-1}"

{
  echo "RelayGuard Bedrock selector demo"
  echo "================================"
  echo "Started: $(date -Iseconds)"
  echo ""
} >"$LOG_FILE"

PREFLIGHT=$("$PYTHON" -c "
import json, sys
try:
    import boto3
except ImportError:
    print(json.dumps({'ok': False, 'reason': 'boto3 not installed — pip install -e \".[bedrock]\"'}))
    sys.exit(0)
try:
    boto3.client('bedrock-runtime', region_name='$REGION')
    print(json.dumps({'ok': True}))
except Exception as exc:
    print(json.dumps({'ok': False, 'reason': str(exc)}))
" 2>&1) || true

echo "$PREFLIGHT" | tee -a "$LOG_FILE"

if echo "$PREFLIGHT" | "$PYTHON" -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('ok') else 1)" 2>/dev/null; then
  :
else
  {
    echo ""
    echo "SKIPPED: Bedrock unavailable."
    echo "Reason: $PREFLIGHT"
  } | tee -a "$LOG_FILE"
  exit 0
fi

export ACTION_SELECTOR=bedrock
export RELAYGUARD_DEMO_TITLE="Bedrock selector demo incident"

set +e
bash "$ROOT/scripts/run-demo.sh" 2>&1 | tee -a "$LOG_FILE"
EXIT=${PIPESTATUS[0]}
set -e

if [[ "$EXIT" -ne 0 ]]; then
  echo "Demo failed with exit $EXIT" | tee -a "$LOG_FILE"
  exit "$EXIT"
fi

{
  echo ""
  echo "Finished: $(date -Iseconds)"
} | tee -a "$LOG_FILE"

echo ""
echo "Bedrock demo log: $LOG_FILE"
