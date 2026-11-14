#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPOSITORY_ROOT}"
PYTHON="${PYTHON:-python}"
"${PYTHON}" scripts/check_structure.py
"${PYTHON}" scripts/run_structure_tests.py
for check in format:check lint typecheck build; do
  npm --prefix apps/web run "${check}"
done
