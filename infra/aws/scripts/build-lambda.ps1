param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
)

$ErrorActionPreference = "Stop"

$BuildDir = Join-Path $Root "infra\aws\build"
$PackageDir = Join-Path $BuildDir "package"
$ZipPath = Join-Path $BuildDir "lambda.zip"
$ReqFile = Join-Path $Root "infra\aws\lambda_worker\requirements.txt"
$HandlerFile = Join-Path $Root "infra\aws\lambda_worker\handler.py"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

Write-Host "==> Cleaning build directory"
if (Test-Path $PackageDir) { Remove-Item -Recurse -Force $PackageDir }
if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }
New-Item -ItemType Directory -Force -Path $PackageDir | Out-Null

Write-Host "==> Installing Lambda dependencies (Linux x86_64 for AWS Lambda)"
& $Python -m pip install -r $ReqFile -t $PackageDir --upgrade --quiet `
    --platform manylinux2014_x86_64 `
    --python-version 3.12 `
    --implementation cp `
    --only-binary=:all:

Write-Host "==> Copying RelayGuard sources"
Copy-Item -Force $HandlerFile (Join-Path $PackageDir "handler.py")
Copy-Item -Recurse -Force (Join-Path $Root "relayguard") (Join-Path $PackageDir "relayguard")
Copy-Item -Recurse -Force (Join-Path $Root "workers") (Join-Path $PackageDir "workers")
$CertsDir = Join-Path $Root "infra\aws\lambda_worker\certs"
if (Test-Path $CertsDir) {
    Copy-Item -Recurse -Force $CertsDir (Join-Path $PackageDir "certs")
}

Write-Host "==> Creating zip: $ZipPath"
Push-Location $PackageDir
try {
    Compress-Archive -Path * -DestinationPath $ZipPath -Force
} finally {
    Pop-Location
}

Write-Host "Lambda package ready: $ZipPath"
