# RelayGuard evidence index



Hackathon proof artifacts captured under `docs/evidence/`. Regenerate with:



```powershell

.\scripts\capture-evidence.ps1

```



## Core evidence files



| File | What it proves |

|------|----------------|

| [`m8_db_status.txt`](./m8_db_status.txt) | Active DB target (`cloud`), CockroachDB version, `embedding_storage_mode=vector`, vector index present, table counts — **no credentials** |

| [`m8_ccloud_check.txt`](./m8_ccloud_check.txt) | **ccloud CLI** works: version, auth session, `relayguard` cluster `CREATED` on AWS |

| [`m6_lambda_demo_output.txt`](./m6_lambda_demo_output.txt) | **AWS Lambda** crash handoff demo: Worker A reserves, Worker B commits, verify **PASS** |

| [`m6_lambda_db_status.txt`](./m6_lambda_db_status.txt) | Lambda `db_status` against Cloud — VECTOR mode from regional worker |

| [`m6_audit_report.txt`](./m6_audit_report.txt) | Text audit report: `ROUTE_TO_STANDBY`, 1 commit, 1 stale rejection, **Invariants PASS** |

| [`m8_latest_audit.txt`](./m8_latest_audit.txt) | Latest incident audit (refreshed by capture-evidence) |

| [`m8_latest_audit.json`](./m8_latest_audit.json) | Machine-readable audit for dashboard/API parity |

| [`m8_incident_list.json`](./m8_incident_list.json) | Recent incidents with invariant status |

| [`bedrock_selector_run.txt`](./bedrock_selector_run.txt) | **Amazon Bedrock** guarded selector demo output, or graceful skip reason if credentials unavailable |

| [`m8_dashboard_instructions.txt`](./m8_dashboard_instructions.txt) | URLs to open the judge dashboard locally |



## Screenshots



| File | What it proves |

|------|----------------|

| [`m6_cloudwatch_logs.png`](./m6_cloudwatch_logs.png) | **CloudWatch** captures `[worker-a]` / `[worker-b]` Lambda execution logs |

| [`m6_cloudwatch_logs.txt`](./m6_cloudwatch_logs.txt) | Text excerpt of CloudWatch log lines |

| [`mcp_worker_rejection_question.png`](./mcp_worker_rejection_question.png) | **Managed MCP** — Cursor asks why Worker A was rejected after it returned |

| [`mcp_worker_rejection_answer.png`](./mcp_worker_rejection_answer.png) | **Managed MCP** — read-only `select_query` on `audit_events`, `action_intents`, `action_results`, `incidents`; answer shows `already_committed`, Worker B epoch 2 |

| [`architecture-diagram.png`](../architecture-diagram.png) | System architecture (PNG export from Mermaid) |

| [`architecture-diagram.svg`](../architecture-diagram.svg) | System architecture (SVG export from Mermaid) |

| `m8_dashboard_proof.png` | Dashboard proof cards — optional capture for Devpost/video |



### Managed MCP proof (captured)



Cursor used **CockroachDB Managed MCP** (`select_query`, read-only) to inspect RelayGuard audit tables for incident `c61104ce-9f84-4b51-b3f2-41c25907be5a`:



| Table | What MCP showed |

|-------|-----------------|

| `audit_events` | `action_intent.reserved` (worker-a, epoch 1) → `action.committed` (worker-b, epoch 2) → `action.commit_rejected` (worker-a, `already_committed`) |

| `action_intents` | Same intent committed by worker-b at epoch 2 |

| `action_results` | One `ROUTE_TO_STANDBY` row, `status=committed`, worker-b |

| `incidents` | Current lease owner worker-b, epoch 2, status resolved |



No write credentials were exposed to MCP.



## Deployment evidence



| File | What it proves |

|------|----------------|

| [`m6_deploy_output.txt`](./m6_deploy_output.txt) | Lambda function deployed, **Secrets Manager** ARN wired, Terraform apply success |



## How to refresh



```powershell

# Snapshot CLI evidence

.\scripts\capture-evidence.ps1



# Full local demo (mock selector)

.\scripts\run-demo.ps1



# Bedrock selector (optional)

.\scripts\run-bedrock-demo.ps1



# Lambda demo (requires deploy)

.\infra\aws\scripts\invoke-demo.ps1

```



## What judges should see



1. **CockroachDB Cloud** — VECTOR memory, durable lease + audit tables

2. **One committed remediation action** in RelayGuard's ledger — 1 commit, 1 stale rejection; duplicate committed actions prevented inside RelayGuard

3. **MemoryGate** — unsafe memories blocked despite high similarity

4. **AWS** — Lambda workers, Secrets Manager, CloudWatch

5. **Read-only proof** — dashboard + **Managed MCP** screenshots (`mcp_worker_rejection_*.png`), no write credentials exposed


