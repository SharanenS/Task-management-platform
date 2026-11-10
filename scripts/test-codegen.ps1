$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repositoryRoot

try {
    $python = if (Test-Path -LiteralPath "$repositoryRoot\.venv\Scripts\python.exe") {
        "$repositoryRoot\.venv\Scripts\python.exe"
    } else {
        "python"
    }

    Write-Host "Running Non-Mutating Schema & Codegen Verification..." -ForegroundColor Cyan
    & $python scripts/verify_codegen.py
    if ($LASTEXITCODE -ne 0) {
        throw "GraphQL schema or codegen verification failed."
    }
}
finally {
    Pop-Location
}
