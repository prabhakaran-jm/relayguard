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

### CockroachDB tools planned

| Tool | Role in RelayGuard |
|------|-------------------|
| **Distributed Vector Indexing** | Semantic retrieval of runbooks and incident memories |
| **Managed MCP** | Read-only audit and memory queries for operator agents |
| **Agent Skills** | Packaged MemoryGate and action-policy skills for Cursor agents |
| **ccloud CLI** | Provision and manage CockroachDB Cloud clusters for demos |

## AWS services planned

| Service | Role in RelayGuard |
|---------|-------------------|
| **Amazon Bedrock** | Action selection from allowlisted remediations |
| **AWS Lambda** | Regional incident workers |
| **API Gateway** | Incident intake and webhook endpoints |
| **CloudWatch** | Alerts, structured logs, demo observability |
| **Secrets Manager** | Database and model credentials |

> The first local proof mocks the model with a deterministic `ROUTE_TO_STANDBY` decision. Bedrock is not called yet.

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
| **AWS integration** | Architecture planned; Bedrock for action selection, Lambda workers, API Gateway intake |
| **Agent safety** | MemoryGate rejects expired/failed memories regardless of similarity score |
| **Crash recovery** | Worker B resumes from checkpoint after Worker A crash |
| **Exactly-once actions** | Idempotent `action_intents` + single `action_results` commit |
| **Auditability** | `audit_events` table records every state transition and rejection |
| **Demo quality** | `run-demo.sh` + `verify-demo.sh` with clean CLI output |

## Project layout

```
apps/cli/          CLI entry points
relayguard/        Models, store, embeddings, DB helpers
workers/           MemoryGate, memory retriever, worker runtime
db/                CockroachDB schema
infra/             Docker Compose for local CockroachDB
scripts/           Demo and verification scripts
tests/             Pytest suite
docs/              Architecture notes
```

## License

See [LICENSE](LICENSE).
