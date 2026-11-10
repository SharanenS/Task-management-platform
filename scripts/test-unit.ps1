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

    function Get-ServicePython {
        param([string]$svc)
        $svcDir = Join-Path $repositoryRoot $svc
        $svcWinVenv = Join-Path $svcDir ".venv\Scripts\python.exe"
        if (Test-Path -LiteralPath $svcWinVenv) {
            return $svcWinVenv
        }
        $svcBaseName = Split-Path $svc -Leaf
        $rootNamedVenv = Join-Path $repositoryRoot ".venv\$svcBaseName\Scripts\python.exe"
        if (Test-Path -LiteralPath $rootNamedVenv) {
            return $rootNamedVenv
        }
        return $python
    }

    $backendSuites = @(
        @{ Name = "Gateway"; Svc = "gateway"; Report = "pytest-gateway.xml"; Ignore = $null },
        @{ Name = "Employee"; Svc = "services/employee"; Report = "pytest-employee.xml"; Ignore = $null },
        @{ Name = "Work"; Svc = "services/work"; Report = "pytest-work.xml"; Ignore = "tests/test_postgres.py" },
        @{ Name = "Job"; Svc = "services/job"; Report = "pytest-job.xml"; Ignore = "tests/test_postgres.py" },
        @{ Name = "Workflow"; Svc = "services/workflow"; Report = "pytest-workflow.xml"; Ignore = "tests/test_postgres.py" },
        @{ Name = "Notification"; Svc = "services/notification"; Report = "pytest-notification.xml"; Ignore = "tests/test_postgres.py" }
    )

    foreach ($suite in $backendSuites) {
        Write-Host "`n--> Suite: $($suite.Name) ($($suite.Svc))" -ForegroundColor Yellow
        $junitPath = Join-Path $reportDir $suite.Report
        $svcPython = Get-ServicePython $suite.Svc
        $pytestArgs = @("tests", "-v", "--tb=short", "--junitxml=$junitPath")
        if ($suite.Ignore) {
            $pytestArgs += "--ignore=$($suite.Ignore)"
        }
        Push-Location (Join-Path $repositoryRoot $suite.Svc)
        try {
            & $svcPython -m pytest @pytestArgs
            if ($LASTEXITCODE -ne 0) {
                throw "Unit test suite failed for $($suite.Name)."
            }
        }
        finally {
            Pop-Location
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
