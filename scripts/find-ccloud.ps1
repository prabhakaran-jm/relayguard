# Find ccloud on this machine (for CCLOUD_BIN in .env)
$ErrorActionPreference = "SilentlyContinue"
$found = @()

if (Get-Command ccloud -ErrorAction SilentlyContinue) {
    $found += (Get-Command ccloud).Source
}

$candidates = @(
    "$env:APPDATA\ccloud\ccloud.exe",
    "$env:LOCALAPPDATA\ccloud\ccloud.exe",
    "$env:USERPROFILE\ccloud\ccloud.exe",
    "$PSScriptRoot\..\ccloud\ccloud.exe",
    "$env:LOCALAPPDATA\Microsoft\WinGet\Links\ccloud.exe",
    "$env:USERPROFILE\scoop\shims\ccloud.exe"
)

foreach ($path in $candidates) {
    if (Test-Path $path) { $found += (Resolve-Path $path).Path }
}

$found = $found | Select-Object -Unique

if (-not $found) {
    Write-Host "ccloud not found. Install from:"
    Write-Host "  https://www.cockroachlabs.com/docs/cockroachcloud/ccloud-get-started"
    exit 1
}

Write-Host "Found ccloud:"
foreach ($path in $found) {
    Write-Host "  $path"
}
Write-Host ""
Write-Host "Add to .env:"
Write-Host "CCLOUD_BIN=$($found[0])"
