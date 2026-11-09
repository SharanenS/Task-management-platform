$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repositoryRoot

try {
    $python = if (Test-Path -LiteralPath "$repositoryRoot\.venv\Scripts\python.exe") {
        "$repositoryRoot\.venv\Scripts\python.exe"
    } else {
        "python"
    }

    Write-Host "==============================================" -ForegroundColor Cyan
    Write-Host "Frontend Production Dependency Audit (npm)" -ForegroundColor Cyan
    Write-Host "==============================================" -ForegroundColor Cyan

    & npm --prefix frontend audit --omit=dev
    $npmExit = $LASTEXITCODE
    if ($npmExit -ne 0) {
        if ($npmExit -eq 1) {
            throw "npm audit found production dependency vulnerabilities."
        } else {
            throw "npm audit tool or network connection failed (exit code $npmExit). Check network connectivity to npm registry."
        }
    }

    Write-Host "`n==============================================" -ForegroundColor Cyan
    Write-Host "Python Service Lockfile Audits (pip-audit)" -ForegroundColor Cyan
    Write-Host "==============================================" -ForegroundColor Cyan

    $lockfiles = @(
        "gateway/requirements.lock",
        "services/employee/requirements.lock",
        "services/work/requirements.lock",
        "services/job/requirements.lock",
        "services/workflow/requirements.lock",
        "services/notification/requirements.lock"
    )

    foreach ($lock in $lockfiles) {
        Write-Host "`n--> Auditing $lock..." -ForegroundColor Yellow
        & $python -m pip_audit -r $lock
        $pipExit = $LASTEXITCODE
        if ($pipExit -ne 0) {
            if ($pipExit -eq 1) {
                throw "pip-audit reported known vulnerabilities in $lock."
            } else {
                throw "pip-audit tool or network failure auditing $lock (exit code $pipExit). Check PyPI / OSV advisory API connectivity."
            }
        }
    }

    Write-Host "`nAll frontend and backend dependency audits passed cleanly with 0 known vulnerabilities!" -ForegroundColor Green
}
finally {
    Pop-Location
}
