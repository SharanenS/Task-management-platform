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

echo "Running Non-Mutating Schema & Codegen Verification..."
"${PYTHON}" scripts/verify_codegen.py
