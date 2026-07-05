# RelayGuard Frontend (M7)

Minimal read-only judge dashboard built with Next.js.

## Purpose

Show the latest RelayGuard demo result in under 30 seconds:

- Selected action (`ROUTE_TO_STANDBY`)
- One committed action, one stale rejection
- Invariants PASS
- MemoryGate verdicts
- Story-ordered execution timeline
- Action ledger and proof counts

## Architecture

```
Browser → Next.js (server) → Python CLI → CockroachDB
```

- **No** browser database access
- **No** API Gateway, SQS, or Lambda required for local demo
- `DATABASE_URL` stays server-side in Python via `.env`

## Run locally

```powershell
.\scripts\run-web.ps1
```

```bash
chmod +x scripts/run-web.sh && ./scripts/run-web.sh
```

Ensure a demo incident exists (`scripts/run-demo` or Lambda invoke).

### Troubleshooting

If you see `ENOENT ... routes-manifest.json` or a plain **Internal Server Error**:

1. Stop the dev server (`Ctrl+C` in the terminal running `run-web`).
2. Re-run `.\scripts\run-web.ps1` — it clears a stale `.next` cache before starting.

This can happen if `next build` and `next dev` were run against the same `.next` folder (common on Windows).
Do not run `npm run build` while the dev server is running.

### Final demo recording

For the hackathon video, prefer a **Bedrock-selected** incident so the dashboard shows `Selector: Bedrock`:

```powershell
$env:ACTION_SELECTOR = "bedrock"
.\scripts\run-demo.ps1
```

Then refresh the dashboard. Local mock runs display **Guarded selector** instead of the internal `mock` id.

## API (read-only)

### `GET /api/incidents`

Returns recent incidents with optional `invariant_status`.

### `GET /api/incidents/{incidentId}`

Returns dashboard view model: incident metadata, selected action, memory verdicts, timeline, ledger, proof counts.

Responses are redacted — no connection strings or secrets.

## Python bridge

The dashboard shells out to:

```bash
python -m apps.cli.list_incidents --json
python -m apps.cli.audit_incident --incident-id <uuid> --json
```

Same `AuditReader` logic as `verify_demo` and `audit_incident` CLI.

## Design

Dark navy command-center theme documented in `apps/web/DESIGN.md` (UI UX Pro direction).

## Tests

- `tests/test_m7_timeline_order.py` — story order for audit events
- `tests/test_m7_dashboard_api.py` — JSON shape, redaction, missing incident
