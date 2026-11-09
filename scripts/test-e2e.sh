#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

PROJECT="desktop"
SPEC=""
BASE_URL=""
ENV_FILE=""
ISOLATED=0
INCLUDE_AUTH=0
RECOVERY=0
REPORT_PATH="test-results/reports/playwright/report.json"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --project)
            PROJECT="$2"
            shift 2
            ;;
        --project=*)
            PROJECT="${1#*=}"
            shift
            ;;
        --spec)
            SPEC="$2"
            shift 2
            ;;
        --spec=*)
            SPEC="${1#*=}"
            shift
            ;;
        --base-url)
            BASE_URL="$2"
            shift 2
            ;;
        --base-url=*)
            BASE_URL="${1#*=}"
            shift
            ;;
        --env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        --env-file=*)
            ENV_FILE="${1#*=}"
            shift
            ;;
        --isolated)
            ISOLATED=1
            shift
            ;;
        --include-auth)
            INCLUDE_AUTH=1
            shift
            ;;
        --recovery)
            RECOVERY=1
            shift
            ;;
        --report-path)
            REPORT_PATH="$2"
            shift 2
            ;;
        --report-path=*)
            REPORT_PATH="${1#*=}"
            shift
            ;;
        --grep)
            GREP="$2"
            shift 2
            ;;
        --grep=*)
            GREP="${1#*=}"
            shift
            ;;
        *)
            if [ -z "${SPEC}" ] && [[ "$1" == *.spec.ts* ]]; then
                SPEC="$1"
            elif [ -z "${PROJECT}" ]; then
                PROJECT="$1"
            fi
            shift
            ;;
    esac
done

if [ "${ISOLATED}" -eq 1 ]; then
    if [ -z "${ENV_FILE}" ] || [ ! -f "${ENV_FILE}" ]; then
        echo "ERROR: Fail-closed isolated mode requires an existing test environment file via --env-file." >&2
        echo "Refusing to fall back to development .env or development endpoints." >&2
        exit 1
    fi
    echo "Running Playwright E2E in FAIL-CLOSED ISOLATED mode using ${ENV_FILE}"
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a
    if [ -z "${BASE_URL}" ]; then
        BASE_URL="http://localhost:${FRONTEND_PORT:-3110}"
    fi
    INCLUDE_AUTH=1
else
    if [ -n "${ENV_FILE}" ] && [ -f "${ENV_FILE}" ]; then
        set -a
        # shellcheck disable=SC1090
        source "${ENV_FILE}"
        set +a
    elif [ -f ".env" ]; then
        set -a
        # shellcheck disable=SC1090
        source ".env"
        set +a
    fi
    if [ -z "${BASE_URL}" ]; then
        BASE_URL="http://localhost:3010"
    fi
fi

if [[ "${REPORT_PATH}" = /* ]]; then
    ABS_REPORT_PATH="${REPORT_PATH}"
else
    ABS_REPORT_PATH="${REPO_ROOT}/${REPORT_PATH}"
fi

export PLAYWRIGHT_BASE_URL="${BASE_URL}"
export PLAYWRIGHT_REPORT_PATH="${ABS_REPORT_PATH}"

mkdir -p "$(dirname "${ABS_REPORT_PATH}")"

if [ "${INCLUDE_AUTH}" -eq 1 ]; then
    export RUN_AUTH_E2E="1"
    export RUN_AUTH_REFRESH_E2E="1"
    export RUN_PROJECT_E2E="1"
    export RUN_TASK_E2E="1"
    export RUN_OPERATIONS_E2E="1"
    export RUN_EMPLOYEE_ADMIN_E2E="1"
    export RUN_WORKFLOW_E2E="1"
    export RUN_NOTIFICATION_REPORT_E2E="1"
fi

if [ "${RECOVERY}" -eq 1 ]; then
    export RUN_DOCKER_RECOVERY="1"
    export RUN_JOB_RECOVERY_E2E="1"
    export RUN_WORKFLOW_RECOVERY_E2E="1"
    export RUN_NOTIFICATION_REPORT_RECOVERY_E2E="1"
fi

if [ "${ISOLATED}" -eq 1 ]; then
    export COMPOSE_FILE="$(cd "${REPO_ROOT}" && pwd)/compose.test.yaml"
    if [ -n "${ENV_FILE}" ]; then
        export COMPOSE_ENV_FILES="$(cd "$(dirname "${ENV_FILE}")" && pwd)/$(basename "${ENV_FILE}")"
    fi
fi

ARGS=("playwright" "test" "--config" "frontend/playwright.config.ts" "--project=${PROJECT}" "--workers=1" "--retries=0")
if [ -n "${SPEC}" ]; then
    read -r -a SPEC_PARTS <<< "${SPEC}"
    ARGS+=("${SPEC_PARTS[@]}")
fi
if [ -n "${GREP}" ]; then
    ARGS+=("-g" "${GREP}")
fi

echo "Running Playwright E2E suite (${PROJECT}) against ${BASE_URL}..."
npx --prefix frontend "${ARGS[@]}"
