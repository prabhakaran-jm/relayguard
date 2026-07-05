# RelayGuard Managed MCP Auditor

RelayGuard treats **CockroachDB as the system of record** for incident coordination, memory decisions, and remediation actions. Managed MCP provides a **read-only audit path** for operators and review agents to interrogate that evidence without mutating application state.

## Design principle

| Path | Access |
|------|--------|
| **RelayGuard workers** | Read/write through lease-aware store (claims, checkpoints, intents, commits) |
| **Managed MCP auditor** | Read-only SQL against audit tables and reference queries |
| **Bedrock selector** | Proposes actions; RelayGuard validates and records `action.selected` |

MCP users must **never** receive write credentials. Application writes always go through RelayGuard workers — not through MCP.

## Read-only role guidance

Create a dedicated SQL user for MCP audit access:

```sql
CREATE USER IF NOT EXISTS relayguard_mcp_auditor;
GRANT CONNECT ON DATABASE relayguard TO relayguard_mcp_auditor;
GRANT SELECT ON TABLE incidents, memories, audit_events, action_intents, action_results, checkpoints TO relayguard_mcp_auditor;
```

Do **not** grant `INSERT`, `UPDATE`, `DELETE`, or `ADMIN` to MCP users.

## Tables the auditor should inspect

| Table | Purpose |
|-------|---------|
| `incidents` | Incident metadata, lease owner, fencing epoch |
| `memories` | Seeded runbooks and outcome memories (including embeddings) |
| `audit_events` | Full evidence chain: retrieval, classification, selection, checkpoints, rejections |
| `action_intents` | Idempotent remediation reservations |
| `action_results` | Committed outcomes (exactly-once proof) |
| `checkpoints` | Worker resume state after crashes |

## Sample SQL (from `db/queries/audit_incident.sql`)

**Why was an action selected?**

```sql
SELECT details_json
FROM audit_events
WHERE incident_id = $1 AND event_type = 'action.selected'
ORDER BY created_at DESC
LIMIT 1;
```

**Which memories were rejected?**

```sql
SELECT details_json->>'label' AS label,
       details_json->>'verdict' AS verdict,
       details_json->>'reason' AS reason
FROM audit_events
WHERE incident_id = $1
  AND event_type = 'memory.classified'
  AND details_json->>'verdict' = 'AVOID';
```

**Which worker committed?**

```sql
SELECT lease_owner, lease_epoch, details_json
FROM audit_events
WHERE incident_id = $1 AND event_type = 'action.committed';
```

**Stale commit rejection**

```sql
SELECT lease_owner, lease_epoch, details_json
FROM audit_events
WHERE incident_id = $1 AND event_type = 'action.commit_rejected';
```

## Sample natural language questions

| Question | MCP should query |
|----------|------------------|
| Why was ROUTE_TO_STANDBY selected? | `action.selected` + `memory.classified` where `verdict = USE` |
| Why was RESTART_SERVICE rejected? | `memory.classified` where label/kind is `failed_restart` or `expired_runbook` with `verdict = AVOID`; confirm `action.selected.action_type` is not `RESTART_SERVICE` |
| Which memories were rejected and why? | `memory.classified` where `verdict = AVOID` |
| Which worker committed the action? | `action.committed` / `action_results.lease_owner` |
| Why did Worker A fail to commit? | `action.commit_rejected` where `lease_owner = worker-a`, reason `stale_lease` or `already_committed` |
| How many remediation actions were committed? | `COUNT(*)` from `action_results` where `status = committed` |

Blocked memory **content** is excluded from Bedrock action-selection prompts. MCP may still return `label`, `verdict`, and `reason` for transparency.

## Judge demo script

Ask the MCP auditor these questions after `run-demo`:

1. **Why was ROUTE_TO_STANDBY selected?**  
   Expect: `action.selected` with `selector_type=mock`, reason referencing approved runbook, `used_memory_ids` including current runbook.

2. **Why was RESTART_SERVICE rejected?**  
   Expect: MemoryGate `AVOID` on `failed_restart` and/or `expired_runbook`; no committed `RESTART_SERVICE` intent.

3. **Which worker committed the action?**  
   Expect: `worker-b` with higher `lease_epoch` in `action.committed`.

4. **Why did Worker A fail to commit?**  
   Expect: `action.commit_rejected` for `worker-a` with stale lease / already committed.

Local equivalent before MCP is wired:

```bash
python -m apps.cli.audit_incident --incident-id <uuid>
```

## Local equivalent

The `AuditReader` (`relayguard/audit_reader.py`) mirrors MCP responses as structured `AuditReport` JSON.

## Security notes

- Grant MCP **SELECT-only** on audit tables.
- Do not expose write roles or worker invocation through MCP.
- Do not allow MCP to call Bedrock or mutate CockroachDB.
- Treat MCP output as operator evidence, not execution authorization.

## Planned MCP tool shape

```
relayguard.audit_incident(incident_id) -> AuditReport JSON
relayguard.list_incidents(status?) -> summary rows
relayguard.explain_action(incident_id) -> action.selected + memory verdicts
```

Each tool maps to `db/queries/audit_incident.sql` and returns the same fields as `relayguard/audit_reader.py`.

## Judge-ready MCP proof (final demo)

Use this section during the hackathon recording. Managed MCP must use a **SELECT-only** SQL role — never worker write credentials.

### Screenshots placeholder

| Capture | File |
|---------|------|
| MCP auditor answering Q1 | `docs/evidence/mcp_q1_action_selection.png` |
| MCP auditor answering Q3–Q4 | `docs/evidence/mcp_q3_worker_commit.png` |
| Dashboard proof panel | `docs/evidence/m8_dashboard_proof.png` |

Run `scripts/capture-evidence.ps1` first to refresh CLI evidence under `docs/evidence/`.

### Exact questions to ask

| # | Question | Expected answer shape |
|---|----------|------------------------|
| 1 | **Why was ROUTE_TO_STANDBY selected?** | `action.selected` event: `action_type=ROUTE_TO_STANDBY`, `selector_type` (`mock` or `bedrock`), `reason` citing approved runbook, `used_memory_ids` including current runbook |
| 2 | **Which memories were rejected and why?** | Rows from `memory.classified` where `verdict=AVOID` — labels such as `expired_runbook`, `failed_restart`, `unrelated_finance` with policy reasons |
| 3 | **Which worker committed the action?** | `action.committed` / `action_results`: `lease_owner=worker-b`, `lease_epoch` higher than Worker A |
| 4 | **Why did Worker A fail to commit?** | `action.commit_rejected` for `worker-a`: stale lease or `already_committed` |
| 5 | **How many remediation actions were committed?** | Exactly **1** row in `action_results` with `status=committed` for the incident |

### Tables the auditor may read (read-only)

| Table | Fields judges care about |
|-------|--------------------------|
| `audit_events` | `event_type`, `lease_owner`, `lease_epoch`, `details_json`, `created_at` |
| `action_intents` | `action_type`, `idempotency_key`, `status` |
| `action_results` | `action_type`, `status`, `lease_owner`, `lease_epoch` |
| `incidents` | `title`, `status`, `lease_owner`, `lease_epoch` |
| `memories` | `label`, `kind` (content optional for transparency) |

### Read-only role requirement

```sql
CREATE USER IF NOT EXISTS relayguard_mcp_auditor;
GRANT CONNECT ON DATABASE relayguard TO relayguard_mcp_auditor;
GRANT SELECT ON TABLE incidents, memories, audit_events, action_intents, action_results, checkpoints TO relayguard_mcp_auditor;
-- No INSERT, UPDATE, DELETE, or ADMIN
```

MCP tools must **not** invoke workers, Bedrock, or `ccloud`. They return evidence only.

### Local equivalent (before MCP is wired)

```bash
python -m apps.cli.audit_incident --incident-id <uuid>
python -m apps.cli.audit_incident --incident-id <uuid> --json
./scripts/capture-evidence.sh
```

`AuditReader` returns the same shape as the planned `relayguard.audit_incident` MCP tool.

