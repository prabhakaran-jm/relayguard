$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Web = Join-Path $Root "apps\web"

Push-Location $Web
try {
    if (-not (Test-Path "node_modules")) {
        Write-Host "Installing frontend dependencies..."
        npm install
    } else {
        Write-Host "node_modules present — run 'npm install' in apps/web if deps changed."
    }

    # Mixed production `next build` + `next dev` caches can omit routes-manifest.json on Windows.
    if (Test-Path ".next") {
        Write-Host "Resetting .next cache for a clean dev session..."
        Remove-Item -Recurse -Force ".next"
    }

    Write-Host ""
    Write-Host "Starting RelayGuard dashboard at http://localhost:3000"
    npm run dev
} finally {
    Pop-Location
}
