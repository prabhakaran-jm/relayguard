# RelayGuard Web Dashboard

Read-only judge-facing dashboard for RelayGuard demo incidents.

## Stack

- Next.js 15 (App Router)
- TypeScript + Tailwind CSS
- Server-side data via Python CLI (`audit_incident --json`, `list_incidents --json`)

## Quick start

From repo root:

```powershell
.\scripts\run-web.ps1
```

```bash
./scripts/run-web.sh
```

Open http://localhost:3000

## Prerequisites

- Node.js 18+
- Python venv with RelayGuard installed (`.venv`)
- `DATABASE_URL` in repo `.env` (never sent to the browser)

## Routes

| Route | Description |
|-------|-------------|
| `/` | Latest incident dashboard |
| `/incident/[id]` | Specific incident |
| `GET /api/incidents` | JSON incident list |
| `GET /api/incidents/[id]` | JSON dashboard view model |

## Design

See [DESIGN.md](./DESIGN.md) for UI UX Pro design direction (dark navy command center).
