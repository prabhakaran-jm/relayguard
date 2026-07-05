# RelayGuard Bedrock selector demo — same crash handoff with ACTION_SELECTOR=bedrock.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$EvidenceDir = Join-Path $Root "docs\evidence"
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
$LogFile = Join-Path $EvidenceDir "bedrock_selector_run.txt"

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

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$Region = if ($env:AWS_REGION) { $env:AWS_REGION } else { "us-east-1" }
$preflight = @"
import json, sys
try:
    import boto3
except ImportError:
    print(json.dumps({"ok": False, "reason": "boto3 not installed — pip install -e '.[bedrock]'"}))
    sys.exit(0)
try:
    boto3.client("bedrock-runtime", region_name="$Region")
    print(json.dumps({"ok": True}))
except Exception as exc:
    print(json.dumps({"ok": False, "reason": str(exc)}))
"@

"" | Set-Content -Path $LogFile -Encoding utf8
Add-Content -Path $LogFile -Value "RelayGuard Bedrock selector demo"
Add-Content -Path $LogFile -Value "================================"
Add-Content -Path $LogFile -Value "Started: $(Get-Date -Format o)"
Add-Content -Path $LogFile -Value ""

$preflightOut = $preflight | & $Python -c $preflight 2>&1 | Out-String
Add-Content -Path $LogFile -Value $preflightOut.TrimEnd()
Write-Host $preflightOut.TrimEnd()

try {
    $check = $preflightOut | ConvertFrom-Json
    if (-not $check.ok) {
        Add-Content -Path $LogFile -Value ""
        Add-Content -Path $LogFile -Value "SKIPPED: Bedrock unavailable."
        Add-Content -Path $LogFile -Value "Reason: $($check.reason)"
        Write-Host "SKIPPED: $($check.reason)"
        exit 0
    }
} catch {
    Add-Content -Path $LogFile -Value "SKIPPED: could not parse Bedrock preflight."
    exit 0
}

$env:ACTION_SELECTOR = "bedrock"
$env:RELAYGUARD_DEMO_TITLE = "API latency spike in us-east-1, primary health checks failing"

& (Join-Path $Root "scripts\run-demo.ps1") *>&1 | ForEach-Object {
    Write-Host $_
    Add-Content -Path $LogFile -Value $_
}

if ($LASTEXITCODE -ne 0) {
    Add-Content -Path $LogFile -Value "Demo failed with exit $LASTEXITCODE"
    exit $LASTEXITCODE
}

Add-Content -Path $LogFile -Value ""
Add-Content -Path $LogFile -Value "Finished: $(Get-Date -Format o)"
Write-Host "`nBedrock demo log: $LogFile"
