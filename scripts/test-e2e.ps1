param(
    [string]$Project = "desktop",
    [string]$Spec = "",
    [string]$Grep = "",
    [string]$BaseUrl = "",
    [string]$EnvFile = "",
    [switch]$Isolated,
    [switch]$IncludeAuth,
    [switch]$Recovery,
    [string]$ReportPath = "test-results/reports/playwright/report.json",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repositoryRoot

try {
    $settings = @{}

    if ($Isolated) {
        if (-not $EnvFile -or -not (Test-Path -LiteralPath $EnvFile)) {
            throw "Fail-closed isolated mode requires an existing test environment file via -EnvFile. Refusing to fall back to development .env or development endpoints."
        }
        Write-Host "Running Playwright E2E in FAIL-CLOSED ISOLATED mode using $EnvFile" -ForegroundColor Cyan
        Get-Content -LiteralPath $EnvFile | ForEach-Object {
            $line = $_.Trim()
            if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
                $name, $value = $line.Split("=", 2)
                $k = $name.Trim()
                $v = $value.Trim()
                $settings[$k] = $v
                [System.Environment]::SetEnvironmentVariable($k, $v)
            }
        }
        if (-not $settings.ContainsKey("FRONTEND_PORT") -or -not $settings["FRONTEND_PORT"]) {
            throw "FRONTEND_PORT must be defined in isolated environment file: $EnvFile"
        }
        if (-not $BaseUrl) {
            $frontendPort = $settings["FRONTEND_PORT"]
            $BaseUrl = "http://localhost:$frontendPort"
        }
    } else {
        $devEnv = Join-Path $repositoryRoot ".env"
        if ($EnvFile -and (Test-Path -LiteralPath $EnvFile)) {
            Get-Content -LiteralPath $EnvFile | ForEach-Object {
                $line = $_.Trim()
                if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
                    $name, $value = $line.Split("=", 2)
                    $settings[$name.Trim()] = $value.Trim()
                }
            }
        } elseif (Test-Path -LiteralPath $devEnv) {
            Get-Content -LiteralPath $devEnv | ForEach-Object {
                $line = $_.Trim()
                if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
                    $name, $value = $line.Split("=", 2)
                    $settings[$name.Trim()] = $value.Trim()
                }
            }
        }
        if (-not $BaseUrl) {
            $BaseUrl = "http://localhost:3010"
        }
    }

    $env:PLAYWRIGHT_BASE_URL = $BaseUrl

    if ($IncludeAuth -or $Isolated) {
        $env:RUN_AUTH_E2E = "1"
        $env:RUN_AUTH_REFRESH_E2E = "1"
        $env:RUN_PROJECT_E2E = "1"
        $env:RUN_TASK_E2E = "1"
        $env:RUN_OPERATIONS_E2E = "1"
        $env:RUN_EMPLOYEE_ADMIN_E2E = "1"
        $env:RUN_WORKFLOW_E2E = "1"
        $env:RUN_NOTIFICATION_REPORT_E2E = "1"
        if ($settings.ContainsKey("COMPOSE_PROJECT_NAME")) {
            $env:COMPOSE_PROJECT_NAME = $settings["COMPOSE_PROJECT_NAME"]
        }
        if ($Isolated -and $EnvFile) {
            $env:COMPOSE_FILE = (Resolve-Path "compose.test.yaml").Path
            $env:COMPOSE_ENV_FILES = (Resolve-Path $EnvFile).Path
        }
        $env:DEV_USER_USERNAME = if ($settings.ContainsKey("DEV_USER_USERNAME")) { $settings["DEV_USER_USERNAME"] } else { "local.user" }
        $env:DEV_USER_PASSWORD = if ($settings.ContainsKey("DEV_USER_PASSWORD")) { $settings["DEV_USER_PASSWORD"] } else { "" }
        $env:KEYCLOAK_ADMIN_USERNAME = if ($settings.ContainsKey("KEYCLOAK_ADMIN_USERNAME")) { $settings["KEYCLOAK_ADMIN_USERNAME"] } else { "local-admin" }
        $env:KEYCLOAK_ADMIN_PASSWORD = if ($settings.ContainsKey("KEYCLOAK_ADMIN_PASSWORD")) { $settings["KEYCLOAK_ADMIN_PASSWORD"] } else { "" }
        $env:PHASE3_E2E_USERNAME = if ($settings.ContainsKey("PHASE3_E2E_USERNAME")) { $settings["PHASE3_E2E_USERNAME"] } else { "disposable.user" }
        $env:PHASE3_E2E_EMAIL = if ($settings.ContainsKey("PHASE3_E2E_EMAIL")) { $settings["PHASE3_E2E_EMAIL"] } else { "disposable.user@example.test" }
        $env:PHASE3_E2E_DISPLAY_NAME = if ($settings.ContainsKey("PHASE3_E2E_DISPLAY_NAME")) { $settings["PHASE3_E2E_DISPLAY_NAME"] } else { "Disposable User" }
        $env:PHASE3_E2E_TEMP_PASSWORD = if ($settings.ContainsKey("PHASE3_E2E_TEMP_PASSWORD")) { $settings["PHASE3_E2E_TEMP_PASSWORD"] } else { "" }
        $env:PHASE3_E2E_PASSWORD = if ($settings.ContainsKey("PHASE3_E2E_PASSWORD")) { $settings["PHASE3_E2E_PASSWORD"] } else { "" }
        $env:PHASE4_E2E_TEMP_PASSWORD = if ($settings.ContainsKey("PHASE4_E2E_TEMP_PASSWORD")) { $settings["PHASE4_E2E_TEMP_PASSWORD"] } else { "" }
        $env:PHASE4_E2E_PASSWORD = if ($settings.ContainsKey("PHASE4_E2E_PASSWORD")) { $settings["PHASE4_E2E_PASSWORD"] } else { "" }
        if ($settings.ContainsKey("JAEGER_UI_PORT")) { $env:JAEGER_UI_PORT = $settings["JAEGER_UI_PORT"] }
        if ($settings.ContainsKey("PROMETHEUS_PORT")) { $env:PROMETHEUS_PORT = $settings["PROMETHEUS_PORT"] }
    }

    if ($Recovery) {
        $env:RUN_DOCKER_RECOVERY = "1"
        $env:RUN_JOB_RECOVERY_E2E = "1"
        $env:RUN_WORKFLOW_RECOVERY_E2E = "1"
        $env:RUN_NOTIFICATION_REPORT_RECOVERY_E2E = "1"
    }

    $reportFile = if ([System.IO.Path]::IsPathRooted($ReportPath)) { $ReportPath } else { Join-Path $repositoryRoot $ReportPath }
    $reportDir = Split-Path -Parent $reportFile
    if (-not (Test-Path -LiteralPath $reportDir)) {
        New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
    }
    $env:PLAYWRIGHT_REPORT_PATH = $reportFile

    $arguments = @("playwright", "test", "--config", "frontend/playwright.config.ts", "--project", $Project, "--workers=1", "--retries=0")
    if ($Spec) {
        $specParts = $Spec -split '\s+' | Where-Object { $_ -ne "" }
        $arguments += $specParts
    }
    if ($Grep) {
        $arguments += "-g"
        $arguments += $Grep
    }

    if ($DryRun) {
        Write-Host "Dry-run E2E validation successful ($Project):" -ForegroundColor Green
        Write-Host "  BASE_URL=$BaseUrl"
        Write-Host "  PLAYWRIGHT_BASE_URL=$env:PLAYWRIGHT_BASE_URL"
        Write-Host "  PLAYWRIGHT_REPORT_PATH=$env:PLAYWRIGHT_REPORT_PATH"
        Write-Host "  ARGS: $($arguments -join ' ')"
        return
    }

    Write-Host "Running Playwright E2E suite ($Project) against $BaseUrl..." -ForegroundColor Cyan
    & npx --prefix frontend @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Playwright test run failed."
    }
}
finally {
    Remove-Item Env:PLAYWRIGHT_BASE_URL -ErrorAction SilentlyContinue
    Remove-Item Env:RUN_AUTH_E2E -ErrorAction SilentlyContinue
    Remove-Item Env:RUN_AUTH_REFRESH_E2E -ErrorAction SilentlyContinue
    Remove-Item Env:RUN_PROJECT_E2E -ErrorAction SilentlyContinue
    Remove-Item Env:RUN_TASK_E2E -ErrorAction SilentlyContinue
    Remove-Item Env:RUN_OPERATIONS_E2E -ErrorAction SilentlyContinue
    Remove-Item Env:RUN_EMPLOYEE_ADMIN_E2E -ErrorAction SilentlyContinue
    Remove-Item Env:RUN_WORKFLOW_E2E -ErrorAction SilentlyContinue
    Remove-Item Env:RUN_NOTIFICATION_REPORT_E2E -ErrorAction SilentlyContinue
    Remove-Item Env:COMPOSE_PROJECT_NAME -ErrorAction SilentlyContinue
    Remove-Item Env:COMPOSE_FILE -ErrorAction SilentlyContinue
    Remove-Item Env:COMPOSE_ENV_FILES -ErrorAction SilentlyContinue
    Remove-Item Env:DEV_USER_USERNAME -ErrorAction SilentlyContinue
    Remove-Item Env:DEV_USER_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:KEYCLOAK_ADMIN_USERNAME -ErrorAction SilentlyContinue
    Remove-Item Env:KEYCLOAK_ADMIN_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:PHASE3_E2E_USERNAME -ErrorAction SilentlyContinue
    Remove-Item Env:PHASE3_E2E_EMAIL -ErrorAction SilentlyContinue
    Remove-Item Env:PHASE3_E2E_DISPLAY_NAME -ErrorAction SilentlyContinue
    Remove-Item Env:PHASE3_E2E_TEMP_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:PHASE3_E2E_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:PHASE4_E2E_TEMP_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:PHASE4_E2E_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:RUN_DOCKER_RECOVERY -ErrorAction SilentlyContinue
    Remove-Item Env:RUN_JOB_RECOVERY_E2E -ErrorAction SilentlyContinue
    Remove-Item Env:RUN_WORKFLOW_RECOVERY_E2E -ErrorAction SilentlyContinue
    Remove-Item Env:RUN_NOTIFICATION_REPORT_RECOVERY_E2E -ErrorAction SilentlyContinue
    Remove-Item Env:JAEGER_UI_PORT -ErrorAction SilentlyContinue
    Remove-Item Env:PROMETHEUS_PORT -ErrorAction SilentlyContinue
    Remove-Item Env:PLAYWRIGHT_REPORT_PATH -ErrorAction SilentlyContinue
    Pop-Location
}
