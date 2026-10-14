# Phase 3 verification

Date: 2026-10-14
Status: **Accepted**
Acceptance date: 2026-10-14

## Coverage matrix

| Requirement                                                               | Automated evidence                                                                                                                          | Layer                       | Remaining owner review                                                                            |
| ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------- | ------------------------------------------------------------------------------------------------- |
| Directory loading, success, empty, error, retry                           | Component tests exercise all states; Docker journey loads the real directory                                                                | Frontend, browser           | None                                                                                              |
| Search, role/status filters, combined filters                             | Request variables and normalized service queries are asserted                                                                               | Component, service          | None                                                                                              |
| Cursor pagination, stable ordering, bounded sizes, malformed cursor       | Forward cursor navigation, UUID ordering, 1–50 bounds, and invalid cursor tests                                                             | Component, service, gateway | Backward cursors are not supported by the API                                                     |
| Employee detail, missing and failure states                               | Service detail/missing tests; component loading, success, failure/retry; real detail navigation                                             | Service, component, browser | None                                                                                              |
| Provisioning validation and normalization                                 | Browser constraints plus service validation for username, email, name, password, and retry key                                              | Component, service          | None                                                                                              |
| Successful provisioning and temporary password                            | Service and real Keycloak first-login journey                                                                                               | Service, browser            | None                                                                                              |
| Duplicate submission, username/email collision, idempotent retry/conflict | Pending-button component test and service collision/idempotency tests                                                                       | Component, service          | Near-concurrent PostgreSQL race remains covered by database constraints rather than a stress test |
| ADMIN authorization; MEMBER/MANAGER/unauthenticated denial                | Every gateway operation rejects unauthenticated callers; direct MEMBER and MANAGER GraphQL tests; Employee Service actor checks             | Gateway, service, browser   | Real MANAGER browser journey is not separately automated                                          |
| Current-profile reload and stale-role prevention                          | Gateway reloads `get_employee` for each operation and tests direct denial from the returned current role                                    | Gateway                     | Session-policy timing remains inherited from Phase 2 refresh coverage                             |
| Role/status changes and repeated requests                                 | Service role, activation, deactivation, repetition, self and final-admin protections                                                        | Service, gateway            | Real role-transition journey remains owner-review evidence                                        |
| Existing-session denial, reactivation, storage safety                     | Real lifecycle verifies denial, recovery, and empty local/session storage                                                                   | Browser                     | None                                                                                              |
| Keycloak failures and reconciliation                                      | Service tests cover create/enable failure, fail-closed state, repeated reconciliation; Phase 2 Keycloak outage tests cover restart recovery | Adapter, service, browser   | Full real provisioning-during-outage reconciliation is not automated                              |
| Employee Service outage and recovery                                      | Exact service stop, sanitized GraphQL failure, restart, and real-query recovery                                                             | Browser                     | None                                                                                              |
| Secret/internal-error non-disclosure                                      | Adapter, service, gateway, component, and outage assertions use sanitized public results                                                    | All automated layers        | None                                                                                              |
| Responsive behavior and horizontal overflow                               | Existing desktop/mobile regressions plus Phase 3 desktop overflow assertion; tablet project is configured                                   | Browser                     | Subjective visual quality deferred                                                                |
| Keyboard, focus, mobile navigation                                        | Existing foundation browser tests and semantic component controls                                                                           | Component, browser          | Final accessibility certification is outside Phase 3                                              |
| Primary-admin preservation and disposable cleanup                         | Protected-subject CLI tests and exact post-journey cleanup                                                                                  | Service, live cleanup       | Review retained ambiguous records below                                                           |

## Automated results

| Command or check                               | Exact result                                                                                 |
| ---------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `python -m pytest -q` from `services/employee` | Passed: 30 tests                                                                             |
| `python -m pytest -q` from `gateway`           | Passed: 34 tests                                                                             |
| Ruff lint                                      | Passed for both Python services                                                              |
| Ruff formatting                                | Passed: gateway 9 files; Employee Service 18 files                                           |
| MyPy                                           | Passed: gateway 6 files; Employee Service 10 files                                           |
| `npm test`                                     | Passed: 28 tests in 6 files                                                                  |
| `npm run typecheck` and `npm run lint`         | Passed                                                                                       |
| `npm run codegen` and gateway schema export    | Passed                                                                                       |
| `npm run build`                                | Passed: 16 routes                                                                            |
| `docker compose config --quiet`                | Passed                                                                                       |
| `docker compose build`                         | Passed: frontend, gateway, and employee images                                               |
| PostgreSQL migration                           | `20261014_02 (head)`                                                                         |
| `npm audit --omit=dev`                         | Passed: zero vulnerabilities                                                                 |
| `npm audit`                                    | 12 known high-severity development findings through `braces`; forced breaking downgrade only |
| Python audits                                  | Passed: no known vulnerabilities in either lock file                                         |
| Real Phase 3 lifecycle                         | Passed: 1 test in 8.5 seconds                                                                |
| Employee Service outage/recovery               | Passed: 1 test in 8.7 seconds after correcting the readiness assertion                       |

## Final clean acceptance run

The final run began on `phase-3-employee-administration` with an empty staging
area. `.env` and `AGENTS.md` remained locally ignored. Compose configuration
validation passed, the existing stack was started without deleting volumes, all
seven services reached healthy state, the idempotent development bootstrap passed,
and the primary administrator was confirmed enabled, active, ADMIN, and linked by
its stable Keycloak subject.

| Final command group                                        | Result                                                                                                                                |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Employee Service pytest, Ruff lint/format, and MyPy        | 30 passed; Ruff passed with 18 files formatted correctly; MyPy passed for 10 source files                                             |
| Gateway pytest, Ruff lint/format, MyPy, and schema export  | 34 passed; Ruff passed with 9 files formatted correctly; MyPy passed for 6 source files; schema export passed                         |
| Frontend GraphQL generation and Vitest                     | Generation passed; 30 tests passed in 6 files                                                                                         |
| ESLint, TypeScript, Prettier, and Next.js production build | All passed; production build emitted 16 routes                                                                                        |
| Complete desktop foundation/authentication collection      | 5 passed, 4 skipped, 0 failed                                                                                                         |
| Complete 768 px foundation/authentication collection       | 5 passed, 4 skipped, 0 failed                                                                                                         |
| Complete 390 px foundation/authentication collection       | 5 passed, 4 skipped, 0 failed                                                                                                         |
| Combined three-viewport collection                         | 15 passed, 12 skipped, 0 failed in 39.2 seconds                                                                                       |
| Expiry and Keycloak recovery collection                    | 3 passed, 0 skipped, 0 failed in 3.0 minutes                                                                                          |
| Phase 1 gateway outage/recovery regression                 | 1 passed, 0 skipped, 0 failed in 12.1 seconds                                                                                         |
| Phase 3 lifecycle and Employee Service outage/recovery     | 2 passed, 0 skipped, 0 failed in 32.5 seconds                                                                                         |
| Callback diagnostic security regression                    | Focused route suite: 4 passed; sensitive values in error name, code, message, cause, and nested cause were absent from console output |
| Final desktop authentication collection                    | 2 passed, 4 intentional opt-in skips, 0 failed in 2.7 seconds                                                                         |

The combined collection's twelve skips are intentional opt-in boundaries, repeated
once per viewport:

- Expired-token refresh requires `RUN_AUTH_REFRESH_E2E=1` because it waits for the
  real token expiry. It passed separately on desktop.
- Inactive or missing Employee Service profile denial requires
  `RUN_ACCESS_DENIED_E2E=1` and a disposable identity prepared in that exact state.
  The state-specific service and gateway paths are automated; this browser variant
  was not enabled in the final run.
- Refresh failure during a Keycloak outage requires `RUN_AUTH_FAILURE_E2E=1`
  because it stops Keycloak. It passed separately and serially on desktop.
- Login during a Keycloak outage requires `RUN_LOGIN_OUTAGE_E2E=1` because it stops
  Keycloak. It passed separately and serially on desktop.

Before the final zero-failure collection, the complete collection reproduced an
intermittent callback failure while all seven Compose health checks were already
passing. Sanitized callback classification identified an invalid OIDC response,
without logging response data, credentials, tokens, or internal addresses. The
frontend image was rebuilt, the same seven-service health gate passed, and the
entire 27-case collection was rerun. Its final result was 15 passed, 12 intentional
skips, and zero failures. No arbitrary sleeps or automatic test retries were added.
Sanitized error classification remains in the callback so any recurrence can be
distinguished without exposing sensitive data.

The callback diagnostic now emits only the fixed message `OIDC callback failed.`
and one application-owned literal category: `AUTHORIZATION_RESPONSE_INVALID`,
`ID_TOKEN_INVALID`, `TOKEN_RESPONSE_INVALID`, `UPSTREAM_RESPONSE_INVALID`,
`UPSTREAM_TIMEOUT`, or `UNKNOWN`. Regression tests inject distinct sensitive sample
values into an error's name, code, message, cause, and nested cause. The focused
route suite passed 4 tests and confirmed that none of those values, the error object,
or a stack trace reached console output. The sanitized callback redirect and the
separate inactive-profile redirect remain unchanged; state, nonce, PKCE, issuer, and
token validation still belong to the OIDC library call.

The lifecycle test-owned Keycloak identity and linked Employee Service profile were
removed by exact subject after the run. The protected primary subject was explicitly
excluded from cleanup. Earlier ambiguous null-linked idempotency records remain
untouched because their ownership cannot be proven safely. Final checks confirmed
all seven containers healthy and the primary administrator enabled, active, ADMIN,
and linked.

The browser journey provisioned a disposable employee, verified the first-login
temporary-password action, MEMBER authorization, deactivation denial, reactivation,
and final deactivation. Its Keycloak identity and Employee Service profile were
removed afterward; the primary administrator was preserved.

The first browser attempt exposed a test race: it captured the provision page URL
before the employee-detail navigation completed. The test now waits for the detail
URL and its clean rerun passed. Earlier interrupted attempts left null-linked
idempotency records. A proposed broad cleanup was intentionally not performed
because those records were not individually proven disposable; they are inert and
contain no credential data.

A combined Phase 1/2 outage regression exposed an unsupported Keycloak realm-import
field. The field was removed because service-account role assignment already belongs
to the idempotent bootstrap. Keycloak then imported the realm successfully, the
bootstrap passed, and the reruns passed: two Keycloak outage scenarios, gateway
outage recovery, three desktop foundation scenarios, and three mobile scenarios.

## Security review

- Administrative operations have no public REST exposure; GraphQL is the public
  business boundary.
- The gateway and Employee Service both require a current active ADMIN profile.
- The service-account secret exists only in ignored `.env`; `.env.example` contains
  a placeholder.
- Initial passwords are neither persisted by Employee Service nor returned in
  operation payloads.
- Keycloak calls use bounded timeouts, sanitized errors, and no unbounded retries.
- The development access CLI is restricted to development/test and refuses the
  protected primary subject.

## Automated functional acceptance

The owner accepted Phase 3 functional scope on 2026-10-14. Automated functional,
authorization, security, lifecycle, outage, recovery, responsive-overflow, and
basic accessibility checks passed.

Objective route, API, authorization, validation, persistence, state, recovery,
storage, and basic responsive behavior is covered at the layers shown above. The
real lifecycle uses an exact disposable identity. It finished inactive and was then
removed through Employee Service-owned development code and Keycloak's supported
administration command. The primary administrator was not used as a mutation target.

The first Employee Service outage run proved the sanitized unavailable state but
checked gateway health too early for recovery. The test now polls the real employee
directory query; its rerun passed. Playwright tracing is disabled so credential-entry
failures cannot retain populated password fields.

The 768 px regression exposed a viewport assumption in the test helper, which now
opens navigation according to the rendered trigger. The mobile authentication test
then exposed a missing accessible name on the compact user-menu button. An explicit
name was added and the rebuilt-container rerun passed. One callback attempt directly
after recreation returned the existing sanitized callback error; the immediate clean
rerun passed and all services were healthy.

Null-linked idempotency rows from earlier interrupted development runs remain. They
are inert and contain no credentials. They were not deleted because individual
ownership could not be proven safely.

The accepted limitations are forward-only pagination, no concurrent PostgreSQL
stress test, no separate real MANAGER browser journey, and no full real
provisioning-during-Keycloak-outage journey. The retained ambiguous null-linked
idempotency records are also documented above. These limitations do not block
Phase 3 functional acceptance.

## Deferred visual and UX review

Subjective color, typography, spacing, icon, animation, and layout refinement is
intentionally deferred to the planned system-wide redesign in Phase 12 and final
portfolio refinement in Phase 15. Automated viewport and interaction checks do not
claim final visual or accessibility certification.

Phase 3 was accepted by the owner on 2026-10-14 based on the functional evidence in
this report. Phase 4 has not started.
