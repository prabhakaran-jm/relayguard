# RelayGuard evidence index

Hackathon proof artifacts under `docs/evidence/`. Regenerate CLI snapshots with:

```powershell
.\scripts\capture-evidence.ps1
```

## Canonical demo incident (Bedrock + Railway)

Use this incident for the judge dashboard, Devpost screenshots, and demo video:

| Field | Value |
|-------|-------|
| **Incident ID** | `ff8d161e-4a7c-4894-9f8d-5759bd32504e` |
| **Title** | API latency spike in us-east-1, primary health checks failing |
| **Selector** | `bedrock` → dashboard shows **Amazon Bedrock** |
| **Selected action** | `ESCALATE_TO_HUMAN` (confidence 0.75) |
| **Proof counts** | 1 committed action, 1 stale commit rejected, invariants **PASS** |
| **Corpus** | 63 memories seeded; 5 retrieved; 3 AVOID, 1 USE, 1 INSPECT |
| **Bedrock story** | USE runbook supports standby routing; INSPECT precedent + blocked failures → Bedrock escalates instead of auto-remediating |

**Live dashboard (Railway):**

- Home (latest incident): https://relayguard-production.up.railway.app
- Deep link: https://relayguard-production.up.railway.app/incident/ff8d161e-4a7c-4894-9f8d-5759bd32504e

See also [`m8_dashboard_instructions.txt`](./m8_dashboard_instructions.txt) for local URLs and API routes.

**Demo video narration:** [`video-script-tts.txt`](./video-script-tts.txt) (Eleven Labs, ~3 min)

## Screen capture checklist (video / Devpost)

Open the Railway deep link above. Capture **two screenshots** or a **~30s scroll recording**:

### 1. Incident header (above the fold)

- Title: **API latency spike in us-east-1, primary health checks failing**
- Incident ID: `ff8d161e-4a7c-4894-9f8d-5759bd32504e`
- **Selector: Amazon Bedrock** (not mock, not fallback)
- **Selected: Escalate to human** with confidence **0.75**
- Bedrock reason: conflicting signals — USE runbook vs INSPECT precedent and blocked failed actions

### 2. Status cards (four tiles)

| Card | Expected value |
|------|----------------|
| Selected action | Escalate to human |
| Committed actions | **1** |
| Stale commits rejected | **1** |
| Invariants | **PASS** (green) |

### 3. MemoryGate verdicts table

Show all five rows with color-coded verdicts:

| Memory label | Verdict |
|--------------|---------|
| `failed_action_dns_cutover` | **AVOID** |
| `historical_incident` | **INSPECT** |
| `failed_action_pod_drain` | **AVOID** |
| `current_runbook` | **USE** |
| `failed_action_similar_restart` | **AVOID** |

Judges should see: similarity ranks failed actions highly, but MemoryGate blocks them. Only the approved runbook is USE; historical precedent is INSPECT.

### 4. Execution timeline (scroll down)

Story order must be visible:

1. `memories.seeded` — seeded **63** memories
2. `lease.claimed` — worker-a, epoch **1**
3. `memory.retrieved` / `memory.classified` — five verdicts
4. `action.selected` — **ESCALATE_TO_HUMAN via bedrock**
5. `action_intent.reserved` + `checkpoint.action_reserved` — Worker A crash point
6. `lease.claimed` — worker-b, epoch **2**
7. `action.committed` — Worker B single commit
8. `action.commit_rejected` — Worker A stale attempt (`already_committed`)

### 5. Action ledger + audit proof strip (bottom)

- One ledger row: `ESCALATE_TO_HUMAN` → **committed**
- Audit proof strip: retrieved **5**, blocked **3**, committed **1**, stale rejections **1**, invariants **PASS**

**Saved screenshots:**

- [`m8_dashboard_bedrock_proof.png`](./m8_dashboard_bedrock_proof.png) — header + status cards + MemoryGate (sections 1–3)
- [`m8_dashboard_bedrock_timeline.png`](./m8_dashboard_bedrock_timeline.png) — execution timeline, action ledger, audit proof strip (sections 4–5)

## Core evidence files

| File | What it proves |
|------|----------------|
| [`m8_db_status.txt`](./m8_db_status.txt) | Active DB target (`cloud`), CockroachDB version, `embedding_storage_mode=vector`, vector index, table counts — **no credentials** |
| [`m8_ccloud_check.txt`](./m8_ccloud_check.txt) | **ccloud CLI** — version, auth session, `relayguard` cluster on AWS |
| [`m8_latest_audit.txt`](./m8_latest_audit.txt) | Text audit for latest incident (`ff8d161e-…`, Bedrock guarded escalation) |
| [`m8_latest_audit.json`](./m8_latest_audit.json) | Machine-readable audit — dashboard/API parity |
| [`m8_incident_list.json`](./m8_incident_list.json) | Recent incidents with invariant status |
| [`bedrock_selector_run.txt`](./bedrock_selector_run.txt) | **Amazon Bedrock** guarded selector CLI output |
| [`m8_dashboard_instructions.txt`](./m8_dashboard_instructions.txt) | Railway + local dashboard URLs |
| [`video-script-tts.txt`](./video-script-tts.txt) | Eleven Labs narration for ~3 min demo video |
| [`m6_lambda_demo_output.txt`](./m6_lambda_demo_output.txt) | **AWS Lambda** crash handoff — Worker A reserves, Worker B commits, **PASS** |
| [`m6_lambda_db_status.txt`](./m6_lambda_db_status.txt) | Lambda `db_status` against Cloud — VECTOR mode |
| [`m6_audit_report.txt`](./m6_audit_report.txt) | Lambda incident audit (`ROUTE_TO_STANDBY`, mock selector) |

## Screenshots

| File | What it proves |
|------|----------------|
| [`m8_dashboard_bedrock_proof.png`](./m8_dashboard_bedrock_proof.png) | **Railway dashboard (top)** — Bedrock selector, MemoryGate, 1 commit / 1 stale rejection (`ff8d161e-…`) |
| [`m8_dashboard_bedrock_timeline.png`](./m8_dashboard_bedrock_timeline.png) | **Railway dashboard (scroll)** — story-ordered timeline, action ledger, audit proof strip |
| [`m6_cloudwatch_logs.png`](./m6_cloudwatch_logs.png) | **CloudWatch** — `[worker-a]` / `[worker-b]` Lambda logs |
| [`m6_cloudwatch_logs.txt`](./m6_cloudwatch_logs.txt) | Text excerpt of CloudWatch log lines |
| [`mcp_worker_rejection_question.png`](./mcp_worker_rejection_question.png) | **Managed MCP** — Cursor asks why Worker A was rejected |
| [`mcp_worker_rejection_answer.png`](./mcp_worker_rejection_answer.png) | **Managed MCP** — read-only SQL on audit tables |
| [`architecture-diagram.png`](../architecture-diagram.png) | System architecture (PNG) |
| [`architecture-diagram.svg`](../architecture-diagram.svg) | System architecture (SVG) |

### Managed MCP proof (Lambda incident)

Cursor used **CockroachDB Managed MCP** (`select_query`, read-only) on incident `c61104ce-9f84-4b51-b3f2-41c25907be5a` (Lambda / mock selector run):

| Table | What MCP showed |
|-------|-----------------|
| `audit_events` | `action_intent.reserved` (worker-a, epoch 1) → `action.committed` (worker-b, epoch 2) → `action.commit_rejected` (worker-a, `already_committed`) |
| `action_intents` | Same intent committed by worker-b at epoch 2 |
| `action_results` | One `ROUTE_TO_STANDBY` row, `status=committed`, worker-b |
| `incidents` | Lease owner worker-b, epoch 2 |

No write credentials were exposed to MCP.

## Deployment evidence

| File | What it proves |
|------|----------------|
| [`m6_deploy_output.txt`](./m6_deploy_output.txt) | Lambda deployed, **Secrets Manager** ARN wired, Terraform apply success |

## How to refresh

```powershell
# 1. Run Bedrock demo (sets ops title + ACTION_SELECTOR=bedrock)
.\scripts\run-bedrock-demo.ps1

# 2. Snapshot CLI evidence (db_status, latest audit, incident list)
.\scripts\capture-evidence.ps1

# 3. Open Railway dashboard and capture screenshots
#    docs/evidence/m8_dashboard_bedrock_proof.png
#    docs/evidence/m8_dashboard_bedrock_timeline.png

# Optional: Lambda path (separate incident, ROUTE_TO_STANDBY mock selector)
.\infra\aws\scripts\invoke-demo.ps1
```

## What judges should see

1. **CockroachDB Cloud** — VECTOR memory, durable lease + audit tables (63-entry demo corpus)
2. **Amazon Bedrock** — guarded action selector; escalates when USE and INSPECT signals conflict
3. **One committed remediation action** — 1 commit, 1 stale rejection; duplicate commits prevented
4. **MemoryGate** — high-similarity failed actions blocked; only approved runbook is USE
5. **AWS** — Lambda workers, Secrets Manager, CloudWatch (separate Lambda incident with `ROUTE_TO_STANDBY`)
6. **Read-only proof** — Railway dashboard + Managed MCP screenshots; no write credentials in the browser or MCP session
