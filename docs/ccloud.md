# ccloud CLI in RelayGuard

The [ccloud CLI](https://www.cockroachlabs.com/docs/cockroachcloud/ccloud-get-started) is RelayGuard's **infrastructure inspection** tool for CockroachDB Cloud. It proves cluster readiness for hackathon judging without letting models mutate infrastructure.

## What ccloud is used for

| Use | RelayGuard role |
|-----|-----------------|
| Cluster inspection | Verify Cloud cluster exists and is reachable |
| Context check | Confirm active org/project before demo |
| Hackathon evidence | Show sponsor-tool usage alongside RelayGuard app |

RelayGuard **does not** let Bedrock or workers run `ccloud` commands. Operators run ccloud manually during setup and judging.

## Setup

1. Install ccloud: https://www.cockroachlabs.com/docs/cockroachcloud/ccloud-get-started
2. Authenticate (redesigned CLI — no `ccloud config` command):

```bash
ccloud auth login
ccloud auth whoami
ccloud cluster list
ccloud cluster info relayguard
```

Connection URL template (fill in password from Console / SQL user setup):

```bash
ccloud cluster sql --connection-url relayguard
```

4. Set in `.env`:

```bash
CCLOUD_CLUSTER_NAME=relayguard
CCLOUD_DATABASE_NAME=relayguard
```

## Check cluster scripts

**Windows:**

```powershell
.\infra\ccloud\check-cluster.ps1
```

**macOS / Linux:**

```bash
bash infra/ccloud/check-cluster.sh
```

Scripts print:

- ccloud version
- active session (`auth whoami`) — no secrets
- cluster list entry for `CCLOUD_CLUSTER_NAME` when set
- database name reminder

They **never** print connection strings or passwords.

Exit code `0` = CLI available and context readable. Non-zero = install/auth failure.

## Expected output (example)

```
ccloud version: v0.5.x
Logged in as: you@example.com
Organization: prabhakaranjm.in (org-3bcbv)
Cluster lookup: relayguard
Cluster state: CREATED
Database expected: relayguard
```

If you see `unknown command "config"` or `unknown command "organization"`, your ccloud build uses the redesigned CLI — use `ccloud auth whoami` and `ccloud cluster list` instead.

## Hackathon usage

This satisfies **ccloud CLI** sponsor-tool requirements by:

1. Documenting cluster provisioning (`docs/cockroach-cloud.md`)
2. Providing inspection scripts (`infra/ccloud/`)
3. Showing `db_status` against Cloud with `RELAYGUARD_DB_TARGET=cloud`

RelayGuard application code connects via `DATABASE_URL_CLOUD` — ccloud is for operator workflow, not runtime mutation by AI agents.

## Safety

- Do not embed ccloud credentials in repo or MCP tools.
- Do not grant MCP write access to Cloud API.
- Use ccloud for human setup and judge demos only.
