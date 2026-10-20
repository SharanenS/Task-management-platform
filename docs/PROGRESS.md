# Project progress

Last updated: 2026-10-20

## Phase 1 â€” Project Foundation and Frontend Design System

Status: **Accepted**

Delivered:

- Responsive Next.js application shell and reusable interface states.
- Clearly labeled demonstration dashboard content.
- Live GraphQL System Status and interactive Design System pages.
- FastAPI and Strawberry gateway with `systemInfo`, health endpoints, bounded
  query complexity, sanitized failures, and generated client types.
- Docker, automated, browser, accessibility, outage, and recovery verification.

## Phase 2 â€” Authentication and Real Application Shell

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

## Phase 3 â€” Employee Administration

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

## Phase 4 â€” Project Management

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

## Phase 5 â€” Task Management

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
or cross-service distributed transaction guarantees.

## Phase 6 â€” Job Management

Status: **Accepted**

Delivered:

- Independent Job Service and PostgreSQL database with a forward-only migration.
- Typed `PROJECT_TASK_EXPORT` payloads, durable `SUBMITTED` jobs, empty attempt
  history, and actor-scoped database-enforced idempotency.
- Current-profile reload at the Gateway, Work Service project-access validation,
  and independent Job Service owner/ADMIN enforcement.
- Job directory, filters, visited-cursor pagination, submission, detail, retryable
  failures, and explicit Phase 7 execution boundary.
- Exact development-only cleanup by job UUID with no public cleanup endpoint.

At Phase 6 acceptance, RabbitMQ and Celery were not configured and no dispatch,
execution progress, attempt, or result was fabricated. Phase 7 now implements
that execution boundary without changing the accepted Phase 6 evidence.

Owner acceptance completed on 2026-10-16 after automated verification of durable
job submission and persistence, typed payload validation, actor-scoped
idempotency, concurrent PostgreSQL behavior, owner and ADMIN authorization,
project-access enforcement, pagination, empty attempt history, responsive
behavior, Job Service and Job PostgreSQL outage recovery, and exact disposable
resource cleanup.

Accepted limitations are one `PROJECT_TASK_EXPORT` job type, CSV output,
forward-only service pagination, browser-session visited-cursor previous
navigation, deterministic concurrency testing rather than performance or load
certification, and no cross-service distributed transaction guarantee. Automated
accessibility evidence is not accessibility certification. Subjective visual and
UX redesign remains deferred to Phases 12 and 15. The ambiguous pre-existing
Employee Administration identity remains untouched. These limitations do not
block Phase 6 acceptance.

## Phase 7 â€“ RabbitMQ and Celery Job Execution

Status: **Accepted**

Delivered:

- Internal RabbitMQ with dedicated credentials, durable routing, persistent JSON
  messages, publisher confirms, health checks, and no host-published broker port.
- One Job Service-owned Celery worker with a dedicated queue, JSON-only task
  allowlist, late acknowledgement, worker-loss rejection, bounded prefetch,
  concurrency, retries, and execution timeouts.
- Expected-version manual dispatch, owner/ADMIN enforcement, current Employee and
  project-access revalidation, and a temporary isolated direct publisher adapter.
- Atomic claim and settlement, durable attempt history, fixed failure categories,
  bounded CSV result storage, UTF-8 CSV quoting, and spreadsheet-formula defense.
- Job detail polling, manual refresh, dispatch confirmation, attempt timeline,
  inert CSV presentation, fixed-name download, and responsive overflow coverage.
- Real worker and RabbitMQ outage/recovery, duplicate-delivery, multi-role, and
  three-viewport lifecycle verification with exact current-run cleanup.

Direct publication does not provide an outbox guarantee. A crash after the
`QUEUED` commit and before publication can leave an unpublished job, and a lost
confirmation can result in duplicate delivery. Idempotent claim prevents duplicate
execution after delivery, but does not guarantee publication. A worker crash after
claim can leave a job `RUNNING`. Phase 8 outbox work and Phase 9 lease, fencing,
and recovery work have not started. Subjective visual redesign remains deferred to
Phases 12 and 15.

The owner accepted Phase 7 on 2026-10-20 after automated functional,
authorization, security, execution-lifecycle, concurrency, persistence, retry,
outage, recovery, responsive-overflow, and basic accessibility verification. The
accepted limitations are the temporary direct publisher and its commit-to-publish
and ambiguous-confirmation windows; possible duplicate delivery without guaranteed
publication; a possible retained `RUNNING` job after worker failure; no execution
lease, fencing token, recovery daemon, or stale-worker protection; PostgreSQL result
storage; and deterministic concurrency evidence rather than load or performance
certification. Automated accessibility evidence is not accessibility certification,
and subjective visual and UX redesign remains deferred to Phases 12 and 15. Phase 8
transactional outbox work and Phase 9 distributed recovery have not started.
Acceptance does not claim outbox reliability, guaranteed publication, execution
recovery, fencing, or stale-worker safety.

## Phase 8 â€” Transactional Outbox and Reliable Job Publication

Status: **Accepted**

Delivered:

- Atomic dispatch state transition and unique durable publication event.
- Independent `job-publisher` process with PostgreSQL claims, leases, publisher
  confirmation, bounded retries, and abandoned-claim recovery.
- Typed owner-visible publication state and ADMIN-only publication diagnostics.
- Explicit legacy reconciliation state for ambiguous pre-Phase-8 queued jobs.

Owner acceptance completed on 2026-10-20 after automated functional,
authorization, security, persistence, concurrency, migration, outage, recovery,
responsive-overflow, and basic accessibility verification. The accepted evidence
is Job Service **48 passed with 12 intentional PostgreSQL-only skips**; Job
PostgreSQL **12 passed**; Work PostgreSQL **5 passed**; Gateway **94 passed**;
Employee Service **40 passed**; Work Service **48 passed with 5 intentional
PostgreSQL-only skips**; frontend **50 passed in 11 files**; non-outage Phase 1–8
browser collection **27 passed, 18 intentional skips, 0 failed**; corrected serial
outage/recovery collection **13 passed, 0 failed**; Phase 8 lifecycle **3 passed**
across desktop, 768 px, and 390 px; real ADMIN diagnostics **1 passed**;
duplicate-publication and broker/worker recovery **1 passed**; and publisher and
Job PostgreSQL recovery **1 passed**. Migration head is `20261020_04`, and all 14
containers were healthy.

Accepted limitations are at-least-once publication without an exactly-once claim;
possible duplicate publication with worker idempotency preventing duplicate
logical execution; publication-only publisher leases; publisher health limited to
process liveness and PostgreSQL availability rather than RabbitMQ or a durable
heartbeat; no multi-replica publisher deployment or load certification; and a
possible retained `RUNNING` job after a worker crash following execution claim.
Subjective visual and UX redesign remains deferred to Phases 12 and 15. These
limitations do not block Phase 8 acceptance.

Phase 9 execution leases, fencing, stale-worker protection, recovery, and
administrative execution retry have not started.
