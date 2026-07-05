# RelayGuard Managed MCP Auditor

RelayGuard treats **CockroachDB as the system of record** for incident coordination, memory decisions, and remediation actions. Managed MCP provides a **read-only audit path** for operators and review agents to interrogate that evidence without mutating application state.

## Design principle

| Path | Access |
|------|--------|
| **RelayGuard workers** | Read/write through lease-aware store (claims, checkpoints, intents, commits) |
| **Managed MCP auditor** | Read-only SQL against audit tables and reference queries |
| **Bedrock selector** | Proposes actions; RelayGuard validates and records `action.selected` |

MCP users must **never** receive write credentials. Application writes always go through RelayGuard workers — not through MCP.

## What the auditor can read

The local `AuditReader` (M4) mirrors the evidence MCP will expose:

- `incidents` — incident metadata and lease state
- `audit_events` — `memory.retrieved`, `memory.classified`, `action.selected`, checkpoints, rejections
- `action_intents` — reserved remediation ledger
- `action_results` — committed outcomes

Reference SQL lives in `db/queries/audit_incident.sql`.

## Sample natural language questions

An MCP-connected review agent can answer questions like:

### Why was ROUTE_TO_STANDBY selected?

Look up the latest `action.selected` audit event for the incident. The `details_json` field contains:

- `selector_type` (`mock` or `bedrock`)
- `action_type`
- `reason`
- `used_memory_ids` and `inspected_memory_ids`
- `fallback_used`

Cross-reference `memory.classified` events where `verdict = USE` to see which runbook evidence supported the decision.

### Which memories were rejected and why?

Filter `audit_events` where `event_type = 'memory.classified'` and `details_json->>'verdict' = 'AVOID'`. Each row includes:

- `label`
- `reason` (e.g. expired runbook, failed prior action)
- `similarity_score` from retrieval

Blocked memory **content** is intentionally excluded from action-selection prompts; MCP can still show verdict and reason for transparency.

### Which worker committed the action?

Read `action.committed` and `action_results`. The `lease_owner` and `lease_epoch` identify the worker that held the valid lease at commit time (Worker B after failover in the demo).

### Why did Worker A fail to commit?

Find `action.commit_rejected` where `lease_owner = 'worker-a'`. The `details_json.reason` is typically `stale_lease` — Worker A's fencing epoch was superseded after the crash and lease expiry.

### How many remediation actions were committed?

Count rows in `action_results` where `status = 'committed'` for the incident. RelayGuard's invariant is **exactly one** committed action per incident in the demo.

## Local equivalent

Before MCP is wired up, use the CLI auditor:

```bash
python -m apps.cli.audit_incident --incident-id <uuid>
```

This prints the same evidence chain: memory verdicts, selection reason, timeline, and invariant status (`PASS` / `FAIL`).

## Security notes

- Grant MCP **SELECT-only** on `relayguard` tables needed for audit.
- Do not expose write roles, `UPDATE`, `INSERT`, or `DELETE` to MCP tools.
- Do not allow MCP to invoke workers or Bedrock directly; it explains recorded evidence only.
- Treat MCP output as an operator aid, not an authorization to execute remediation.

## Planned MCP tool shape

```
relayguard.audit_incident(incident_id) -> AuditReport JSON
relayguard.list_incidents(status?) -> summary rows
relayguard.explain_action(incident_id) -> action.selected + supporting memory verdicts
```

Each tool maps to the queries in `db/queries/audit_incident.sql` and returns structured JSON matching `relayguard/audit_reader.py`.
