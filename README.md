# Enterprise Task Platform

A GraphQL-first enterprise work platform, developed in verified full-stack slices.
Phases 1–8 are accepted. Phase 9 has not started.

Phase 2 adds a protected Taskspace shell, Keycloak Authorization Code Flow with
PKCE, Redis-backed server sessions, an Employee Service with its own PostgreSQL
database and Alembic migrations, an authenticated GraphQL `me` query, role-aware
navigation, logout, refresh, and explicit authentication failure states.

Phase 3 adds ADMIN-only employee directory, detail, provisioning, role, status,
and reconciliation workflows. Keycloak owns identities and credentials; Employee
Service owns application profiles, roles, active status, and provisioning state.
The owner accepted Phase 3 on 2026-10-14 after automated functional,
authorization, security, lifecycle, outage, recovery, responsive-overflow, and
basic accessibility checks passed. Subjective visual and UX redesign remains
deferred to Phases 12 and 15; this acceptance is not a final visual or
accessibility certification.

Phase 4 adds project directories, project creation and detail, lifecycle controls,
and membership governance. The Work Service owns project and membership data in
its own PostgreSQL database. The gateway reloads the current Employee Service
profile before every project operation and exposes project behavior only through
typed GraphQL operations.

The owner accepted Phase 4 on 2026-10-14 after automated functional,
authorization, security, lifecycle, persistence, outage, recovery,
responsive-overflow, and basic accessibility checks passed. Forward-only service
pagination, deterministic PostgreSQL contention coverage rather than large-scale
stress, and a desktop multi-role browser lifecycle are accepted limitations.
Automated accessibility evidence is not accessibility certification. Subjective
visual and UX redesign remains deferred to Phases 12 and 15; this acceptance does
not claim final visual quality, performance or load-testing certification, or
accessibility certification.

Phase 5 adds project-scoped task lists and bounded status boards, task creation and
editing, assignment, explicit status transitions, comments, and append-only
activity history. Work Service owns this data in its existing PostgreSQL database;
the gateway remains the only public business API.

The owner accepted Phase 5 on 2026-10-15 after automated functional,
authorization, security, lifecycle, concurrency, persistence, outage, recovery,
responsive-overflow, and basic accessibility verification passed. The accepted
limitations and complete results are recorded in the Phase 5 verification report.
Acceptance does not claim final visual quality, accessibility certification,
performance or load-testing certification, or cross-service distributed
transaction guarantees. Subjective visual and UX redesign remains deferred to
Phases 12 and 15.

Phase 6 adds durable `PROJECT_TASK_EXPORT` submissions, actor-scoped idempotency,
owner and administrator visibility, an empty attempt-history foundation, and job
directory, submission, and detail pages. Job Service owns its PostgreSQL schema
and is reachable only through the public GraphQL Gateway. Every Phase 6 job remains
truthfully `SUBMITTED`; RabbitMQ, Celery, workers, dispatch, and execution are not
configured. At Phase 6 acceptance, Phase 7 had not started.

The owner accepted Phase 6 on 2026-10-16 after automated verification of durable
submission and persistence, typed payload validation, actor-scoped idempotency,
concurrent PostgreSQL behavior, authorization, project access, pagination, empty
attempt history, responsive behavior, service and database recovery, and exact
disposable-resource cleanup. The accepted limitations and complete results are
recorded in the Phase 6 verification report. Acceptance does not claim RabbitMQ,
Celery, workers, dispatch, execution retry, cancellation, fabricated queue or
execution state, a transactional outbox, or a delivery guarantee.

Phase 7 adds manual dispatch, RabbitMQ, a Job Service-owned Celery worker, durable
execution attempts, bounded transient retries, and persisted CSV results. The
worker reloads the submitting Employee profile and revalidates project access
through Work Service before exporting an allowlisted, formula-safe task view.
Direct publication is a temporary adapter: a crash between the database commit
and broker publication can leave a `QUEUED` job unpublished, and an ambiguous
publisher confirmation can cause duplicate delivery. Duplicate delivery is
claimed idempotently, but guaranteed publication is not claimed. A worker crash
after claim can leave a job `RUNNING`. The Phase 8 outbox and Phase 9 lease,
fencing, and recovery work have not started.

The owner accepted Phase 7 on 2026-10-20 after automated functional,
authorization, security, execution-lifecycle, concurrency, persistence, retry,
outage, recovery, responsive-overflow, and basic accessibility verification. The
accepted limitations and complete results are recorded in the Phase 7 verification
report. Acceptance does not claim outbox reliability, guaranteed publication,
execution recovery, fencing, stale-worker safety, performance or load-testing
certification, accessibility certification, or final visual quality. Subjective
visual and UX redesign remains deferred to Phases 12 and 15. At Phase 7
acceptance, Phase 8 and Phase 9 had not started.

Phase 8 replaces request-path broker publication with a transactional outbox. A
manual dispatch atomically commits the `QUEUED` transition and one durable event;
the independent `job-publisher` claims events with PostgreSQL leases, publishes
the UUID-only message with confirmation, and retries fixed classified failures.
Job detail separates execution from publication state, and administrators receive
global publication diagnostics. Eligible committed events have at-least-once
publication under the retry model; exactly-once delivery is not claimed. Phase 8
was accepted by the owner on 2026-10-20 after automated functional,
authorization, security, persistence, concurrency, migration, outage, recovery,
responsive-overflow, and basic accessibility verification. Phase 9 has not
started.

Accepted Phase 8 limitations remain explicit: publication is at least once, not
exactly once, and duplicate publication remains possible while worker idempotency
prevents duplicate logical execution. Publisher leases govern publication only.
Publisher health covers process liveness and PostgreSQL availability, not
RabbitMQ or a durable heartbeat. There is no multi-replica publisher deployment
or load certification. A worker crash after execution claim can still leave a job
`RUNNING`; execution leases, fencing, stale-worker protection, the recovery
daemon, and administrative execution retry belong to Phase 9. Subjective visual
and UX redesign remains deferred to Phases 12 and 15.

## Run with Docker

Prerequisites are Docker Desktop with Linux containers, Node.js 24, and PowerShell.
From the repository root:

```powershell
Copy-Item .env.example .env
# Replace every change-me value in .env with a unique local value.
docker compose up --build -d
docker compose ps
.\scripts\bootstrap-development.ps1
```

Open http://localhost:3010 and select **Sign in**. Use the development username
and password stored only in the ignored `.env` file. The bootstrap is idempotent:
it creates or updates one Keycloak identity and its matching active Employee
Service profile. Public registration remains disabled.

Local endpoints:

- Application: http://localhost:3010
- Keycloak: http://localhost:8080
- GraphQL gateway: http://localhost:8010/graphql
- Gateway health: http://localhost:8010/health/live and `/health/ready`
- Employee PostgreSQL: loopback port 5435
- Work PostgreSQL: loopback port 5436
- Job PostgreSQL: loopback port 5437
- Session Redis: loopback port 6380

Keycloak, Employee Service PostgreSQL, Work Service PostgreSQL, Job Service
PostgreSQL, RabbitMQ, and Redis each use a distinct named volume. RabbitMQ is
internal-only; no broker or management port is published to the host. Do not use
`docker compose down --volumes` when the data should be retained.

## Authentication boundary

The browser receives only opaque session and CSRF cookies. Access, refresh, and ID
tokens remain in Redis and are used by Next.js server routes. `/graphql` is a
same-origin transparent transport that attaches the current access token before
forwarding the GraphQL request to the public gateway. It does not create a second
business API.

The browser uses the public issuer `http://localhost:8080/realms/taskspace` for
authorization and logout. Containers use `http://keycloak:8080` for token and JWKS
traffic. The gateway still validates the exact public issuer in every token. The
HTTP allowance is explicitly limited to loopback local development; deployed
environments must use HTTPS.

## Verify

```powershell
.\.venv\Scripts\python.exe -m pytest gateway/tests
.\.venv\Scripts\python.exe -m ruff check gateway
.\.venv\Scripts\python.exe -m ruff format --check gateway
.\.venv\Scripts\python.exe -m mypy gateway/app
.\.venv\Scripts\python.exe -m pytest services/employee/tests
.\.venv\Scripts\python.exe -m ruff check services/employee
.\.venv\Scripts\python.exe -m ruff format --check services/employee
.\.venv\Scripts\python.exe -m mypy services/employee/app
.\.venv\Scripts\python.exe -m pytest services/work/tests
.\.venv\Scripts\python.exe -m ruff check services/work
.\.venv\Scripts\python.exe -m ruff format --check services/work
.\.venv\Scripts\python.exe -m mypy services/work/app
Set-Location frontend
npm run codegen
npm run typecheck
npm run lint
npm test
npm run format:check
npm run build
npm audit --omit=dev
Set-Location ..
docker compose config --quiet
docker compose build
```

The Docker-backed authentication suite is opt-in and reads credentials from the
process environment. It never embeds them in test source or reports:

```powershell
$settings = @{}
Get-Content .env | ForEach-Object {
  if ($_ -match '^([^#=]+)=(.*)$') { $settings[$matches[1]] = $matches[2] }
}
$env:RUN_AUTH_E2E = "1"
$env:DEV_USER_USERNAME = $settings.DEV_USER_USERNAME
$env:DEV_USER_PASSWORD = $settings.DEV_USER_PASSWORD
Set-Location frontend
npx playwright test authentication foundation --project=desktop --workers=1
$env:RUN_AUTH_REFRESH_E2E = "1"
npx playwright test authentication --project=desktop --workers=1 --grep "expired access token"
Remove-Item Env:RUN_AUTH_E2E, Env:RUN_AUTH_REFRESH_E2E, Env:DEV_USER_USERNAME, Env:DEV_USER_PASSWORD
```

The Phase 3 browser journey also reads its disposable identity values from `.env`.
Set `RUN_EMPLOYEE_ADMIN_E2E=1` and export the `PHASE3_E2E_*` variables before
running `tests/e2e/employee-administration.spec.ts`. Never use the primary
administrator as the disposable identity.

The Phase 4 browser journey is also opt-in. Set `RUN_PROJECT_E2E=1`, export the
development administrator username and password from the ignored `.env`, and run
`tests/e2e/project-management.spec.ts`. It creates a unique project and removes
only that project after the test by matching both its UUID and key.

The real multi-role and Work outage journeys require
`RUN_PROJECT_MULTI_ROLE_E2E=1` and `RUN_PROJECT_OUTAGE_E2E=1`, respectively. They
run serially, use only unique test-owned resources, restore stopped services, and
perform exact cleanup.

The Phase 5 task lifecycle is opt-in through `RUN_TASK_E2E=1`. It runs at desktop,
768 px, and 390 px using credentials from the ignored `.env`. The existing
multi-role and Work recovery journeys also verify contributor/non-member task
authorization and task, comment, and activity persistence.

The Phase 7 job lifecycle is opt-in through `RUN_JOB_E2E=1`. The owner/non-owner
journey uses `RUN_JOB_MULTI_ROLE_E2E=1`. The serial worker and RabbitMQ recovery
journey uses `RUN_JOB_EXECUTION_OUTAGE_E2E=1`; it verifies exact service targets,
duplicate delivery, service restoration, and exact test-owned cleanup.

Generated GraphQL TypeScript is committed for reproducible builds. After schema
changes, run `gateway/export_schema.py` and `npm run codegen`, then review both.

## Repository

| Directory                  | Responsibility                                                  |
| -------------------------- | --------------------------------------------------------------- |
| `frontend/`                | Next.js UI, BFF session boundary, same-origin GraphQL transport |
| `gateway/`                 | Public GraphQL schema, JWT validation, service composition      |
| `services/employee/`       | Employee profiles, roles, access status, migrations             |
| `services/work/`           | Projects, memberships, lifecycle, and owned migrations          |
| `services/job/`            | Durable jobs, execution attempts, worker, results, migrations   |
| `infrastructure/keycloak/` | Reproducible realm and public-client configuration              |
| `docs/`                    | Architecture, dependency, progress, and verification records    |

See [architecture](docs/architecture.md), [dependency review](docs/dependency-review.md),
and [Phase 8 verification](docs/phase-8-verification.md).
