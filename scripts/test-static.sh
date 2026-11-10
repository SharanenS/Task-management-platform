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

RUFF_PYTHON="${PYTHON}"
if ! "${RUFF_PYTHON}" -m ruff --version >/dev/null 2>&1; then
    if [[ -f "${REPO_ROOT}/gateway/.venv/bin/python" ]]; then
        RUFF_PYTHON="${REPO_ROOT}/gateway/.venv/bin/python"
    fi
fi

echo "=== 1/6 Python Linting (Ruff) ==="
"${RUFF_PYTHON}" -m ruff check gateway services

echo "=== 2/6 Python Formatting (Ruff) ==="
"${RUFF_PYTHON}" -m ruff format --check gateway services

echo "=== 3/6 Python Type Checking (MyPy) ==="
SERVICES=("gateway" "services/employee" "services/work" "services/job" "services/workflow" "services/notification")
for svc in "${SERVICES[@]}"; do
    echo "  -> MyPy ${svc}"
    svc_python="$(get_service_python "${svc}")"
    (
        cd "${REPO_ROOT}/${svc}"
        "${svc_python}" -m mypy --config-file pyproject.toml app
    )
done

echo "=== 4/6 Frontend Formatting (Prettier) ==="
npm --prefix frontend run format:check

echo "=== 5/6 Frontend Linting (ESLint) ==="
npm --prefix frontend run lint

echo "=== 6/6 Frontend Type Checking (TypeScript) ==="
npm --prefix frontend run typecheck

echo "All static checks passed successfully!"
