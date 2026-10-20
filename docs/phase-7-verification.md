# Phase 7 verification — RabbitMQ and Celery Job Execution

Status: **Accepted**

Owner acceptance completed on 2026-10-20 after automated functional,
authorization, security, execution-lifecycle, concurrency, persistence, retry,
outage, recovery, responsive-overflow, and basic accessibility verification.

Phase 7 adds real local execution for `PROJECT_TASK_EXPORT`. Phase 8 transactional
outbox work and Phase 9 execution leases, fencing, stale-worker protection, and
recovery have not started. Subjective visual and UX redesign remains deferred to
Phases 12 and 15.

## Implemented boundary

- RabbitMQ 3.13.7 is internal-only, pinned by immutable image digest, and uses a
  dedicated account and virtual host from the ignored environment file. The
  durable `job.execution` queue is bound to a
  durable direct exchange by `job.execute`; messages are persistent JSON and
  contain only the job UUID.
- One Job Service-owned Celery worker accepts only the export task. It uses late
  acknowledgement, worker-loss rejection, prefetch one, concurrency two, no
  Celery result backend, a 25-second soft limit, and a 30-second hard limit.
- Dispatch reloads the current Employee profile at the Gateway, revalidates the
  project through Work Service, checks owner or ADMIN access in Job Service, locks
  the `SUBMITTED` job at its expected version, commits `QUEUED`, and requests a
  publisher confirmation.
- An unambiguous publication failure compensates back to `SUBMITTED` only while
  the exact queued version remains unclaimed. An ambiguous confirmation leaves the
  honest `QUEUED` state for manual investigation.
- Claim atomically moves `QUEUED` to `RUNNING` and creates one durable attempt.
  Duplicate deliveries and deliveries for ineligible states are safe no-ops.
- Transient Employee or Work dependency failures create `RETRY_SCHEDULED`
  attempts and use at most two Celery retries with bounded backoff. Validation,
  authorization, missing-resource, inactive-employee, and unsupported-type
  failures are permanent. Only fixed classifications are persisted.
- Success stores the attempt and job terminal state with CSV text, content type,
  SHA-256 checksum, row count, truncation flag, and completion timestamp in one
  transaction. Results are limited to 500 rows and 256,000 UTF-8 bytes.
- CSV uses a real writer and a six-column allowlist. Commas, quotes, newlines, and
  Unicode remain valid CSV. Cells beginning with `=`, `+`, `-`, `@`, tab, or
  carriage return receive a leading apostrophe before persistence.
- The job page confirms dispatch, prevents duplicate clicks, polls every two
  seconds only for `QUEUED` and `RUNNING`, prevents overlapping reads, stops on
  unmount or terminal state, supports manual refresh, renders CSV as inert text,
  and downloads it under the fixed name `project-task-export.csv`.

## Reliability boundary

Direct publication is a temporary adapter. A process crash after the database
commit and before broker publication can leave a committed `QUEUED` job
unpublished. A lost publisher confirmation can make the publication result
ambiguous and may cause duplicate delivery. Atomic claim prevents duplicate
execution after delivery, but Phase 7 does not guarantee publication. Phase 8
will replace this path with a transactional outbox.

A worker crash after claim can leave a job `RUNNING`. Phase 7 has no execution
lease, fencing token, recovery daemon, or stale-worker settlement protection.
Those controls remain Phase 9 work.

## Coverage matrix

| Requirement                                                                  | Automated evidence                                                       |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| Dispatch authorization, version, state, compensation, ambiguous confirmation | Job Service and Gateway unit tests                                       |
| UUID-only persistent publication and fixed failure mapping                   | Publisher unit tests                                                     |
| Claim, duplicate claim, attempt numbering, settlement, retry exhaustion      | Job Service unit tests                                                   |
| Concurrent submission, dispatch, claim, and retry-state persistence          | Seven PostgreSQL tests with deterministic barriers                       |
| Current Employee and project-access reload                                   | Handler, Gateway, and real lifecycle tests                               |
| CSV quoting, formula defense, checksum, bounds, and inert presentation       | Handler and frontend component tests                                     |
| Confirmation, duplicate click, attempt/result views, polling boundary        | Frontend component tests                                                 |
| Real submit, dispatch, execution, refresh persistence, storage, and cleanup  | Browser lifecycle at desktop, 768 px, and 390 px                         |
| Owner, non-owner, and ADMIN behavior                                         | Serial disposable-identity browser journey                               |
| Duplicate broker delivery                                                    | Controlled internal publication while the worker is stopped              |
| Worker outage and queued recovery                                            | Serial opt-in browser recovery test                                      |
| RabbitMQ outage, compensation, sanitized response, and recovery              | Serial opt-in browser recovery test                                      |
| Clean and upgrade migrations                                                 | PostgreSQL migration from zero, accepted Phase 6 head, and repeated head |

## Automated results

The final verification collection records:

- Job Service: 41 passed and 7 PostgreSQL-only skips in the ordinary suite.
- Job PostgreSQL: 7 passed separately against PostgreSQL 18.
- Employee Service: 40 passed.
- Work Service: 48 passed and 5 PostgreSQL-only skips; all 5 passed separately.
- Gateway: 86 passed.
- Frontend Vitest: 48 passed in 10 files.
- Schema export and GraphQL generation: completed successfully.
- Docker production builds: completed successfully for all application images.
- RabbitMQ pin and topology: RabbitMQ reported 3.13.7 from immutable digest
  `sha256:606d8c0d6b3c18d1da9afc53bc7cdb2a8d5486df91b5a9830e9e07626c9ae281`.
  The `jobs` virtual host, dedicated `job-worker` account, durable
  `job.execution` direct exchange and queue, `job.execute` binding, broker health,
  and worker ping passed. Broker and management ports remained unbound from the
  host.
- Migration head: `20261020_03`; clean, Phase 6 upgrade, and repeated-head runs
  completed successfully.
- Primary execution lifecycle: 3 passed, 0 failed, and 0 skipped across desktop,
  768 px, and 390 px after the responsive correction.
- Multi-role execution: 1 passed on desktop.
- Worker and RabbitMQ outage/recovery with duplicate delivery: 1 passed on
  desktop, one worker, no retries.
- Disposable inactive profile: 1 passed on desktop in a fresh browser context;
  the sanitized access-denied page appeared and no application session cookie was
  created.
- Transient Work Service failure and bounded retry: 1 passed within the
  disposable multi-role journey. Attempt 1 persisted `RETRY_SCHEDULED` with
  `DEPENDENCY_UNAVAILABLE`; attempt 2 succeeded after bounded health polling.
- Permanent current-access failure: 1 passed within the same journey. A uniquely
  created MEMBER was deactivated after dispatch and before claim; exactly one
  `SUBMITTER_INACTIVE` attempt was persisted, no retry or result was created, and
  the profile was restored before exact cleanup.
- Corrected serial authentication and outage collection: 12 passed, 1 intentional
  skip, and 0 failed with one worker and no retries. The skip is the superseded
  primary-credential inactive-profile case; the separately prepared disposable
  inactive-profile test passed in the same collection.
- Python dependency audits: pip-audit 2.10.1 reported no known vulnerabilities in
  every pinned package enumerated by the Job, Gateway, Employee, and Work lock
  files. The successful equivalent method used `--no-deps --disable-pip` only
  after the normal resolver-based method was environment-blocked; each lock lists
  its transitive dependencies, including Celery, Kombu, AMQP, billiard, and vine.
- Complete non-outage Phase 1–7 browser regression collection: 28 passed, 11
  intentional skips, and 0 failed across the configured projects.
- Earlier serial outage and recovery collection: 9 passed, 2 intentional skips, and 1
  test-setup failure. The failure was the inactive-profile scenario running with
  the active primary development administrator; it reached the authenticated
  application instead of the expected access-denied page. The primary profile
  was not deactivated to satisfy a test precondition. The same collection passed
  the Keycloak refresh and login recovery, Gateway recovery, Employee Service
  recovery, Work Service recovery, Job Service recovery, Job PostgreSQL recovery,
  and worker/RabbitMQ recovery scenarios.
- Production npm audit: 0 vulnerabilities. The full npm audit retained 12 high
  severity `braces` findings in development-only tooling.

The ordinary Job suite skips exactly the seven tests in `test_postgres.py` when
`JOB_POSTGRES_TEST_URL` is absent. They are intentionally separated because they
truncate the dedicated test tables and require PostgreSQL locking semantics. The
ordinary Work suite uses the same intentional separation for its five PostgreSQL
tests.

The 11 non-outage browser skips are intentional project applicability gates:
desktop-only multi-role and lifecycle journeys do not repeat in the tablet and
mobile projects, outage suites require their explicit opt-in flags, and the
inactive-profile scenario requires a deliberately inactive disposable identity.
The two outage-collection skips were opt-in scenarios whose flags were not enabled
for that command. The inactive-profile setup failure remains recorded as a failed
attempt; it is not counted as a successful acceptance result or an application
defect.

## Failed attempts and corrections

- The initial dependency-lock command failed because the installed `pip-tools`
  version was incompatible with the current resolver. Updating local verification
  tooling to 7.6.2 allowed the Job lock to regenerate.
- The first local environment-value generator used a PowerShell API unavailable in
  that host and produced empty additions. They were replaced immediately with
  cryptographically random values; no value is recorded here.
- The first RabbitMQ 4.2 image pull failed twice because Docker could not resolve
  its registry content host. The available `rabbitmq:3-management-alpine` image
  was selected and verified without exposing any broker or management port.
- A PostgreSQL test command first referenced environment names that do not define
  the Job database user and database, then used the exact Compose-owned `job`
  values and passed all tests. No database or volume was recreated.
- Vitest first failed to start because its build worker could not spawn in the
  restricted environment. The unchanged suite passed with the required process
  permission.
- The initial three-viewport lifecycle passed desktop and 768 px but found
  document overflow at 390 px. The job result container and inert CSV view were
  constrained to their parent width, and the complete collection was rerun.
- A final serial outage collection incorrectly enabled the inactive-profile test
  with the active primary administrator credentials. The application correctly
  admitted that active profile. The primary administrator was left unchanged, and
  the invalid setup was not hidden with a retry or counted as a pass.
- The first real transient-dependency journey exposed a PostgreSQL migration
  defect: the application enum included `RETRY_SCHEDULED`, but the database enum
  did not. The worker therefore could not settle the retryable attempt. Forward
  migration `20261020_03` adds the value, a PostgreSQL regression test persists
  the state, and the complete disposable multi-role journey then passed.
- The first corrected retry test used `docker compose start job-worker`, which
  also restored Work Service and produced a valid first-attempt success. Starting
  the exact worker container kept Work unavailable until the persisted retry
  state was observed. A later assertion expected descriptive text rather than the
  implemented fixed safe summary; it was corrected without changing production
  behavior.
- The first disposable inactive-profile assertion searched for the word
  `inactive`, while the sanitized page says that no active profile is linked. The
  assertion was corrected to the exact application-owned message and passed on
  the complete rerun.
- Initial Python dependency-audit attempts could not complete in the restricted
  Windows environment: sandboxed runs failed while creating the temporary audit
  virtual environment, and the first permitted resolver query produced no result
  before bounded termination. The technically equivalent every-pinned-package
  method then completed successfully for all four locks with the result recorded
  above. No temporary audit directory remains.
- Automatic command review rejected the first fixed-name PostgreSQL test cleanup
  because an unconditional drop could remove a pre-existing database if creation
  failed. The replacement used a unique current-run database and dropped it only
  after confirmed creation.

## Recovery and cleanup

The worker test stopped only `job-worker`, dispatched a unique job, verified it
remained `QUEUED` with zero attempts, published the same UUID twice through an
internal development command, restarted the worker, and observed one successful
attempt and one result. The RabbitMQ test stopped only `rabbitmq`, received the
fixed `BROKER_UNAVAILABLE` response, verified compensation to `SUBMITTED`, restored
the broker and worker, dispatched again, and observed `SUCCEEDED`.

Every browser journey removed jobs by exact UUID and projects by exact UUID plus
expected unique key. The multi-role journey also removed each exact Employee
profile and Keycloak subject it created. The primary administrator was not used as
a destructive target. Existing accepted application data and the ambiguous
pre-existing Employee Administration identity were left untouched.

Final model-owned checks reported zero Phase 7 marker jobs, projects, Employee
profiles, and Keycloak identities. The journeys created no retained test tasks.
The unique PostgreSQL test databases were dropped only after confirmed creation,
and no one-off test container remained. The idempotent bootstrap confirmed that
the unique primary administrator remains enabled, active, ADMIN, and linked to
the same Keycloak subject.

## Security review

The broker message has no payload or actor context. Separate credentials protect
Gateway-to-Job, worker-to-Employee, worker-to-Work, and RabbitMQ traffic. Internal
services are not host-published. Network calls and worker execution are bounded.
Celery accepts JSON only; pickle is disabled. No task payload, token, credential,
CSV content, raw exception, response body, internal URL, or stack trace is logged
or returned through GraphQL.

## Accepted limitations

- Direct publication has the documented commit-to-publish and ambiguous-confirm
  windows and provides no delivery guarantee.
- A worker crash after claim can leave a job `RUNNING` until Phase 9 recovery.
- The handler supports one job type, CSV output, 500 rows, and 256,000 encoded
  bytes. Results remain in Job PostgreSQL rather than external object storage.
- Retries cover allowlisted transient dependency failures only and are bounded to
  two retries after the first attempt. There is no public arbitrary retry action.
- Forward-only service pagination and browser-session visited-cursor navigation
  remain unchanged.
- Deterministic concurrency verification is not performance or load certification.
- Automated keyboard, overflow, and semantic checks are not accessibility
  certification. Final visual and UX quality remains deferred to Phases 12 and 15.

These limitations are accurate Phase 7 boundaries. They do not represent Phase 8
or Phase 9 completion and do not block Phase 7 acceptance. Phase 8 transactional
outbox work and Phase 9 distributed recovery have not started. Acceptance does not
claim outbox reliability, guaranteed publication, execution recovery, fencing, or
stale-worker safety.
