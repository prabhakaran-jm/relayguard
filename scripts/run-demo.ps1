# RelayGuard end-to-end demo (Windows PowerShell)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
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

Import-RelayGuardEnv (Join-Path $Root ".env")

$DbTarget = if ($env:RELAYGUARD_DB_TARGET) { $env:RELAYGUARD_DB_TARGET.ToLower() } else { "local" }
if ($DbTarget -ne "cloud") {
    $env:DATABASE_URL = if ($env:DATABASE_URL) { $env:DATABASE_URL } else { "postgresql://root@localhost:26257/relayguard?sslmode=disable" }
}
$env:LEASE_TTL_SECONDS = if ($env:LEASE_TTL_SECONDS) { $env:LEASE_TTL_SECONDS } else { "3" }

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

$IncidentFile = Join-Path $env:TEMP "relayguard_incident_id.txt"

Write-Host "=============================================="
Write-Host " RelayGuard - crash-safe incident handoff demo"
Write-Host "=============================================="
Write-Host "Database target: $DbTarget"

if ($DbTarget -eq "cloud") {
    Write-Host "`n==> Using CockroachDB Cloud (skipping local Docker)"
} else {
    Write-Host "`n==> Starting CockroachDB"
    docker compose -f infra/docker-compose.yml up -d

    Write-Host "==> Waiting for CockroachDB"
    for ($i = 1; $i -le 30; $i++) {
        docker compose -f infra/docker-compose.yml exec -T cockroach ./cockroach sql --insecure -e "SELECT 1" 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { break }
        Start-Sleep -Seconds 1
    }
}

Write-Host "==> Applying schema and creating incident"
$DemoTitle = if ($env:RELAYGUARD_DEMO_TITLE) { $env:RELAYGUARD_DEMO_TITLE } else { "Hackathon demo incident" }
$IncidentId = & $Python -m apps.cli.create_incident --apply-schema --title $DemoTitle | Select-Object -Last 1
$IncidentId | Set-Content -Path $IncidentFile -NoNewline
Write-Host "Incident ID: $IncidentId"

Write-Host "`n==> Step 1-5: Worker A claims, classifies memories, reserves action, then crashes"
$env:WORKER_ID = "worker-a"
$env:FAIL_AFTER = "ACTION_RESERVED"
& $Python -m apps.cli.run_worker $IncidentId
$WorkerAExit = $LASTEXITCODE
if ($WorkerAExit -ne 2) {
    throw "Expected Worker A exit code 2 (simulated crash), got $WorkerAExit"
}
Write-Host "Worker A crashed after reservation (exit $WorkerAExit)"

$StateJson = & $Python scripts/demo_state.py $IncidentId | ConvertFrom-Json
$IntentId = $StateJson.intent_id
$WorkerAEpoch = $StateJson.lease_epoch
if (-not $IntentId) {
    throw "Could not resolve intent_id from checkpoint or action_intents"
}
Write-Host "Captured intent_id=$IntentId worker_a_epoch=$WorkerAEpoch"

Write-Host "`n==> Step 6-7: Waiting for lease expiry ($($env:LEASE_TTL_SECONDS)s)..."
Start-Sleep -Seconds ([int]$env:LEASE_TTL_SECONDS + 1)

Write-Host "`n==> Step 8-9: Worker B claims with higher epoch and commits once"
$env:WORKER_ID = "worker-b"
Remove-Item Env:FAIL_AFTER -ErrorAction SilentlyContinue
& $Python -m apps.cli.run_worker $IncidentId
if ($LASTEXITCODE -ne 0) { throw "Worker B failed with exit $LASTEXITCODE" }

Write-Host "`n==> Step 10: Worker A attempts stale commit (should be rejected)"
$env:WORKER_ID = "worker-a"
& $Python -m apps.cli.stale_commit $IncidentId $IntentId --worker-id worker-a --lease-epoch $WorkerAEpoch

Write-Host "`n==> Step 11: Verify demo invariants"
& $Python -m apps.cli.verify_demo $IncidentId
if ($LASTEXITCODE -ne 0) { throw "Verification failed" }

Write-Host "`n==> Step 12: Audit incident report"
& $Python -m apps.cli.audit_incident --incident-id $IncidentId
if ($LASTEXITCODE -ne 0) { throw "Audit report failed" }

Write-Host "`nDemo complete."
