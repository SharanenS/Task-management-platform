#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

PYTHON="${PYTHON:-python3}"
if [[ -f "${REPO_ROOT}/.venv/bin/python" ]]; then
    PYTHON="${REPO_ROOT}/.venv/bin/python"
elif [[ -f "${REPO_ROOT}/.venv/Scripts/python.exe" ]]; then
    PYTHON="${REPO_ROOT}/.venv/Scripts/python.exe"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON="python"
fi

echo "=============================================="
echo "Frontend Production Dependency Audit (npm)"
echo "=============================================="

set +e
npm --prefix frontend audit --omit=dev
NPM_EXIT=$?
set -e

if [ "${NPM_EXIT}" -ne 0 ]; then
    if [ "${NPM_EXIT}" -eq 1 ]; then
        echo "ERROR: npm audit found production dependency vulnerabilities." >&2
    else
        echo "ERROR: npm audit tool or network connection failed (exit code ${NPM_EXIT}). Check network connectivity to npm registry." >&2
    fi
    exit "${NPM_EXIT}"
fi

echo ""
echo "=============================================="
echo "Python Service Lockfile Audits (pip-audit)"
echo "=============================================="

LOCKFILES=(
    "gateway/requirements.lock"
    "services/employee/requirements.lock"
    "services/work/requirements.lock"
    "services/work/requirements-test.lock"
    "services/job/requirements.lock"
    "services/workflow/requirements.lock"
    "services/notification/requirements.lock"
)

for lock in "${LOCKFILES[@]}"; do
    echo ""
    echo "--> Auditing ${lock}..."
    set +e
    "${PYTHON}" -m pip_audit -r "${lock}"
    PIP_EXIT=$?
    set -e
    if [ "${PIP_EXIT}" -ne 0 ]; then
        if [ "${PIP_EXIT}" -eq 1 ]; then
            echo "ERROR: pip-audit reported known vulnerabilities in ${lock}." >&2
        else
            echo "ERROR: pip-audit tool or network failure auditing ${lock} (exit code ${PIP_EXIT}). Check PyPI / OSV advisory API connectivity." >&2
        fi
        exit "${PIP_EXIT}"
    fi
done

echo ""
echo "All frontend and backend dependency audits passed cleanly with 0 known vulnerabilities!"
