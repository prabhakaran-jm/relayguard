# RelayGuard judge dashboard (Railway)

Single-container image: Python 3.11 + Node 20 + Next.js.

The dashboard shells out to the same Python CLIs used locally (`list_incidents`, `audit_incident`), so Railway must run the **repo root** context with both runtimes installed.

## Build

```bash
docker build -f infra/railway/Dockerfile -t relayguard-web .
```

## Run locally (smoke test)

```bash
docker run --rm -p 3000:3000 \
  -e RELAYGUARD_DB_TARGET=cloud \
  -e DATABASE_URL_CLOUD="postgresql://..." \
  relayguard-web
```

Open `http://localhost:3000`.

## Deploy to Railway

### 1. Install CLI and log in

```powershell
npm i -g @railway/cli
railway login
```

### 2. Create project and link repo

From the repo root:

```powershell
railway init
```

Or link an existing project:

```powershell
railway link
```

### 3. Set environment variables

In the Railway dashboard (**Variables**) or via CLI:

| Variable | Example | Required |
|----------|---------|----------|
| `RELAYGUARD_DB_TARGET` | `cloud` | yes |
| `DATABASE_URL_CLOUD` | `postgresql://relayguard:...@...cockroachlabs.cloud:26257/relayguard?sslmode=verify-full` | yes |
| `COCKROACH_VECTOR_MODE` | `vector` | recommended for Cloud |

Do **not** commit connection strings. Paste `DATABASE_URL_CLOUD` in Railway only.

### 4. Deploy

Railway reads [`railway.toml`](../../railway.toml) at the repo root and builds `infra/railway/Dockerfile`.

```powershell
.\scripts\deploy-web-railway.ps1
```

Or:

```bash
railway up
```

### 5. Generate public URL

```powershell
railway domain
```

Railway sets `PORT` automatically; the container binds Next.js to that port.

## Architecture on Railway

```
Browser → Next.js (Node) → python -m apps.cli.* → CockroachDB Cloud
```

Same path as local `run-web.ps1`, but `DATABASE_URL` never leaves the server.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `No incidents found` | Run a demo against the same Cloud DB (`run-demo` or Lambda) so data exists |
| Python `ModuleNotFoundError` | Rebuild image — `pip install .` runs at Docker build time |
| DB SSL errors | Image bundles `infra/aws/lambda_worker/certs/root.crt` at `/app/certs/root.crt` for CockroachDB Cloud |
| Build fails on `npm ci` | Ensure `apps/web/package-lock.json` is committed |
| Build fails prerendering `/` | Pages use `force-dynamic` — data loads at request time, not build time |

## Tests

Local dashboard API tests still use Docker CockroachDB:

- `tests/test_m7_dashboard_api.py`
