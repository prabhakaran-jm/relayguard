# RelayGuard on AWS Lambda

RelayGuard workers run on **AWS Lambda** against **CockroachDB Cloud**. 
CloudWatch captures structured worker logs. **Secrets Manager** stores the database connection string.

## AWS services used

| Service | Role |
|---------|------|
| **AWS Lambda** | Regional worker runtime for `run_worker`, `stale_commit`, and `db_status` |
| **CloudWatch Logs** | Worker stdout/stderr (`[worker-a] claimed lease epoch=1`, etc.) |
| **Secrets Manager** | CockroachDB Cloud `DATABASE_URL` (never in Lambda env plaintext) |
| **IAM** | Least-privilege execution role (logs + one secret read) |

Not in scope for M6: API Gateway, SQS, Step Functions, VPC.

## Architecture

```
invoke-demo script
  ├─ create_incident (local CLI → CockroachDB Cloud)
  ├─ Lambda run_worker worker-a (crash after reserve)
  ├─ Lambda run_worker worker-b (commit)
  ├─ Lambda stale_commit worker-a (rejected)
  ├─ verify_demo (CLI)
  └─ audit_incident (CLI) → Invariants: PASS
```

CockroachDB Cloud remains the **memory system of record** — Lambda workers only coordinate through the existing RelayGuard store.

## IAM permissions

Terraform creates:

- `AWSLambdaBasicExecutionRole` → CloudWatch Logs
- Inline policy on the execution role:
  - `secretsmanager:GetSecretValue`
  - `secretsmanager:DescribeSecret`
  - Resource: your database secret ARN only

## Secrets Manager setup

1. Create a secret (Console or CLI) with either:

**Plain string**

```
postgresql://relayguard_app:<password>@<host>:26257/relayguard?sslmode=verify-full
```

**JSON**

```json
{
  "DATABASE_URL": "postgresql://relayguard_app:<password>@<host>:26257/relayguard?sslmode=verify-full"
}
```

2. Note the secret **ARN** and **name** for deploy.

Lambda environment (set by Terraform):

```bash
RELAYGUARD_DB_TARGET=cloud
RELAYGUARD_DATABASE_SECRET_NAME=relayguard/db
COCKROACH_VECTOR_MODE=auto
ACTION_SELECTOR=mock
LEASE_TTL_SECONDS=3
```

Local `.env` can still use `DATABASE_URL_CLOUD` directly. When `RELAYGUARD_DATABASE_SECRET_NAME` is set, RelayGuard loads the URL from Secrets Manager instead.

## Deploy steps

### 1. Build and deploy

**Windows**

```powershell
.\infra\aws\scripts\deploy-lambda.ps1 `
  -DatabaseSecretArn "arn:aws:secretsmanager:us-east-1:123456789012:secret:relayguard/db-AbCdEf" `
  -DatabaseSecretName "relayguard/db"
```

**macOS / Linux**

```bash
bash infra/aws/scripts/deploy-lambda.sh \
  --secret-arn "arn:aws:secretsmanager:us-east-1:123456789012:secret:relayguard/db-AbCdEf" \
  --secret-name "relayguard/db"
```

### 2. Confirm function name

```bash
terraform -chdir=infra/aws/terraform output lambda_function_name
```

## Lambda event format

### `run_worker`

```json
{
  "incident_id": "uuid",
  "worker_id": "worker-a",
  "mode": "run_worker",
  "fail_after": "ACTION_RESERVED"
}
```

Response (example):

```json
{
  "ok": true,
  "mode": "run_worker",
  "incident_id": "...",
  "worker_id": "worker-a",
  "exit_code": 2,
  "status": "simulated_crash",
  "intent_id": "...",
  "lease_epoch": 1
}
```

### `stale_commit`

```json
{
  "mode": "stale_commit",
  "incident_id": "uuid",
  "worker_id": "worker-a",
  "intent_id": "uuid",
  "lease_epoch": 1
}
```

### `db_status`

```json
{ "mode": "db_status" }
```

Returns target, version, embedding mode, counts — **no credentials**.

## Invoke demo steps

Prerequisites:

- `.env` configured for CockroachDB Cloud (`RELAYGUARD_DB_TARGET=cloud`, `DATABASE_URL_CLOUD`)
- Lambda deployed
- AWS CLI authenticated

```powershell
$env:RELAYGUARD_LAMBDA_FUNCTION_NAME = "relayguard-worker"
.\infra\aws\scripts\invoke-demo.ps1
```

```bash
export RELAYGUARD_LAMBDA_FUNCTION_NAME=relayguard-worker
bash infra/aws/scripts/invoke-demo.sh
```

## Expected output

```
==============================================
 RelayGuard Lambda handoff demo (Cloud)
==============================================
Incident ID: ...
Captured intent_id=... worker_a_epoch=1
...
--- PASS ---
RelayGuard demo verified: one committed action, semantic retrieval, MemoryGate audit trail.

RelayGuard Audit Report
...
Invariants:    PASS
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `AccessDeniedException` on invoke | IAM user/role needs `lambda:InvokeFunction` |
| `ResourceNotFoundException` | Check `RELAYGUARD_LAMBDA_FUNCTION_NAME` and region |
| `Secret ... not found` | Verify `RELAYGUARD_DATABASE_SECRET_NAME` and IAM secret ARN |
| SSL / connection errors in Lambda | Secret URL must use `sslmode=verify-full`; Cloud host must allow Lambda egress IPs or use public endpoint |
| `exit_code` not `2` for worker-a | Ensure `fail_after` is `ACTION_RESERVED` |
| Worker B fails to commit | Increase wait after worker-a; check `LEASE_TTL_SECONDS` (default 3) |

View logs:

```bash
aws logs tail /aws/lambda/relayguard-worker --follow
```

## Hackathon requirement

This satisfies the **AWS Lambda** sponsor-tool requirement by:

1. Running the same RelayGuard worker runtime on Lambda against CockroachDB Cloud
2. Preserving crash-safe lease handoff with structured Lambda responses
3. Using CloudWatch for observability and Secrets Manager for credentials
4. Ending the invoke demo with `verify_demo` and `audit_incident` → **Invariants: PASS**

Bedrock remains optional (`ACTION_SELECTOR=mock` default). Application writes still flow through RelayGuard workers — not through MCP or direct SQL from models.
