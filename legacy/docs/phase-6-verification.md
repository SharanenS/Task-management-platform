# Phase 6 verification

Status: **Accepted**

The owner accepted Phase 6 on 2026-10-16 after automated verification of durable
job submission and persistence, typed payload validation, actor-scoped
idempotency, concurrent PostgreSQL behavior, owner and ADMIN authorization,
project-access enforcement, pagination, empty attempt history, responsive
behavior, Job Service outage and recovery, Job PostgreSQL outage and recovery, and
exact disposable-resource cleanup.

Phase 6 introduces a durable Job Service and job-management interface. Phase 7 has
not started. RabbitMQ and Celery are not configured, no worker runs, no job is
dispatched, and no execution attempt, progress, or result is fabricated. The stack
contains eleven Compose services.

## Contract and boundaries

The supported type is `PROJECT_TASK_EXPORT`. Its typed payload contains a stable
project UUID, fixed `CSV` format, and `includeCompleted` boolean. This is the
smallest useful contract for later worker execution while avoiding arbitrary JSON,
commands, scripts, URLs, secrets, and unsupported nested input.

The Gateway reloads the current Employee profile and validates current project
access through Work Service before submission. Job Service independently enforces
owner or ADMIN visibility using validated internal actor headers and a dedicated
credential. It is not host-published. GraphQL remains the only public business API.
No cross-service distributed transaction is claimed.

Every normal Phase 6 submission begins and remains `SUBMITTED`. The durable future
state model includes `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, and `CANCELLED`,
but no public execution transition exists. The attempt table and GraphQL shape are
present; Phase 6 jobs have zero attempts.

Idempotency uniqueness is scoped by submitter and key. The server fingerprints the
canonical normalized request. An identical replay returns the existing job;
conflicting reuse returns sanitized `IDEMPOTENCY_CONFLICT`; different actors may
reuse a key. PostgreSQL uniqueness resolves concurrent races without an in-memory
lock.

## Coverage matrix

| Requirement                              | Evidence layer                                | Verified evidence                                                                                                                       |
| ---------------------------------------- | --------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Typed payload validation and size limits | Job unit and API                              | Typed UUID, enum, boolean, unknown-field, unsupported-type, and canonical serialized-size boundaries                                    |
| Initial `SUBMITTED` behavior             | Job unit, Gateway, component, browser         | New jobs remain `SUBMITTED`; no Phase 6 transition endpoint or UI action exists                                                         |
| State-machine validation                 | Job unit                                      | Allowed future transitions and invalid transitions are checked without exposing execution                                               |
| Idempotency and concurrency              | Job unit, PostgreSQL, browser                 | Identical replay, conflict, actor scoping, concurrent identical and conflicting submission, database uniqueness, and rollback integrity |
| Owner and ADMIN authorization            | Job unit, Gateway, multi-role browser         | Owner list/detail, non-owner omission and concealed detail, direct GraphQL denial, and ADMIN inspection                                 |
| Current Employee profile reload          | Gateway                                       | Every query and mutation reloads the current active Employee profile before Job Service access                                          |
| Project access validation                | Gateway and multi-role browser                | Work Service access is checked before submission; an active project contributor submits successfully                                    |
| Pagination boundaries                    | Job unit, Gateway, component                  | Stable opaque forward cursors, deterministic ordering, malformed cursor handling, and bounded page size                                 |
| Empty attempts                           | Job unit, Gateway, component, browser         | New jobs have zero durable attempts and the UI states that execution begins in Phase 7                                                  |
| Persistence                              | PostgreSQL and browser                        | Reconnect and Job Service restart retain the submitted job                                                                              |
| Job Service outage                       | Real browser                                  | Fixed sanitized failure, service restoration, real-query recovery, and idempotent replay                                                |
| Job PostgreSQL failure/recovery          | Real browser                                  | No false success during database outage; recovery, one durable job, replay, and sanitized conflict                                      |
| Responsive behavior                      | Real browser                                  | Desktop, 768 px, and 390 px lifecycle with storage and document-overflow checks                                                         |
| Exact cleanup                            | Service CLI and real browser                  | Exact job UUID, project UUID plus expected key, and exact Keycloak subject/profile cleanup                                              |
| Phase 7 exclusions                       | Unit, component, browser, architecture review | No RabbitMQ, Celery, worker, dispatch, retry, cancel, progress, fabricated attempt, or result behavior                                  |

## Automated results

The final service and static verification completed on 2026-10-16:

| Area                      | Command                                                                                        | Result                                                                                                             |
| ------------------------- | ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Job Service               | `pytest -q`                                                                                    | 21 passed, 4 PostgreSQL-only skips                                                                                 |
| Job PostgreSQL            | `pytest -q tests/test_postgres.py` with `JOB_POSTGRES_TEST_URL`                                | 4 passed                                                                                                           |
| Job migration             | `alembic upgrade head` twice, then `alembic current`, in an isolated empty PostgreSQL database | clean upgrade; repeated upgrade passed; `20261016_01 (head)`                                                       |
| Job static checks         | `ruff check .`, `ruff format --check .`, `mypy app tests`                                      | passed; 12 source files checked by MyPy                                                                            |
| Employee Service          | `pytest -q`, Ruff lint and format, MyPy                                                        | 40 passed; all static checks passed; 10 source files checked by MyPy                                               |
| Work Service              | `pytest -q`                                                                                    | 48 passed, 5 PostgreSQL-only skips                                                                                 |
| Work PostgreSQL           | `pytest -q tests/test_postgres.py` against an isolated PostgreSQL 18 database                  | 5 passed                                                                                                           |
| Work static checks        | Ruff lint and format, MyPy                                                                     | passed; 8 source files checked by MyPy                                                                             |
| Gateway                   | `pytest -q`                                                                                    | 82 passed                                                                                                          |
| Gateway static checks     | Ruff lint and format, MyPy                                                                     | passed; 8 source files checked by MyPy                                                                             |
| GraphQL contract          | `python export_schema.py`; `npm run codegen`                                                   | schema export and generated frontend operations passed                                                             |
| Frontend                  | `npm test -- --run`                                                                            | 46 passed in 10 files                                                                                              |
| Frontend static checks    | `npm run lint`; `npm run typecheck`; `npm run format:check`                                    | passed                                                                                                             |
| Frontend production build | `npm run build`                                                                                | passed; all 20 routes built, including the three job routes                                                        |
| Compose                   | `docker compose config --quiet`; `docker compose build job gateway frontend`                   | passed                                                                                                             |
| Python dependency audit   | `pip-audit -r` for Job, Employee, Work, and Gateway locks                                      | no known vulnerabilities in all four locks                                                                         |
| Production npm audit      | `npm audit --omit=dev`                                                                         | 0 vulnerabilities                                                                                                  |
| Full npm audit            | `npm audit`                                                                                    | exited 1 with the existing 12 high-severity development-only `braces` findings in lint and code-generation tooling |

The ordinary Job Service suite skips only the four tests that require a real
PostgreSQL URL. All four passed in the separate PostgreSQL run. They prove that
concurrent identical requests create one job; concurrent conflicting requests
produce one durable winner and one sanitized conflict; the losing transaction does
not poison replay or create a partial row; different actors can reuse one key; the
database uniqueness constraint enforces the actor/key invariant; and a new engine
and connection retain committed data. The ordinary Work
Service suite similarly skips five PostgreSQL-specific tests, and all five passed
separately against PostgreSQL 18. The database tests used unique temporary
databases, applied the real migration chain, and removed those exact databases
afterward.

### Browser and recovery results

The primary Phase 6 lifecycle passed once in each Playwright project: desktop,
768 px tablet, and 390 px mobile, for **3 passed, 0 failed**. Each journey created
unique project and job records, submitted through the public GraphQL path, proved
the durable `SUBMITTED` state and typed CSV payload, confirmed zero attempts and no
execution controls, reloaded the detail, checked storage and horizontal overflow,
proved identical replay and sanitized conflict behavior, and removed its exact
records.

The combined Phase 1, Phase 2, Phase 4, Phase 5, and Phase 6 responsive collection
completed with **24 passed, 12 intentionally skipped, 0 failed**. The twelve skips
are four opt-in authentication scenarios repeated across the three viewport
projects: the slow refresh check, inactive-profile check, refresh-failure outage,
and login-time Keycloak outage. They were excluded from the viewport collection to
avoid repeating destructive or slow scenarios. The slow refresh, refresh-failure,
and login-outage scenarios were then enabled in the serial desktop recovery run.
The inactive-profile scenario is an opt-in Phase 2 fixture that requires a
separately prepared disposable inactive identity. It was not enabled in the
combined viewport collection. Its accepted Phase 2 service, Gateway, and browser
evidence remains unchanged; no new pass is claimed here.

The serial legacy recovery collection completed with **8 passed, 1 intentionally
skipped, 0 failed**. It covered login and logout, the 65-second session refresh,
Keycloak refresh failure and recovery, Keycloak login outage and recovery, Gateway
outage and recovery, Employee Service outage and recovery, and Work Service restart,
outage, persistence, and recovery. The single skip was the separately prepared
inactive-profile fixture described above.

The new Job Service restart, outage, sanitized failure, real-query recovery, and
idempotent replay scenario completed with **1 passed, 0 failed**. It ran serially
with one worker and no retries and restored Job Service in `finally` cleanup.

The Employee Administration lifecycle fixture now derives a unique username and
email for every run, records the exact created Keycloak subject, and removes only
that subject and linked Employee profile in `finally`. The complete lifecycle
passed **1 passed, 0 failed**. The ambiguous fixed identity that caused the earlier
collision remains untouched.

The new serial multi-role Job journey passed **1 passed, 0 failed** with fresh
browser contexts. An active MEMBER project contributor submitted and inspected the
job; another MEMBER could neither list it nor distinguish its detail from a missing
job; a direct request with forged actor fields received fixed GraphQL validation;
ADMIN inspected it; both browser stores remained empty; and the job remained
`SUBMITTED` with zero attempts and no execution behavior. Its exact job, project,
two Employee profiles, and two Keycloak subjects were removed.

The real Job PostgreSQL outage/recovery journey passed **1 passed, 0 failed**. It
stopped only `job-db`, observed fixed `SERVICE_UNAVAILABLE` with no success
navigation or internal detail, restored the database, waited for a real jobs query,
retried the same key to create exactly one job, replayed to the same UUID, received
sanitized `IDEMPOTENCY_CONFLICT` for changed input, and removed the exact job and
project in `finally`.

### Failed attempts and corrections

- The first local focused Vitest command could not spawn its worker inside the
  restricted environment. The same command ran successfully with the required
  execution permission.
- The first focused jobs test expected the shared retry control to be named
  `Retry`; the implemented shared component correctly exposes `Try again`. The
  semantic assertion was corrected and all four focused tests passed.
- The first frontend format check identified only the two new Playwright files.
  Prettier formatted them, and the complete format check then passed.
- The first isolated Work PostgreSQL command used an unavailable global `alembic`
  executable. Its `finally` cleanup removed the empty temporary database. The
  corrected command used the repository virtual environment and all five tests
  passed.
- The first exact persistence-record cleanup invoked the Job cleanup CLI with an
  unsupported option form. The corrected positional UUID invocation removed the
  exact current-run record.
- The first dependency-audit attempt could not create audit environments in the
  system temporary directory. Repeating it with an isolated workspace temporary
  directory produced four successful audits, and that directory was removed.
- Workspace-local test output was removed. Some ignored Python cache directories
  could not be deleted because Windows denied access; Git confirms that none is in
  the deliverable set. The first compact audit script and first concise Docker
  health-format command had PowerShell and template-quoting errors respectively;
  corrected read-only commands completed successfully.
- The first two multi-role Job attempts used an invalid paginated selection on the
  list-valued `attempts` field and then expected raw schema-validation wording.
  The test was corrected to use the published schema and fixed sanitized GraphQL
  message; the complete journey then passed without changing production behavior.
- Initial frontend Vitest and production-build invocations encountered restricted
  worker `spawn EPERM` errors. Both complete commands passed when rerun with the
  required execution permission.

## Cleanup and limitations

Development cleanup is an unexposed CLI that refuses production and removes only
an exact job UUID through Job Service-owned models. Browser tests use unique
project and idempotency markers and remove only their exact jobs and project.

All Phase 6 browser-owned jobs and projects were removed. The PostgreSQL
persistence-test job was removed by its exact UUID through the Job Service cleanup
CLI, and a final marker query returned zero remaining Phase 6 test jobs. Both
isolated test databases were removed. The pre-existing Employee Administration
identity described above remains untouched because its ownership is ambiguous.
The primary administrator remains unique, Keycloak-enabled, active, linked by its
stable subject, and assigned `ADMIN`.

Final read-only counts were zero current-run jobs, zero current-run projects, zero
current-run disposable Employee profiles, zero current-run Keycloak identities,
and zero temporary Phase 6 databases. The ambiguous pre-existing identity count
remained one.

The accepted limitations are one supported job type (`PROJECT_TASK_EXPORT`), one
output format (`CSV`), forward-only service pagination, visited-cursor previous
navigation only within the browser session, deterministic concurrency verification
rather than performance or load certification, and no cross-service distributed
transaction guarantee. Automated accessibility evidence is not accessibility
certification. Subjective visual and UX redesign remains deferred to Phases 12 and 15. The ambiguous pre-existing Employee Administration identity remains untouched.
These limitations do not block Phase 6 acceptance.

Acceptance does not claim RabbitMQ, Celery, a worker, dispatch, execution retry,
cancellation behavior, fabricated attempt, progress, result, or queue state, a
transactional outbox, or a delivery guarantee. Phase 7 has not started.
