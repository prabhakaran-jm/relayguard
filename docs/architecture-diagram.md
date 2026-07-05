# RelayGuard architecture diagram

Judge-facing view of how RelayGuard uses CockroachDB Cloud and AWS.

## Diagram

```mermaid
%%{init: {'theme': 'dark'}}%%
flowchart TB
  subgraph clients["Judge & operator surfaces"]
    DASH["Next.js dashboard<br/>(read-only)"]
    CLI["CLI demo scripts<br/>run-demo · verify · audit"]
    MCP["Managed MCP auditor<br/>(read-only SQL)"]
    CCLOUD["ccloud CLI<br/>(cluster evidence)"]
  end

  subgraph aws["AWS"]
    LAM_A["Lambda worker-a"]
    LAM_B["Lambda worker-b"]
    BED["Amazon Bedrock<br/>guarded selector"]
    SM["Secrets Manager<br/>DATABASE_URL"]
    CW["CloudWatch Logs"]
  end

  subgraph crdb["CockroachDB Cloud — system of record"]
    INC[("incidents")]
    MEM[("memories<br/>VECTOR retrieval")]
    CKP[("checkpoints")]
    INT[("action_intents")]
    RES[("action_results")]
    AUD[("audit_events")]
  end

  CLI -->|"1 create incident"| INC
  CLI -->|"seed memories"| MEM

  LAM_A -->|"2 retrieve candidates"| MEM
  MEM -->|"VECTOR similarity"| LAM_A
  LAM_A -->|"3 MemoryGate"| LAM_A
  LAM_A -->|"4 select action"| BED
  BED --> LAM_A
  LAM_A -->|"5 reserve"| INT
  LAM_A -->|"audit"| AUD
  LAM_A -->|"6 crash"| LAM_A

  LAM_B -->|"7 resume"| CKP
  LAM_B -->|"claim lease"| INC
  LAM_B -->|"8 commit once"| RES
  LAM_B --> AUD

  LAM_A -->|"9 stale commit rejected"| RES

  SM --> LAM_A
  SM --> LAM_B
  LAM_A --> CW
  LAM_B --> CW

  DASH --> AUD
  MCP -->|"SELECT only"| AUD
  CCLOUD -.-> crdb
```

Source: [`architecture-diagram.mmd`](./architecture-diagram.mmd)

Exported images:

- [`architecture-diagram.png`](./architecture-diagram.png)
- [`architecture-diagram.svg`](./architecture-diagram.svg)

Regenerate:

```bash
npx @mermaid-js/mermaid-cli -i docs/architecture-diagram.mmd -o docs/architecture-diagram.png -b transparent
npx @mermaid-js/mermaid-cli -i docs/architecture-diagram.mmd -o docs/architecture-diagram.svg
```

## Demo story (10 steps)

| Step | What happens | Proof |
|------|----------------|-------|
| 1 | Incident created | `incidents`, `audit_events: incident.created` |
| 2 | Worker A retrieves memory | `memories` VECTOR search, `memory.retrieved` |
| 3 | MemoryGate blocks unsafe memories | `memory.classified` with `AVOID` |
| 4 | Bedrock/mock selector picks allowlisted action | `action.selected` |
| 5 | Worker A reserves action | `action_intents`, `action_intent.reserved` |
| 6 | Worker A stops (simulated crash) | checkpoint at `ACTION_RESERVED` |
| 7 | Worker B resumes from CockroachDB | `lease.claimed` higher epoch, checkpoint read |
| 8 | Worker B commits once | single `action_results` row |
| 9 | Worker A stale commit rejected | `action.commit_rejected` |
| 10 | Dashboard and MCP read audit trail | `audit_incident`, Next.js dashboard |

## Design rules

- **Writes** go through RelayGuard workers only (CLI or Lambda).
- **Dashboard and MCP** are read-only — no direct mutation of incident state.
- **Bedrock** proposes actions; RelayGuard validates, records, and commits.
- **ccloud** is operator evidence only — not invoked by workers or models.
