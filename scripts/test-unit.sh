#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

PYTHON="${PYTHON:-python}"
if [[ -f "${REPO_ROOT}/.venv/bin/python" ]]; then
    PYTHON="${REPO_ROOT}/.venv/bin/python"
elif [[ -f "${REPO_ROOT}/.venv/Scripts/python.exe" ]]; then
    PYTHON="${REPO_ROOT}/.venv/Scripts/python.exe"
fi

get_service_python() {
    local svc="$1"
    local svc_name
    svc_name="$(basename "${svc}")"
    if [[ -f "${REPO_ROOT}/${svc}/.venv/bin/python" ]]; then
        echo "${REPO_ROOT}/${svc}/.venv/bin/python"
    elif [[ -f "${REPO_ROOT}/.venv/${svc_name}/bin/python" ]]; then
        echo "${REPO_ROOT}/.venv/${svc_name}/bin/python"
    elif [[ -f "${REPO_ROOT}/${svc}/.venv/Scripts/python.exe" ]]; then
        echo "${REPO_ROOT}/${svc}/.venv/Scripts/python.exe"
    elif [[ -f "${REPO_ROOT}/.venv/${svc_name}/Scripts/python.exe" ]]; then
        echo "${REPO_ROOT}/.venv/${svc_name}/Scripts/python.exe"
    else
        echo "${PYTHON}"
    fi
}

REPORT_DIR="${REPO_ROOT}/test-results/reports/unit"
mkdir -p "${REPORT_DIR}"

echo "=============================================="
echo "Running Backend Pytest Unit Suites"
echo "=============================================="

run_service_pytest() {
    local svc="$1"
    local report_file="$2"
    shift 2
    local extra_args=("$@")
    local svc_python
    svc_python="$(get_service_python "${svc}")"
    (
        cd "${REPO_ROOT}/${svc}"
        "${svc_python}" -m pytest tests -v --tb=short --junitxml="${REPORT_DIR}/${report_file}" "${extra_args[@]}"
    )
}

run_service_pytest "gateway" "pytest-gateway.xml"
run_service_pytest "services/employee" "pytest-employee.xml"
run_service_pytest "services/work" "pytest-work.xml" --ignore=tests/test_postgres.py
run_service_pytest "services/job" "pytest-job.xml" --ignore=tests/test_postgres.py
run_service_pytest "services/workflow" "pytest-workflow.xml" --ignore=tests/test_postgres.py
run_service_pytest "services/notification" "pytest-notification.xml" --ignore=tests/test_postgres.py

echo ""
echo "=============================================="
echo "Running Frontend Vitest Component Suites"
echo "=============================================="

npm --prefix frontend test -- --reporter=default --reporter=junit --outputFile="../test-results/reports/unit/vitest.xml"

echo ""
echo "=============================================="
echo "Verifying Machine-Readable Test Reports"
echo "=============================================="

"${PYTHON}" scripts/verify_test_reports.py --unit-dir test-results/reports/unit

echo ""
echo "All Backend and Frontend Unit Suites Passed and Verified Successfully!"
