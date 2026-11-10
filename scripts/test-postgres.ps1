param(
    [switch]$Isolated,
    [string]$EnvFile = "",
    [string]$JunitDir = ""
)

$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repositoryRoot

try {
    $python = if (Test-Path -LiteralPath "$repositoryRoot\.venv\Scripts\python.exe") {
        "$repositoryRoot\.venv\Scripts\python.exe"
    } else {
        "python"
    }

    $arguments = @("scripts/run_postgres_regression.py")
    if ($Isolated) {
        $arguments += "--isolated"
    }
    if ($EnvFile) {
        $arguments += @("--env-file", $EnvFile)
    }
    if ($JunitDir) {
        $arguments += @("--junit-dir", $JunitDir)
    }

    Write-Host "Running PostgreSQL Integration Suites..." -ForegroundColor Cyan
    & $python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "PostgreSQL regression suite failed."
    }
}
finally {
    Pop-Location
}
