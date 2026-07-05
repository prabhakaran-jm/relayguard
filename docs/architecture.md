# RelayGuard

Architecture notes for the CockroachDB × AWS Hackathon submission.

## Components

| Path | Purpose |
|------|---------|
| `relayguard/` | Core models, DB access, lease-aware store |
| `workers/` | MemoryGate classification and worker runtime |
| `apps/cli/` | CLI entry points for demo and verification |
| `db/` | CockroachDB schema |
| `infra/` | Local CockroachDB via Docker Compose |
| `scripts/` | `run-demo.sh`, `verify-demo.sh` |
| `tests/` | Pytest coverage for fencing, idempotency, MemoryGate |

## Lease + fencing

Every state-changing update checks `incident_id`, `lease_owner`, and `lease_epoch`.
Stale workers update zero rows and emit an `audit_events` record.

## Demo flow

See `scripts/run-demo.sh` for the full Worker A → crash → Worker B handoff.
