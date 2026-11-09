#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

PYTHON="${PYTHON:-python}"
if [[ -f "${REPO_ROOT}/.venv/bin/python" ]]; then
    PYTHON="${REPO_ROOT}/.venv/bin/python"
fi

echo "=== 1/6 Python Linting (Ruff) ==="
"${PYTHON}" -m ruff check gateway services

echo "=== 2/6 Python Formatting (Ruff) ==="
"${PYTHON}" -m ruff format --check gateway services

echo "=== 3/6 Python Type Checking (MyPy) ==="
SERVICES=("gateway" "services/employee" "services/work" "services/job" "services/workflow" "services/notification")
for svc in "${SERVICES[@]}"; do
    echo "  -> MyPy ${svc}"
    "${PYTHON}" -m mypy --config-file "${svc}/pyproject.toml" "${svc}/app"
done

echo "=== 4/6 Frontend Formatting (Prettier) ==="
npm --prefix frontend run format:check

echo "=== 5/6 Frontend Linting (ESLint) ==="
npm --prefix frontend run lint

echo "=== 6/6 Frontend Type Checking (TypeScript) ==="
npm --prefix frontend run typecheck

echo "All static checks passed successfully!"
