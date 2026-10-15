# Project progress

Last updated: 2026-10-15

## Phase 1 — Project Foundation and Frontend Design System

Status: **Accepted**

Delivered:

- Responsive Next.js application shell and reusable interface states.
- Clearly labeled demonstration dashboard content.
- Live GraphQL System Status and interactive Design System pages.
- FastAPI and Strawberry gateway with `systemInfo`, health endpoints, bounded
  query complexity, sanitized failures, and generated client types.
- Docker, automated, browser, accessibility, outage, and recovery verification.

## Phase 2 — Authentication and Real Application Shell

Status: **Accepted**

Delivered:

- Keycloak Authorization Code Flow with PKCE, strict state and nonce validation,
  exact redirect targets, disabled registration, and a reproducible realm.
- Redis-backed server sessions with opaque cookies, CSRF-protected logout, a
  distributed refresh lock, and explicit expiry and failure states.
- Protected shell with Employee Service-backed identity and role-aware navigation.
- Same-origin GraphQL transport that supplies access tokens only on the server.
- Gateway JWT signature and claim validation plus authenticated `me` composition.
- Employee Service with owned PostgreSQL database, Alembic migration, stable
  Keycloak-subject link, application role, and active access status.
- Development-only identity/profile bootstrap with credentials held in `.env`.
- Unit, integration, and opt-in Docker-backed browser coverage.

Acceptance completed on 2026-10-14. Automated, Docker-backed, end-to-end, and
manual checks passed. The final development dependency audit records 12
high-severity `braces` findings in repository-controlled code-generation and lint
tooling; the production dependency audit reports zero vulnerabilities.

## Phase 3 — Employee Administration

Status: **Accepted**

Delivered:

- ADMIN-only cursor-paginated directory, search and filters, detail, provisioning,
  role management, activation, deactivation, and reconciliation.
- Defense-in-depth authorization at the gateway and Employee Service boundaries.
- Dedicated Keycloak service account with bounded calls and minimum user-management
  roles assigned by the idempotent development bootstrap.
- Fail-closed identity/profile coordination, idempotent provisioning requests, and
  explicit non-sensitive reconciliation state.
- Forward-only PostgreSQL migration and generated GraphQL client artifacts.
- Responsive UI states, confirmation flows, backend/unit coverage, and a real
  disposable-identity browser journey.

Acceptance completed on 2026-10-14. Automated functional, authorization,
security, lifecycle, outage, recovery, responsive-overflow, and basic
accessibility checks passed. Subjective visual and UX redesign remains
intentionally deferred to Phases 12 and 15; Phase 3 acceptance does not claim
final visual or accessibility certification.

The accepted limitations are forward-only pagination, no concurrent PostgreSQL
stress test, no separate real MANAGER browser journey, and no full real
provisioning-during-Keycloak-outage journey. Ambiguous null-linked idempotency
records remain untouched because their ownership cannot be proven safely. These
limitations do not block Phase 3 functional acceptance.

## Phase 4 — Project Management

Status: **Accepted**

Delivered:

- Work Service with an independently owned PostgreSQL database and forward-only
  Alembic migration for projects and memberships.
- Cursor-paginated project directory, search and status filtering, project detail,
  creation, lifecycle transitions, and membership governance.
- ADMIN override, project-manager administration, contributor read-only access,
  final-project-manager protection, and optimistic version checks.
- Current Employee Service profile reload at the gateway boundary and independent
  authorization enforcement in Work Service.
- Typed GraphQL operations and generated frontend types, responsive project pages,
  and opt-in Docker-backed lifecycle verification with exact test-data cleanup.
- Real manager, contributor, and non-member authorization; PostgreSQL concurrency;
  clean migration; persistence; and dependency outage/recovery verification.

Acceptance completed on 2026-10-14. Automated functional, authorization,
security, lifecycle, persistence, outage, recovery, responsive-overflow, and basic
accessibility checks passed.

The accepted limitations are forward-only service pagination, deterministic
PostgreSQL contention coverage rather than large-scale stress, and a desktop
multi-role browser lifecycle. Basic automated accessibility evidence is not
accessibility certification. Subjective visual and UX redesign remains deferred
to Phases 12 and 15. These limitations do not block Phase 4 functional acceptance,
which does not claim final visual quality, performance or load-testing
certification, or accessibility certification.

## Phase 5 — Task Management

Status: **Accepted**

Delivered:

- Project-scoped tasks with concurrency-safe human-readable references,
  priorities, assignment, due dates, optimistic versions, and an explicit status
  state machine.
- Paginated task lists, bounded board lanes, comments, and append-only activity
  written atomically with domain mutations.
- ADMIN, project-manager, assigned-contributor, and non-member authorization at
  the gateway and Work Service boundaries.
- Responsive task list, board, create, detail, edit, assignment, status, comment,
  and activity interfaces.
- Forward-only Work migration, clean and upgrade migration verification, real
  PostgreSQL contention tests, multi-role browser coverage, and persistence and
  outage recovery verification.

The owner accepted Phase 5 on 2026-10-15 after automated functional,
authorization, security, lifecycle, concurrency, persistence, outage, recovery,
responsive-overflow, and basic accessibility verification passed. The accepted
limitations are forward-only task, comment, and activity pagination;
independently bounded board lanes with `hasMore`; deterministic PostgreSQL
concurrency verification rather than performance or load certification; and a
desktop-only multi-role lifecycle, while the essential lifecycle runs at desktop,
768 px, and 390 px. Comments remain append-only plain text. Due dates remain
date-only, and reminders are outside Phase 5.

These limitations do not block Phase 5 acceptance. Automated accessibility
evidence is not accessibility certification. Subjective visual and UX redesign
remains deferred to Phases 12 and 15. Acceptance does not claim final visual
quality, performance or load-testing certification, accessibility certification,
or cross-service distributed transaction guarantees. Phase 6 has not started.
