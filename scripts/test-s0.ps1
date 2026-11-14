$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repositoryRoot
try {
    $python = if (Test-Path ".venv/Scripts/python.exe") {
        (Resolve-Path ".venv/Scripts/python.exe").Path
    } else { "python" }
    & $python scripts/check_structure.py
    if ($LASTEXITCODE) { throw "Source boundary verification failed." }
    & $python scripts/run_structure_tests.py
    if ($LASTEXITCODE) { throw "Structure regression tests failed." }
    foreach ($check in @("format:check", "lint", "typecheck", "build")) {
        npm --prefix apps/web run $check
        if ($LASTEXITCODE) { throw "Application check failed: $check" }
    }
} finally {
    Pop-Location
}
