# RelayGuard

RelayGuard is a crash-safe memory and action-control layer for autonomous incident-response agents.

It lets agents:

- Resume work after crashes
- Reject stale or failed precedent
- Prevent duplicate remediation actions
- Preserve a full audit trail of memory, decisions, actions, and outcomes

## What RelayGuard is

RelayGuard sits between an incident-response agent and the systems it acts on. It uses CockroachDB as the durable coordination layer:

1. **Lease + fencing epoch** — only one worker owns an incident at a time; stale workers are rejected.
2. **MemoryGate** — classifies retrieved memories as `USE`, `INSPECT`, or `AVOID` before they influence decisions.
3. **Action intents** — idempotent reservation ledger prevents duplicate remediation.
4. **Checkpoints** — workers resume from the last durable state after a crash or handoff.
5. **Audit trail** — every claim, rejection, reservation, and commit is recorded.

The local demo simulates Worker A crashing after reserving `ROUTE_TO_STANDBY`, Worker B taking over via an expired lease, and Worker A's stale commit being rejected.

## Why CockroachDB is the memory layer

Incident response spans regions and workers. A single-node database cannot provide the durability and consistency guarantees agents need when one worker crashes and another resumes.

CockroachDB gives RelayGuard:

- **Survivable state** — checkpoints, intents, and audit events survive process crashes.
- **Fencing tokens** — `lease_epoch` increments on every claim; stale workers cannot commit.
- **Serializable coordination** — conditional updates (`UPDATE … WHERE lease_epoch = ?`) are atomic.
- **Global footprint** — the same schema works locally and in multi-region production.

### CockroachDB tools (hackathon tool map)

| Tool | RelayGuard usage |
|------|------------------|
| **Distributed Vector Indexing** | Semantic retrieval of incidents, runbooks, and negative outcomes via `VECTOR(64)` on Cloud; `FLOAT8[]` + Python cosine fallback locally |
| **Managed MCP Server** | Read-only auditor over `audit_events`, `action_intents`, `action_results` — see `docs/mcp-auditor.md` |
| **ccloud CLI** | Cluster inspection scripts in `infra/ccloud/`; setup guide in `docs/ccloud.md` |
| **Agent Skills** | Planned optional diagnostics packaging for MemoryGate policies |

### AWS services (hackathon tool map)

| Service | RelayGuard usage |
|---------|------------------|
| **Amazon Bedrock** | Guarded action selection from allowlisted remediations (`ACTION_SELECTOR=bedrock`) |
| **AWS Lambda** | Regional worker runtime — see `docs/aws-lambda.md` |
| **CloudWatch** | Lambda worker logs and invoke-demo evidence |
| **Secrets Manager** | CockroachDB Cloud `DATABASE_URL` for Lambda (`RELAYGUARD_DATABASE_SECRET_NAME`) |
| **API Gateway** | Planned incident intake |

## M5: CockroachDB Cloud and sponsor-tool proof

Switch between local Docker and Cloud with environment variables only:

```bash
# Local (default)
RELAYGUARD_DB_TARGET=local

# CockroachDB Cloud
RELAYGUARD_DB_TARGET=cloud
DATABASE_URL_CLOUD=postgresql://...
COCKROACH_VECTOR_MODE=auto
```

```bash
python -m apps.cli.db_status          # target, vector mode, counts (no credentials)
bash infra/ccloud/check-cluster.sh    # ccloud inspection (no secrets)
```

Guides: `docs/cockroach-cloud.md`, `docs/ccloud.md`

## M6: AWS Lambda worker deployment

RelayGuard workers run on **AWS Lambda** against CockroachDB Cloud:

| Component | Role |
|-----------|------|
| **Lambda handler** | `infra/aws/lambda_worker/handler.py` — `run_worker`, `stale_commit`, `db_status` |
| **Terraform** | `infra/aws/terraform/` — execution role, CloudWatch Logs, Secrets Manager read |
| **Deploy scripts** | `infra/aws/scripts/deploy-lambda.*` |
| **Invoke demo** | `infra/aws/scripts/invoke-demo.*` — full crash handoff via Lambda |

```powershell
.\infra\aws\scripts\deploy-lambda.ps1 -DatabaseSecretArn "arn:..." -DatabaseSecretName "relayguard/db"
$env:RELAYGUARD_LAMBDA_FUNCTION_NAME = "relayguard-worker"
.\infra\aws\scripts\invoke-demo.ps1
```

- **CloudWatch** captures `[worker-a]` / `[worker-b]` logs from Lambda
- **Secrets Manager** stores `DATABASE_URL` — never logged or returned by `db_status`
- **CockroachDB Cloud** remains the memory system of record

Guide: `docs/aws-lambda.md`

## M7: Judge dashboard and timeline polish

M7 adds stable **story-ordered audit timelines** and a read-only **Next.js dashboard** for hackathon judges.

| Component | Role |
|-----------|------|
| **audit_timeline.py** | Narrative sort for audit events (retrieved before classified, failover lease after reservation) |
| **audit_incident --json** | JSON bridge for the dashboard |
| **list_incidents --json** | Recent incidents for the selector |
| **apps/web** | Next.js App Router dashboard (server-side Python bridge) |

```powershell
.\scripts\run-web.ps1
# http://localhost:3000
```

```bash
python -m apps.cli.audit_incident --incident-id <uuid> --json
python -m apps.cli.list_incidents --json
```

Guides: `docs/frontend.md`, `apps/web/DESIGN.md`

## M8: Sponsor proof pass and final demo polish

M8 packages judge-ready evidence without new backend features.

| Artifact | Purpose |
|----------|---------|
| `scripts/run-bedrock-demo.*` | One Bedrock-selected incident; logs to `docs/evidence/bedrock_selector_run.txt` |
| `scripts/capture-evidence.*` | Snapshot `db_status`, ccloud check, audit JSON/text, incident list, dashboard URLs |
| `relayguard/judge_display.py` | Display label contract (mirrored in dashboard) |
| Dashboard polish | Human action labels, selector meta, 1920×1080 layout |

```powershell
.\scripts\capture-evidence.ps1
.\scripts\run-bedrock-demo.ps1   # skips gracefully if AWS/Bedrock unavailable
.\scripts\run-web.ps1
```

### Sponsor tool proof map

| Sponsor | Tool | Working proof in RelayGuard |
|---------|------|----------------------------|
| **CockroachDB** | Cloud | System of record for incident memory, lease fencing, action ledger, audit trail (`RELAYGUARD_DB_TARGET=cloud`) |
| **CockroachDB** | Distributed Vector Indexing | Semantic retrieval of runbooks, incidents, and negative outcomes (`VECTOR(64)`, MemoryGate verdicts) |
| **CockroachDB** | Managed MCP | Read-only audit path — `docs/mcp-auditor.md`, `audit_incident` CLI, planned `relayguard.audit_incident` tool |
| **CockroachDB** | ccloud CLI | Cluster inspection — `infra/ccloud/check-cluster.*`, captured in `docs/evidence/m8_ccloud_check.txt` |
| **AWS** | Lambda | Regional worker runtime — `infra/aws/`, `docs/aws-lambda.md`, M6 evidence |
| **AWS** | Secrets Manager | CockroachDB URL for Lambda (`relayguard/db`) |
| **AWS** | CloudWatch | Worker logs from Lambda invoke demo |
| **AWS** | Bedrock | Guarded action selection — `scripts/run-bedrock-demo.*`, `selector_type=bedrock` in audit |

## M3: Bedrock action selection with guardrails

RelayGuard replaces hard-coded action picks with a pluggable **ActionSelector**:

| Component | Role |
|-----------|------|
| **MockActionSelector** | Default for local demo and CI — always selects `ROUTE_TO_STANDBY` |
| **BedrockActionSelector** | Calls Amazon Bedrock Runtime when `ACTION_SELECTOR=bedrock` |
| **RelayGuard validation** | Pydantic schema check, allowlist enforcement, confidence threshold |
| **CockroachDB** | Still the system of record for intents, commits, and audit |

**Allowed actions:** `ROUTE_TO_STANDBY`, `RESTART_SERVICE`, `ESCALATE_TO_HUMAN`

**Safety rules:**
- Bedrock must return strict JSON matching the schema
- Unknown actions, invalid JSON, or low confidence → fallback to `ESCALATE_TO_HUMAN`
- `AVOID` memory **content** is never passed to the selector (only blocked IDs + rejection reasons)
- Bedrock never writes to CockroachDB and never generates shell commands

Enable Bedrock:

```bash
ACTION_SELECTOR=bedrock
BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
AWS_REGION=us-east-1
pip install -e ".[bedrock]"
```

Audit event `action.selected` records selector type, action, confidence, reason, memory IDs used, and whether fallback was used.

## M4: Audit reader and MCP auditor

RelayGuard builds an evidence-backed **AuditReport** from CockroachDB — no UI required.

```bash
python -m apps.cli.audit_incident --incident-id <uuid>
```

The report answers:
- Why was an action selected?
- Which memories were blocked and why?
- Which worker committed after crash recovery?
- Why was a stale commit rejected?
- Did invariants pass (`PASS` / `FAIL`)?

See `docs/mcp-auditor.md` for how **Managed MCP** will expose the same read-only audit path. Application writes still go through RelayGuard workers, not MCP.

## M2: Semantic memory retrieval

RelayGuard separates **retrieval** from **validation**:

| Layer | Role |
|-------|------|
| **Vector retrieval** | Ranks memories by semantic similarity to the incident description |
| **MemoryGate** | Deterministic safety policy — high similarity does not override `AVOID` |

Retrieval uses CockroachDB `VECTOR(64)` columns with cosine distance (`<=>`). A `DeterministicEmbeddingProvider` keeps tests stable locally; swap in Bedrock Titan via the `EmbeddingProvider` protocol later.

### M2 demo output (excerpt)

```
[worker-a] score=0.842 current_runbook verdict=USE reason=active runbook approved for current incident response
[worker-a] score=0.791 historical_incident verdict=INSPECT reason=related historical incident requires human review
[worker-a] score=0.756 expired_runbook verdict=AVOID reason=runbook is expired or deprecated
[worker-a] score=0.731 failed_restart verdict=AVOID reason=prior action failed and must not be repeated
[worker-a] score=0.214 unrelated_finance verdict=AVOID reason=memory is unrelated to the active incident
```

Verification confirms:

```
Committed actions: 1
Stale commits rejected: 1
Retrieved memories: 5
AVOID memories: 3
USE memories: 1
```

### Vector indexing

Local OSS CockroachDB does not include the `VECTOR` type (enterprise license required). RelayGuard automatically falls back to `FLOAT8[]` storage and Python-side cosine ranking locally. On **CockroachDB Cloud** with vector support enabled:

```sql
ALTER TABLE memories ADD COLUMN IF NOT EXISTS embedding VECTOR(64);
CREATE VECTOR INDEX IF NOT EXISTS idx_memories_embedding ON memories (embedding);
```

See `relayguard/db.py` (`_ensure_embedding_column`) and `db/migrations/002_vector_memory.sql`.

## Local demo instructions

### Prerequisites

- Python 3.11+
- Docker (for CockroachDB)

### Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
cp .env.example .env        # Windows: copy .env.example .env
```

### Run the full demo

**Windows (PowerShell):**

```powershell
docker compose -f infra/docker-compose.yml up -d
.\scripts\run-demo.ps1
```

**macOS / Linux / Git Bash:**

```bash
bash scripts/run-demo.sh
```

This executes the complete handoff:

1. Creates an incident and seeds demo memories
2. Worker A claims, classifies memories, reserves `ROUTE_TO_STANDBY`, then crashes
3. Worker B claims with a higher fencing epoch after lease expiry
4. Worker B resumes from checkpoint and commits exactly once
5. Worker A's stale commit is rejected
6. `verify-demo.sh` confirms one committed action and a full audit trail

### Run steps manually

```bash
docker compose -f infra/docker-compose.yml up -d
python -m apps.cli.create_incident --apply-schema
# copy the printed incident UUID
export INCIDENT_ID=<uuid>

WORKER_ID=worker-a FAIL_AFTER=ACTION_RESERVED python -m apps.cli.run_worker $INCIDENT_ID
sleep 4
WORKER_ID=worker-b python -m apps.cli.run_worker $INCIDENT_ID
bash scripts/verify-demo.sh $INCIDENT_ID
```

### Tests

```powershell
# Windows — use the project venv (avoids global pytest/flake8 conflicts)
.\scripts\test.ps1 -v
```

```bash
# macOS / Linux
docker compose -f infra/docker-compose.yml up -d
.venv/bin/python -m pytest -v
```

## Hackathon judging map

| Judging criterion | RelayGuard proof |
|-------------------|------------------|
| **CockroachDB integration** | Lease fencing, vector memory retrieval, checkpoints, action ledger, audit events |
| **Vector search** | `VECTOR(64)` embeddings with cosine ranking; MemoryGate validates retrieved memories |
| **AWS integration** | Bedrock action selection; Lambda workers + CloudWatch + Secrets Manager |
| **Agent safety** | MemoryGate rejects expired/failed memories regardless of similarity score |
| **Crash recovery** | Worker B resumes from checkpoint after Worker A crash |
| **Exactly-once actions** | Idempotent `action_intents` + single `action_results` commit |
| **CockroachDB Cloud** | `RELAYGUARD_DB_TARGET=cloud`, `db_status`, `docs/cockroach-cloud.md` |
| **ccloud CLI** | `infra/ccloud/check-cluster` scripts (inspection only, no secrets) |
| **Managed MCP** | Read-only audit path in `docs/mcp-auditor.md` + `audit_incident` CLI |
| **Demo quality** | `run-demo` → verify → audit report; `Invariants: PASS` |
| **Judge dashboard** | `scripts/run-web.ps1` → proof cards, MemoryGate, timeline, ledger |
| **Sponsor evidence** | `scripts/capture-evidence.*` → `docs/evidence/m8_*` |

## Project layout

```
apps/cli/          CLI entry points
relayguard/        Models, store, embeddings, DB helpers
workers/           MemoryGate, memory retriever, worker runtime
db/                CockroachDB schema
infra/             Docker Compose, ccloud, and AWS Lambda/Terraform
scripts/           Demo and verification scripts
tests/             Pytest suite
docs/              Architecture notes
```

## License

See [LICENSE](LICENSE).
