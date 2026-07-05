#!/usr/bin/env bash
# Deploy RelayGuard worker Lambda
set -eu

DATABASE_SECRET_ARN=""
DATABASE_SECRET_NAME=""
AWS_REGION="${AWS_REGION:-us-east-1}"
FUNCTION_NAME="relayguard-worker"

usage() {
  echo "Usage: $0 --secret-arn <arn> --secret-name <name> [--region us-east-1] [--function-name relayguard-worker]"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --secret-arn) DATABASE_SECRET_ARN="$2"; shift 2 ;;
    --secret-name) DATABASE_SECRET_NAME="$2"; shift 2 ;;
    --region) AWS_REGION="$2"; shift 2 ;;
    --function-name) FUNCTION_NAME="$2"; shift 2 ;;
    *) usage ;;
  esac
done

[[ -n "$DATABASE_SECRET_ARN" && -n "$DATABASE_SECRET_NAME" ]] || usage

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
TERRAFORM_DIR="$ROOT/infra/aws/terraform"
export ZIP_PATH="$ROOT/infra/aws/build/lambda.zip"

echo "==> Building Lambda package"
bash "$ROOT/infra/aws/scripts/build-lambda.sh"

echo "==> Terraform init"
terraform -chdir="$TERRAFORM_DIR" init -input=false

echo "==> Terraform apply"
terraform -chdir="$TERRAFORM_DIR" apply -auto-approve \
  -var="aws_region=$AWS_REGION" \
  -var="function_name=$FUNCTION_NAME" \
  -var="database_secret_arn=$DATABASE_SECRET_ARN" \
  -var="database_secret_name=$DATABASE_SECRET_NAME"

echo ""
echo "==> Deployment outputs"
terraform -chdir="$TERRAFORM_DIR" output

echo ""
echo "Deploy complete (no secrets printed)"
