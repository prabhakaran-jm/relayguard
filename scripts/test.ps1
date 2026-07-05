# Run tests using the project venv (avoids global pytest plugin conflicts)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Host "Virtual env not found. Run: python -m venv .venv; .\.venv\Scripts\pip install -e `".[dev]`""
    exit 1
}

& $Python -m pytest @args
