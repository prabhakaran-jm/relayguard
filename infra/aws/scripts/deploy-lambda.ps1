# Deploy RelayGuard worker Lambda
param(
    [Parameter(Mandatory = $true)]
    [string]$DatabaseSecretArn,
    [Parameter(Mandatory = $true)]
    [string]$DatabaseSecretName,
    [string]$AwsRegion = $(if ($env:AWS_REGION) { $env:AWS_REGION } else { "us-east-1" }),
    [string]$FunctionName = "relayguard-worker"
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
$TerraformDir = Join-Path $Root "infra\aws\terraform"

Write-Host "==> Building Lambda package"
& (Join-Path $PSScriptRoot "build-lambda.ps1") -Root $Root

Write-Host "==> Terraform init"
Push-Location $TerraformDir
try {
    terraform init -input=false
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "==> Terraform apply"
    terraform apply -auto-approve `
        -var="aws_region=$AwsRegion" `
        -var="function_name=$FunctionName" `
        -var="database_secret_arn=$DatabaseSecretArn" `
        -var="database_secret_name=$DatabaseSecretName"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "`n==> Deployment outputs"
    terraform output
} finally {
    Pop-Location
}

Write-Host "`nDeploy complete (no secrets printed)"
