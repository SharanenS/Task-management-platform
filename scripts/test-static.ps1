$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repositoryRoot

try {
    $python = if (Test-Path -LiteralPath "$repositoryRoot\.venv\Scripts\python.exe") {
        "$repositoryRoot\.venv\Scripts\python.exe"
    } else {
        "python"
    }

    Write-Host "=== 1/6 Python Linting (Ruff) ===" -ForegroundColor Cyan
    & $python -m ruff check gateway services
    if ($LASTEXITCODE -ne 0) { throw "Ruff check failed." }

    Write-Host "=== 2/6 Python Formatting (Ruff) ===" -ForegroundColor Cyan
    & $python -m ruff format --check gateway services
    if ($LASTEXITCODE -ne 0) { throw "Ruff format check failed." }

    Write-Host "=== 3/6 Python Type Checking (MyPy) ===" -ForegroundColor Cyan
    $services = @("gateway", "services/employee", "services/work", "services/job", "services/workflow", "services/notification")
    foreach ($svc in $services) {
        Write-Host "  -> MyPy $svc"
        & $python -m mypy --config-file "$svc/pyproject.toml" "$svc/app"
        if ($LASTEXITCODE -ne 0) { throw "MyPy check failed for $svc." }
    }

    Write-Host "=== 4/6 Frontend Formatting (Prettier) ===" -ForegroundColor Cyan
    npm --prefix frontend run format:check
    if ($LASTEXITCODE -ne 0) { throw "Prettier format check failed." }

    Write-Host "=== 5/6 Frontend Linting (ESLint) ===" -ForegroundColor Cyan
    npm --prefix frontend run lint
    if ($LASTEXITCODE -ne 0) { throw "ESLint check failed." }

    Write-Host "=== 6/6 Frontend Type Checking (TypeScript) ===" -ForegroundColor Cyan
    npm --prefix frontend run typecheck
    if ($LASTEXITCODE -ne 0) { throw "TypeScript type check failed." }

    Write-Host "`nAll static checks passed successfully!" -ForegroundColor Green
}
finally {
    Pop-Location
}
