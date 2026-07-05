# RelayGuard on CockroachDB Cloud

This guide connects RelayGuard to a **CockroachDB Cloud** cluster while keeping the local Docker demo as fallback.

## 1. Create a cluster

1. Sign in to [CockroachDB Cloud](https://cockroachlabs.cloud/).
2. Create a cluster (Dedicated or Serverless with vector support when available).
3. Note the cluster name for `CCLOUD_CLUSTER_NAME`.

## 2. Create database and user

### Option A — Cloud Console SQL Shell (one statement per Run)

The web SQL Shell often cancels multi-statement batches (`SQLSTATE 57014`). Run **each line separately** and click **Run** after each:

```sql
CREATE DATABASE IF NOT EXISTS relayguard;
```

Switch the database dropdown from `defaultdb` to `relayguard`, then:

```sql
CREATE USER IF NOT EXISTS relayguard_app WITH PASSWORD 'choose-a-strong-password';
```

```sql
GRANT ALL ON DATABASE relayguard TO relayguard_app;
```

Verify:

```sql
SHOW DATABASES;
```

### Option B — ccloud SQL shell

```bash
ccloud auth login
ccloud cluster sql relayguard
```

Run the same SQL statements one at a time in the interactive shell.

### Option C — Console SQL Users UI

**Security → SQL Users → Add user** (`relayguard_app`), then grant access to database `relayguard` in the Console.

### Connection string

From the Console **Connect** button, or:

```bash
ccloud cluster sql --connection-url relayguard
```

Use database `relayguard` and user `relayguard_app` in `DATABASE_URL_CLOUD`.

## 3. Configure RelayGuard

Copy `.env.example` to `.env` and set:

```bash
RELAYGUARD_DB_TARGET=cloud
DATABASE_URL_CLOUD=postgresql://relayguard_app:<password>@<host>:26257/relayguard?sslmode=verify-full
COCKROACH_VECTOR_MODE=auto
CCLOUD_CLUSTER_NAME=<your-cluster>
CCLOUD_DATABASE_NAME=relayguard
```

Keep `DATABASE_URL_LOCAL` for switching back to Docker:

```bash
RELAYGUARD_DB_TARGET=local
```

## 4. Apply schema

```bash
pip install -e ".[dev]"
python -m apps.cli.create_incident --apply-schema --title "Cloud smoke test"
```

Or apply only:

```bash
python -c "from relayguard.db import apply_schema; apply_schema()"
```

On Cloud with vector support, RelayGuard prefers `VECTOR(64)` and creates `idx_memories_embedding` when available.

## 5. Check database status

```bash
python -m apps.cli.db_status
```

Expected output (Cloud with vectors):

```
Target:              cloud
Embedding storage:   vector
Vector index:        yes
```

Local Docker OSS fallback:

```
Target:              local
Embedding storage:   float8[]
Vector index:        no
```

## 6. Run the demo against Cloud

```bash
RELAYGUARD_DB_TARGET=cloud python -m apps.cli.create_incident --apply-schema
# PowerShell
$env:RELAYGUARD_DB_TARGET='cloud'; .\scripts\run-demo.ps1
```

Expected end state:

- `verify-demo` → `PASS`
- `audit_incident` → `Invariants: PASS`
- `db_status` → `embedding storage: vector` (Cloud) or `float8[]` (local)

## Troubleshooting

### SQL Shell canceled (SQLSTATE 57014)

The Cloud Console SQL Shell often fails when you paste multiple statements at once. Run **one statement per Run**, or use `ccloud cluster sql relayguard` interactively.

### SSL errors

| Symptom | Fix |
|---------|-----|
| `SSL connection required` | Use `sslmode=verify-full` or `require` in `DATABASE_URL_CLOUD` |
| `root.crt does not exist` (Windows) | Download CA cert (see below) **or** add `&sslrootcert=system` to the URL |
| Certificate verify failed | Download CA from Cloud Console; set `sslrootcert` in connection URL |

**Windows — download CA cert (one time):**

```powershell
New-Item -ItemType Directory -Force -Path "$env:APPDATA\postgresql"
Invoke-WebRequest -Uri "https://letsencrypt.org/certs/isrgrootx1.pem" -OutFile "$env:APPDATA\postgresql\root.crt"
```

CockroachDB Cloud Basic/Standard clusters use Let's Encrypt. Alternatively expand **Download CA Cert** in the Connect dialog and run the command shown there.

**Quick alternative (psycopg 3):** append `&sslrootcert=system` to `DATABASE_URL_CLOUD` to use the OS trust store instead of `root.crt`.
| `sslmode=disable` on Cloud | Remove `sslmode=disable`; Cloud requires TLS |

### Connection refused / timeout

- Confirm IP allowlist includes your machine in Cloud Console.
- Verify host/port in connection string (usually port `26257`).
- Test with `cockroach sql --url "$DATABASE_URL_CLOUD" -e "SELECT 1"`.

### VECTOR type unavailable

- Set `COCKROACH_VECTOR_MODE=float_array` for FLOAT8[] + Python cosine fallback.
- Upgrade cluster tier or enable vector features per CockroachDB Cloud docs.

### Wrong database target

```bash
python -m apps.cli.db_status
```

Confirms active `RELAYGUARD_DB_TARGET` without printing credentials.

## Switching between local and cloud

| Goal | Setting |
|------|---------|
| Local Docker demo | `RELAYGUARD_DB_TARGET=local` |
| Cloud proof | `RELAYGUARD_DB_TARGET=cloud` + `DATABASE_URL_CLOUD` |

No code changes required — only environment variables.
