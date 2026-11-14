#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/load-env.sh
source "${SCRIPT_DIR}/load-env.sh"

PROJECT_NAME="${1:-}"
COMPOSE_FILE="${2:-compose.test.yaml}"
ENV_FILE="${3:-}"
DRY_RUN="${4:-0}"

if [ -z "${PROJECT_NAME}" ]; then
    echo "ERROR: Compose project name is mandatory for test stack bootstrap." >&2
    exit 1
fi

case "${PROJECT_NAME}" in
    "enterprise-task-platform-phase2"|"project2.0"|"taskspace"|"default")
        echo "ERROR: Protected development project '${PROJECT_NAME}' cannot be targeted for test bootstrap!" >&2
        exit 1
        ;;
esac

if [ -z "${COMPOSE_FILE}" ] || [ ! -f "${COMPOSE_FILE}" ]; then
    echo "ERROR: Compose file does not exist: '${COMPOSE_FILE}'" >&2
    exit 1
fi

if [ -z "${ENV_FILE}" ] || [ ! -f "${ENV_FILE}" ]; then
    echo "ERROR: Isolated environment file is mandatory and must exist: '${ENV_FILE}'" >&2
    exit 1
fi

# Clean slate: unset sensitive and isolated config to reject inherited credentials
unset FRONTEND_PORT KEYCLOAK_ADMIN_USERNAME KEYCLOAK_ADMIN_PASSWORD KEYCLOAK_ADMIN_CLIENT_SECRET DEV_USER_USERNAME DEV_USER_PASSWORD DEV_USER_EMAIL DEV_USER_DISPLAY_NAME DEV_USER_ROLE COMPOSE_PROJECT_NAME

load_env_file "${ENV_FILE}"

if [ -n "${COMPOSE_PROJECT_NAME:-}" ] && [ "${COMPOSE_PROJECT_NAME}" != "${PROJECT_NAME}" ]; then
    echo "ERROR: Project name mismatch: argument '${PROJECT_NAME}' does not match COMPOSE_PROJECT_NAME '${COMPOSE_PROJECT_NAME}' in '${ENV_FILE}'." >&2
    exit 1
fi

for req_var in FRONTEND_PORT KEYCLOAK_ADMIN_USERNAME KEYCLOAK_ADMIN_PASSWORD KEYCLOAK_ADMIN_CLIENT_SECRET DEV_USER_USERNAME DEV_USER_PASSWORD DEV_USER_EMAIL DEV_USER_DISPLAY_NAME DEV_USER_ROLE; do
    if [ -z "${!req_var:-}" ]; then
        echo "ERROR: Required isolated configuration '${req_var}' is missing from '${ENV_FILE}'." >&2
        exit 1
    fi
done

FRONTEND_PORT="${FRONTEND_PORT}"
KEYCLOAK_ADMIN_USER="${KEYCLOAK_ADMIN_USERNAME}"
KEYCLOAK_ADMIN_PASS="${KEYCLOAK_ADMIN_PASSWORD}"
KEYCLOAK_SECRET="${KEYCLOAK_ADMIN_CLIENT_SECRET}"
DEV_USER="${DEV_USER_USERNAME}"
DEV_PASS="${DEV_USER_PASSWORD}"
DEV_EMAIL="${DEV_USER_EMAIL}"
DEV_NAME="${DEV_USER_DISPLAY_NAME}"
DEV_ROLE="${DEV_USER_ROLE}"

if [ "${DRY_RUN}" = "1" ] || [ "${DRY_RUN}" = "--dry-run" ]; then
    echo "Dry-run bootstrap validation successful for project '${PROJECT_NAME}':"
    echo "  COMPOSE_FILE=${COMPOSE_FILE}"
    echo "  ENV_FILE=${ENV_FILE}"
    echo "  FRONTEND_PORT=${FRONTEND_PORT}"
    exit 0
fi

echo "Bootstrapping isolated Keycloak & Employee profile for project '${PROJECT_NAME}'..."

# Configure Keycloak admin CLI
docker compose -p "${PROJECT_NAME}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T keycloak \
    /opt/keycloak/bin/kcadm.sh config credentials \
    --server http://localhost:8080 --realm master \
    --user "${KEYCLOAK_ADMIN_USER}" --password "${KEYCLOAK_ADMIN_PASS}" >/dev/null

# Update taskspace-web OIDC client
CLIENT_ID=$(docker compose -p "${PROJECT_NAME}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T keycloak \
    /opt/keycloak/bin/kcadm.sh get clients -r taskspace -q clientId=taskspace-web | grep '"id"' | head -n1 | awk -F'"' '{print $4}')

docker compose -p "${PROJECT_NAME}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T keycloak \
    /opt/keycloak/bin/kcadm.sh update "clients/${CLIENT_ID}" -r taskspace \
    -s "rootUrl=http://localhost:${FRONTEND_PORT}" \
    -s "baseUrl=http://localhost:${FRONTEND_PORT}/" \
    -s "redirectUris=[\"http://localhost:${FRONTEND_PORT}/auth/callback\"]" \
    -s "webOrigins=[\"http://localhost:${FRONTEND_PORT}\"]" \
    -s "attributes={\"pkce.code.challenge.method\":\"S256\",\"post.logout.redirect.uris\":\"http://localhost:${FRONTEND_PORT}/signed-out\"}" >/dev/null

# Ensure taskspace-employee-admin service client
ADMIN_CLIENT_ID=$(docker compose -p "${PROJECT_NAME}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T keycloak \
    /opt/keycloak/bin/kcadm.sh get clients -r taskspace -q clientId=taskspace-employee-admin | grep '"id"' | head -n1 | awk -F'"' '{print $4}' || true)

if [ -z "${ADMIN_CLIENT_ID}" ]; then
    docker compose -p "${PROJECT_NAME}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T keycloak \
        /opt/keycloak/bin/kcadm.sh create clients -r taskspace \
        -s clientId=taskspace-employee-admin -s enabled=true \
        -s publicClient=false -s standardFlowEnabled=false \
        -s directAccessGrantsEnabled=false -s serviceAccountsEnabled=true \
        -s secret="${KEYCLOAK_SECRET}" >/dev/null

    ADMIN_CLIENT_ID=$(docker compose -p "${PROJECT_NAME}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T keycloak \
        /opt/keycloak/bin/kcadm.sh get clients -r taskspace -q clientId=taskspace-employee-admin | grep '"id"' | head -n1 | awk -F'"' '{print $4}')
fi

docker compose -p "${PROJECT_NAME}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T keycloak \
    /opt/keycloak/bin/kcadm.sh update "clients/${ADMIN_CLIENT_ID}" -r taskspace \
    -s "enabled=true" -s "publicClient=false" \
    -s "standardFlowEnabled=false" -s "directAccessGrantsEnabled=false" \
    -s "serviceAccountsEnabled=true" \
    -s "secret=${KEYCLOAK_SECRET}" >/dev/null

# Assign service account roles
SA_ID=$(docker compose -p "${PROJECT_NAME}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T keycloak \
    /opt/keycloak/bin/kcadm.sh get "clients/${ADMIN_CLIENT_ID}/service-account-user" -r taskspace | grep '"id"' | head -n1 | awk -F'"' '{print $4}')

for role in manage-users view-users query-users; do
    docker compose -p "${PROJECT_NAME}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T keycloak \
        /opt/keycloak/bin/kcadm.sh add-roles -r taskspace --uid "${SA_ID}" \
        --cclientid realm-management --rolename "${role}" >/dev/null 2>&1 || true
done

# Provision test user
USER_ID=$(docker compose -p "${PROJECT_NAME}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T keycloak \
    /opt/keycloak/bin/kcadm.sh get users -r taskspace -q username="${DEV_USER}" | grep '"id"' | head -n1 | awk -F'"' '{print $4}' || true)

if [ -z "${USER_ID}" ]; then
    docker compose -p "${PROJECT_NAME}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T keycloak \
        /opt/keycloak/bin/kcadm.sh create users -r taskspace \
        -s "username=${DEV_USER}" -s "email=${DEV_EMAIL}" \
        -s "firstName=Local" -s "lastName=User" \
        -s "enabled=true" -s "emailVerified=true" >/dev/null

    USER_ID=$(docker compose -p "${PROJECT_NAME}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T keycloak \
        /opt/keycloak/bin/kcadm.sh get users -r taskspace -q username="${DEV_USER}" | grep '"id"' | head -n1 | awk -F'"' '{print $4}')
fi

docker compose -p "${PROJECT_NAME}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T keycloak \
    /opt/keycloak/bin/kcadm.sh update "users/${USER_ID}" -r taskspace \
    -s "enabled=true" -s "emailVerified=true" -s 'requiredActions=[]' >/dev/null

docker compose -p "${PROJECT_NAME}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T keycloak \
    /opt/keycloak/bin/kcadm.sh set-password -r taskspace --userid "${USER_ID}" \
    --new-password "${DEV_PASS}" >/dev/null

# Bootstrap employee profile
docker compose -p "${PROJECT_NAME}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T employee python -m app.bootstrap \
    --subject "${USER_ID}" --username "${DEV_USER}" \
    --email "${DEV_EMAIL}" --display-name "${DEV_NAME}" --role "${DEV_ROLE}" >/dev/null

echo "Isolated test stack bootstrap completed successfully."
