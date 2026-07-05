# Invoke RelayGuard Lambda crash-safe handoff demo against CockroachDB Cloud
param(
    [string]$FunctionName = $(if ($env:RELAYGUARD_LAMBDA_FUNCTION_NAME) { $env:RELAYGUARD_LAMBDA_FUNCTION_NAME } else { "relayguard-worker" }),
    [string]$AwsRegion = $(if ($env:AWS_REGION) { $env:AWS_REGION } else { "us-east-1" })
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
Set-Location $Root

function Import-RelayGuardEnv {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if ($line -eq "" -or $line.StartsWith("#")) { return }
        $eq = $line.IndexOf("=")
        if ($eq -lt 1) { return }
        $name = $line.Substring(0, $eq).Trim()
        $value = $line.Substring($eq + 1).Trim()
        if ([string]::IsNullOrEmpty([Environment]::GetEnvironmentVariable($name, "Process"))) {
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

function Invoke-RelayGuardLambda {
    param(
        [hashtable]$Payload,
        [string]$Label
    )
    $PayloadFile = Join-Path $env:TEMP "relayguard-lambda-payload.json"
    $ResponseFile = Join-Path $env:TEMP "relayguard-lambda-response.json"
    $json = ($Payload | ConvertTo-Json -Compress)
    [System.IO.File]::WriteAllText($PayloadFile, $json)
    Write-Host "`n==> Lambda invoke: $Label"
    $payloadUri = "file://" + ($PayloadFile -replace '\\', '/')
    aws lambda invoke `
        --function-name $FunctionName `
        --region $AwsRegion `
        --cli-binary-format raw-in-base64-out `
        --payload $payloadUri `
        $ResponseFile 2>&1 | Out-String | Write-Verbose
    if ($LASTEXITCODE -ne 0) { throw "Lambda invoke failed: $Label" }
    $body = Get-Content $ResponseFile -Raw | ConvertFrom-Json
    if (-not $body.ok) {
        throw "Lambda returned error for ${Label}: $($body.error)"
    }
    return $body
}

Import-RelayGuardEnv (Join-Path $Root ".env")
$env:RELAYGUARD_DB_TARGET = "cloud"
$LeaseTtl = if ($env:LEASE_TTL_SECONDS) { [int]$env:LEASE_TTL_SECONDS } else { 3 }

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

Write-Host "=============================================="
Write-Host " RelayGuard Lambda handoff demo (Cloud)"
Write-Host "=============================================="
Write-Host "Function: $FunctionName"
Write-Host "Region:   $AwsRegion"

Write-Host "`n==> Creating incident on CockroachDB Cloud"
$IncidentId = & $Python -m apps.cli.create_incident --apply-schema --title "Lambda handoff demo" | Select-Object -Last 1
Write-Host "Incident ID: $IncidentId"

$WorkerA = Invoke-RelayGuardLambda @{
    mode        = "run_worker"
    incident_id = $IncidentId
    worker_id   = "worker-a"
    fail_after  = "ACTION_RESERVED"
} "worker-a crash after reserve"
if ($WorkerA.exit_code -ne 2) {
    throw "Expected worker-a exit_code 2, got $($WorkerA.exit_code)"
}
$IntentId = $WorkerA.intent_id
$WorkerAEpoch = $WorkerA.lease_epoch
if (-not $IntentId) { throw "Lambda response missing intent_id" }
Write-Host "Captured intent_id=$IntentId worker_a_epoch=$WorkerAEpoch"

Write-Host "`n==> Waiting for lease expiry (${LeaseTtl}s)..."
Start-Sleep -Seconds ($LeaseTtl + 1)

$WorkerB = Invoke-RelayGuardLambda @{
    mode        = "run_worker"
    incident_id = $IncidentId
    worker_id   = "worker-b"
} "worker-b commit"
if ($WorkerB.exit_code -ne 0) {
    throw "Expected worker-b exit_code 0, got $($WorkerB.exit_code)"
}

$Stale = Invoke-RelayGuardLambda @{
    mode        = "stale_commit"
    incident_id = $IncidentId
    worker_id   = "worker-a"
    intent_id   = $IntentId
    lease_epoch = $WorkerAEpoch
} "worker-a stale commit"
if (-not $Stale.rejected) {
    throw "Expected stale commit rejection"
}

Write-Host "`n==> Verify demo invariants"
& $Python -m apps.cli.verify_demo $IncidentId
if ($LASTEXITCODE -ne 0) { throw "Verification failed" }

Write-Host "`n==> Audit incident report"
& $Python -m apps.cli.audit_incident --incident-id $IncidentId
if ($LASTEXITCODE -ne 0) { throw "Audit report failed" }

Write-Host "`nLambda demo complete."
