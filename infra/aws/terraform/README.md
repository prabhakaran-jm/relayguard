# RelayGuard Lambda worker (Terraform)

Deploys the RelayGuard worker Lambda with CloudWatch Logs and Secrets Manager read access.

## Prerequisites

- AWS CLI configured
- Terraform >= 1.5
- Python 3.11+ with project venv
- CockroachDB Cloud secret in AWS Secrets Manager

## Secret format

Store either a plain connection string or JSON:

```json
{
  "DATABASE_URL": "postgresql://relayguard_app:***@host:26257/relayguard?sslmode=verify-full"
}
```

## Deploy

From repo root:

```powershell
.\infra\aws\scripts\deploy-lambda.ps1 `
  -DatabaseSecretArn "arn:aws:secretsmanager:us-east-1:123456789012:secret:relayguard/db-AbCdEf" `
  -DatabaseSecretName "relayguard/db"
```

```bash
bash infra/aws/scripts/deploy-lambda.sh \
  --secret-arn "arn:aws:secretsmanager:us-east-1:123456789012:secret:relayguard/db-AbCdEf" \
  --secret-name "relayguard/db"
```

The deploy script:

1. Builds `infra/aws/build/lambda.zip`
2. Runs `terraform init` and `terraform apply` in this directory

## Outputs

```bash
terraform -chdir=infra/aws/terraform output lambda_function_name
```

## Manual Terraform

```bash
cd infra/aws/terraform
terraform init
terraform apply \
  -var="database_secret_arn=arn:aws:secretsmanager:..." \
  -var="database_secret_name=relayguard/db"
```

## IAM permissions created

- `AWSLambdaBasicExecutionRole` for CloudWatch Logs
- `secretsmanager:GetSecretValue` and `DescribeSecret` on the configured secret ARN only

## Destroy

```bash
terraform -chdir=infra/aws/terraform destroy \
  -var="database_secret_arn=arn:aws:secretsmanager:..." \
  -var="database_secret_name=relayguard/db"
```
