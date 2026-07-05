$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

Push-Location $Root
try {
    if (-not (Get-Command railway -ErrorAction SilentlyContinue)) {
        Write-Host "Install Railway CLI: npm i -g @railway/cli"
        exit 1
    }

    Write-Host "Deploying RelayGuard dashboard to Railway..."
    Write-Host "Ensure RELAYGUARD_DB_TARGET=cloud and DATABASE_URL_CLOUD are set in Railway Variables."
    railway up
} finally {
    Pop-Location
}
