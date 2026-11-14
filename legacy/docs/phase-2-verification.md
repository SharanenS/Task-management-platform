# Phase 2 verification

Date: 2026-10-14
Status: **Accepted**

## Acceptance result

Phase 2 authentication and the real application shell passed automated, Docker-backed,
end-to-end, and manual acceptance. Phase 3 has not started.

The completed manual acceptance covered:

- Active administrator login and the Employee Service-backed profile.
- Protected routes, session refresh, logout, and Keycloak logout.
- Browser storage inspection: no tokens were present in local or session storage.
- Desktop, 768 px, and 390 px layouts, keyboard navigation, and the mobile drawer.
- Inactive and missing employee denial without automatic registration.
- Session-expired and authentication-service-unavailable presentation and recovery.
- Preservation of the primary administrator and restoration of all seven healthy services.

## Final automated verification

| Command or check | Exact result |
| --- | --- |
| `..\.venv\Scripts\python.exe -m pytest` from `gateway` | Passed: 16 tests |
| `..\.venv\Scripts\python.exe -m ruff check .` from `gateway` | Passed |
| `..\.venv\Scripts\python.exe -m ruff format --check .` from `gateway` | Passed: 9 files formatted |
| `..\.venv\Scripts\python.exe -m mypy app` from `gateway` | Passed: 6 source files |
| `.\.venv\Scripts\python.exe -m pytest services/employee/tests` | Passed: 8 tests |
| `.\.venv\Scripts\python.exe -m ruff check services/employee` | Passed |
| `.\.venv\Scripts\python.exe -m ruff format --check services/employee` | Passed: 13 files formatted |
| `.\.venv\Scripts\python.exe -m mypy services/employee/app` | Passed: 8 source files |
| `npm test` | Passed: 22 tests in 5 files |
| `npm run lint` | Passed |
| `npm run typecheck` | Passed |
| `npm run format:check` | Passed |
| `..\.venv\Scripts\python.exe export_schema.py` from `gateway` | Passed |
| `npm run codegen` | Passed |
| `npm run build` | Passed: 14 routes generated |
| `docker compose config --quiet` | Passed |
| `docker compose build` | Passed: frontend, gateway, and employee images |
| `npm audit --omit=dev` | Passed: zero vulnerabilities |
| `npm audit` | Reported 12 high-severity development dependency findings through `braces`; no non-breaking fix is offered |
| `.\.venv\Scripts\python.exe -m pip_audit -r gateway\requirements.lock` | Passed: no known vulnerabilities |
| `.\.venv\Scripts\python.exe -m pip_audit -r services\employee\requirements.lock` | Passed: no known vulnerabilities |

The first restricted Windows runs of Vitest and the local Next.js build could not
spawn their worker processes (`EPERM`). Their unrestricted reruns passed. The
production build did not emit an unrelated workspace-lockfile warning.

## Docker-backed and end-to-end results

Fourteen final browser scenario results passed:

- Unauthenticated protected-route redirect.
- Active administrator login, Employee Service identity, GraphQL, browser-storage
  inspection, and logout.
- Real refresh after the 60-second access-token expiry.
- Refresh failure, session-expired presentation, and Keycloak recovery.
- Login-time Keycloak outage, sanitized unavailable presentation, and recovery.
- Disposable inactive employee denial followed by profile restoration.
- Disposable missing employee denial followed by profile restoration.
- Real gateway outage and recovery.
- Three desktop Phase 1 regressions covering GraphQL, responsive navigation,
  simulated connection failure/recovery, and component states.
- Three mobile Phase 1 regressions covering the same application areas and the drawer.

The gateway outage test initially lacked authentication after its route became
protected. It now performs a real login, and its assertion budget accounts for the
application's bounded eight-second upstream timeout. The final isolated rerun passed.

## Development-access boundary review

- `app.development_access` is a command-line module and is not imported by the
  Employee Service HTTP application or GraphQL gateway.
- It uses the Employee Service SQLAlchemy session and model, so changes go through
  Employee Service-owned code and storage.
- It permits only `development` and `test` environments. Unit and live-container
  negative checks confirmed that it refuses production mode.
- Every state-changing command requires the protected primary Keycloak subject and
  refuses to act when the target matches it. Unit and live-container negative checks
  passed. Acceptance commands supplied the primary subject and targeted disposable identities.
- The inactive profile was restored to active, and the missing profile was recreated
  through the Employee Service bootstrap. The primary administrator remained active.

## Authentication-unavailable boundary review

- Discovery uses a three-second `AbortSignal` timeout; the OIDC client uses an
  eight-second timeout.
- The browser receives only `error=unavailable` and the fixed, user-facing message.
  Error details are not rendered.
- Only discovery HTTP failures, fetch `TypeError`, and timeout `DOMException` are
  converted to the unavailable state. An automated test confirms that an unrelated
  application error propagates instead of being hidden.

All seven Compose services were healthy after restoration and final verification.
