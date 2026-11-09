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

REPORT_DIR="${REPO_ROOT}/test-results/reports/unit"
mkdir -p "${REPORT_DIR}"

echo "=============================================="
echo "Running Backend Pytest Unit Suites"
echo "=============================================="

"${PYTHON}" -m pytest gateway/tests -v --tb=short --junitxml="${REPORT_DIR}/pytest-gateway.xml"
"${PYTHON}" -m pytest services/employee/tests -v --tb=short --junitxml="${REPORT_DIR}/pytest-employee.xml"
"${PYTHON}" -m pytest services/work/tests --ignore=services/work/tests/test_postgres.py -v --tb=short --junitxml="${REPORT_DIR}/pytest-work.xml"
"${PYTHON}" -m pytest services/job/tests --ignore=services/job/tests/test_postgres.py -v --tb=short --junitxml="${REPORT_DIR}/pytest-job.xml"
"${PYTHON}" -m pytest services/workflow/tests --ignore=services/workflow/tests/test_postgres.py -v --tb=short --junitxml="${REPORT_DIR}/pytest-workflow.xml"
"${PYTHON}" -m pytest services/notification/tests --ignore=services/notification/tests/test_postgres.py -v --tb=short --junitxml="${REPORT_DIR}/pytest-notification.xml"

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
