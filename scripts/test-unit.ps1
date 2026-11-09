$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repositoryRoot

try {
    $python = if (Test-Path -LiteralPath "$repositoryRoot\.venv\Scripts\python.exe") {
        "$repositoryRoot\.venv\Scripts\python.exe"
    } else {
        "python"
    }

    $reportDir = Join-Path $repositoryRoot "test-results\reports\unit"
    if (-not (Test-Path -LiteralPath $reportDir)) {
        New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
    }

    Write-Host "==============================================" -ForegroundColor Cyan
    Write-Host "Running Backend Pytest Unit Suites" -ForegroundColor Cyan
    Write-Host "==============================================" -ForegroundColor Cyan

    $backendSuites = @(
        @{ Name = "Gateway"; Path = "gateway/tests"; Report = "pytest-gateway.xml"; Ignore = $null },
        @{ Name = "Employee"; Path = "services/employee/tests"; Report = "pytest-employee.xml"; Ignore = $null },
        @{ Name = "Work"; Path = "services/work/tests"; Report = "pytest-work.xml"; Ignore = "services/work/tests/test_postgres.py" },
        @{ Name = "Job"; Path = "services/job/tests"; Report = "pytest-job.xml"; Ignore = "services/job/tests/test_postgres.py" },
        @{ Name = "Workflow"; Path = "services/workflow/tests"; Report = "pytest-workflow.xml"; Ignore = "services/workflow/tests/test_postgres.py" },
        @{ Name = "Notification"; Path = "services/notification/tests"; Report = "pytest-notification.xml"; Ignore = "services/notification/tests/test_postgres.py" }
    )

    foreach ($suite in $backendSuites) {
        Write-Host "`n--> Suite: $($suite.Name) ($($suite.Path))" -ForegroundColor Yellow
        $junitPath = Join-Path $reportDir $suite.Report
        $pytestArgs = @($suite.Path, "-v", "--tb=short", "--junitxml=$junitPath")
        if ($suite.Ignore) {
            $pytestArgs += "--ignore=$($suite.Ignore)"
        }
        & $python -m pytest @pytestArgs
        if ($LASTEXITCODE -ne 0) {
            throw "Unit test suite failed for $($suite.Name)."
        }
    }

    Write-Host "`n==============================================" -ForegroundColor Cyan
    Write-Host "Running Frontend Vitest Component Suites" -ForegroundColor Cyan
    Write-Host "==============================================" -ForegroundColor Cyan

    $vitestJunit = Join-Path $reportDir "vitest.xml"
    & npm --prefix frontend test -- --reporter=default --reporter=junit "--outputFile=$vitestJunit"
    if ($LASTEXITCODE -ne 0) {
        throw "Frontend Vitest test suite failed."
    }

    Write-Host "`n==============================================" -ForegroundColor Cyan
    Write-Host "Verifying Machine-Readable Test Reports" -ForegroundColor Cyan
    Write-Host "==============================================" -ForegroundColor Cyan

    & $python scripts/verify_test_reports.py --unit-dir test-results/reports/unit
    if ($LASTEXITCODE -ne 0) {
        throw "Unit test report verification failed (zero-skip fail-closed policy)."
    }

    Write-Host "`nAll Backend and Frontend Unit Suites Passed and Verified Successfully!" -ForegroundColor Green
}
finally {
    Pop-Location
}
