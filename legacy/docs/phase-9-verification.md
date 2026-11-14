# Phase 9 verification

Status: **Accepted**

Phase 9 adds durable execution ownership and recovery without changing the
at-least-once publication and execution claim. The owner accepted Phase 9 on
2026-10-27 after reviewing the complete automated evidence and cleanup record.
Phase 10 has not started.

## Automated functional acceptance

| Area                                     | Final result                                                                                                                           |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Job Service                              | 53 passed, 15 intentional PostgreSQL-only skips                                                                                        |
| Job PostgreSQL 18                        | 15 passed against a migrated isolated database                                                                                         |
| Employee Service                         | 40 passed                                                                                                                              |
| Work Service                             | 48 passed, 5 intentional PostgreSQL-only skips                                                                                         |
| Work PostgreSQL 18                       | 5 passed against a migrated isolated database                                                                                          |
| Gateway                                  | 99 passed                                                                                                                              |
| Frontend                                 | 51 passed in 11 files                                                                                                                  |
| Python static checks                     | Ruff lint passed; Ruff format passed for 73 files; strict MyPy passed for all four application modules                                 |
| GraphQL contract                         | Gateway schema export and frontend code generation passed                                                                              |
| Frontend static checks                   | ESLint, TypeScript, and Prettier passed                                                                                                |
| Next.js production build                 | Passed; 21 routes generated or validated                                                                                               |
| Compose                                  | Configuration validation and application image build passed                                                                            |
| Migration                                | Clean zero-to-head, Phase 8 head to `20261020_05`, and repeated head upgrade passed                                                    |
| Python dependency audit                  | All four locks reported no known vulnerabilities after the `certifi` correction                                                        |
| npm production audit                     | 0 vulnerabilities                                                                                                                      |
| Full npm audit                           | 12 existing high-severity development-tool findings through `braces`; only a forced breaking downgrade is offered                      |
| Non-outage browser collection            | 24 passed, 48 intentional skips, 0 failed across desktop, 768 px, and 390 px                                                           |
| Serial service outage/recovery           | 8 passed, 0 failed with one desktop worker                                                                                             |
| Authentication and multi-role collection | Corrected collection: 6 passed, 1 intentional skip, 0 failed; ownership-proven inactive-profile journey: 1 passed, 0 skipped, 0 failed |
| Phase 9 retry-through-exhaustion journey | 1 passed, 0 skipped, 0 failed in 3.2 minutes on desktop with one worker and zero retries                                               |
| Phase 9 worker-crash recovery journey    | 1 passed, 0 skipped, 0 failed on desktop with one worker and zero retries                                                              |

Final closure checks passed Prettier, ESLint, TypeScript, 23 focused frontend
tests across 3 files, and Playwright discovery of both Phase 9 journey files. The
ownership-proven inactive-profile journey then passed separately with one desktop
worker and zero retries.

The 48 non-outage skips are exactly 16 opt-in scenarios in each of the three
projects. They are categorized below rather than treated as passing assertions.

| Scenario                             | Flag                             | D/T/M applicability                          | Skips | Dedicated passing evidence                                                   |
| ------------------------------------ | -------------------------------- | -------------------------------------------- | ----: | ---------------------------------------------------------------------------- |
| Authentication refresh               | `RUN_AUTH_REFRESH_E2E`           | D/T/M opt-in                                 |     3 | Corrected desktop authentication collection                                  |
| Inactive or missing Employee profile | `RUN_ACCESS_DENIED_E2E`          | D/T/M opt-in                                 |     3 | Disposable inactive-profile desktop journey using `RUN_INACTIVE_PROFILE_E2E` |
| Authentication refresh failure       | `RUN_AUTH_FAILURE_E2E`           | D/T/M opt-in                                 |     3 | Corrected desktop authentication collection                                  |
| Login-time Keycloak outage           | `RUN_LOGIN_OUTAGE_E2E`           | D/T/M opt-in                                 |     3 | Corrected desktop authentication collection                                  |
| Gateway dependency recovery          | `RUN_DOCKER_RECOVERY`            | Desktop infrastructure; T/M inapplicable     |     3 | Serial outage collection                                                     |
| Employee Administration lifecycle    | `RUN_EMPLOYEE_ADMIN_E2E`         | Desktop identity lifecycle; T/M inapplicable |     3 | Dedicated accepted-phase journey                                             |
| Employee Service outage              | `RUN_EMPLOYEE_ADMIN_OUTAGE_E2E`  | Desktop infrastructure; T/M inapplicable     |     3 | Serial outage collection                                                     |
| Disposable inactive profile          | `RUN_INACTIVE_PROFILE_E2E`       | Desktop identity lifecycle; T/M inapplicable |     3 | Separate closure journey: 1 passed                                           |
| Job PostgreSQL outage                | `RUN_JOB_DATABASE_OUTAGE_E2E`    | Desktop infrastructure; T/M inapplicable     |     3 | Serial outage collection                                                     |
| Job execution lifecycle              | `RUN_JOB_EXECUTION_OUTAGE_E2E`   | Desktop infrastructure; T/M inapplicable     |     3 | Dedicated broker/worker journey                                              |
| Job multi-role authorization         | `RUN_JOB_MULTI_ROLE_E2E`         | Desktop identity lifecycle; T/M inapplicable |     3 | Corrected collection: 1 passed                                               |
| Job publication recovery             | `RUN_JOB_PUBLICATION_OUTAGE_E2E` | Desktop infrastructure; T/M inapplicable     |     3 | Serial outage collection                                                     |
| Job worker-crash recovery            | `RUN_JOB_RECOVERY_E2E`           | Desktop infrastructure; T/M inapplicable     |     3 | Strengthened real-worker journey: 1 passed                                   |
| Job Service outage                   | `RUN_JOB_OUTAGE_E2E`             | Desktop infrastructure; T/M inapplicable     |     3 | Serial outage collection                                                     |
| Project multi-role authorization     | `RUN_PROJECT_MULTI_ROLE_E2E`     | Desktop identity lifecycle; T/M inapplicable |     3 | Dedicated accepted-phase journey                                             |
| Work Service outage                  | `RUN_PROJECT_OUTAGE_E2E`         | Desktop infrastructure; T/M inapplicable     |     3 | Serial outage collection                                                     |

The viewport collection therefore has 24 executed assertions, 48 intentional
opt-in or inapplicable assertions, and no unexplained coverage gaps. Infrastructure
mutation and disposable multi-role journeys run separately and serially. The
ordinary job lifecycle supplies desktop, 768 px, and 390 px coverage.

The serial collection passed Gateway, Employee Service, Work Service, Job Service,
Job PostgreSQL, publisher, RabbitMQ/worker, and Phase 9 recovery-process outage
scenarios. The corrected authentication collection separately passed
unauthenticated denial, real login and logout, refresh, session-expiration recovery,
Keycloak outage and recovery, and the desktop Job multi-role journey: 6 passed,
1 intentional skip, 0 failed. The skipped case requires a missing or inactive
profile and was excluded because the configured credentials belong to the protected
primary administrator; the dedicated disposable inactive-profile journey passed.
That journey preflighted a unique username, recorded the exact Keycloak subject and
Employee UUID, established inactivity through Employee Service-owned code, verified
denial without an application session, and completed ownership-proven cleanup.
An earlier collection mistakenly enabled that case with the primary administrator
credentials and correctly reached the application. That attempt is neither a
product failure nor a successful missing-profile check.

## Requirement-to-evidence matrix

| Requirement                            | Evidence                                                                                                                                                                                     |
| -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Durable execution ownership            | Job unit and PostgreSQL suites verify persisted token, bounded lease, heartbeat, generation, and fence ownership.                                                                            |
| Stale-worker protection                | PostgreSQL tests reject stale token and fence heartbeat, success, and failure settlement after recovery. A deliberately stale live worker remains unsuitable without an unsafe product hook. |
| Worker-crash recovery                  | The serial browser journey stops the owning worker after a real claim, observes lease expiry and `ABANDONED`, and completes generation 2 without redispatch.                                 |
| Bounded automatic retry and exhaustion | Service, PostgreSQL, Gateway, frontend, and the real browser journey verify three automatic attempts and no fourth automatic generation.                                                     |
| ADMIN manual retry                     | The real journey verifies visibility, confirmation cancellation, one successful retry, one-use policy, and optimistic conflict behavior.                                                     |
| MEMBER and MANAGER denial              | Gateway tests and direct real GraphQL mutations return `FORBIDDEN`; both roles lack the retry control.                                                                                       |
| Generation-scoped publication          | Migration uniqueness and PostgreSQL concurrency tests prove one outbox intent per job, generation, and event type.                                                                           |
| Sanitized public behavior              | Gateway regression tests and browser assertions verify fixed conflict messages and omit lease tokens, fences, internal responses, and credentials.                                           |
| Authentication denial                  | The corrected disposable inactive-profile journey verifies deliberate inactive state, denial without a session, exact ownership, cleanup, and primary-administrator protection.              |
| Migration safety                       | PostgreSQL 18 checks cover zero-to-head, Phase 8-to-Phase 9, repeated head, mappings, indexes, constraints, and retained ambiguous work.                                                     |
| Cleanup and integrity                  | Independent counts are zero for all Phase 9 markers; the primary identity is unique, enabled, active, ADMIN, complete, and linked by its stable subject.                                     |
| Recovery operations                    | Health, serial dependency outages, Compose DNS, downstream connectivity, exact cleanup, and 15-service recovery were verified during the acceptance run.                                     |

## Reliability and security evidence

- Claims persist a random execution lease token, bounded lease timestamps,
  heartbeat time, execution generation, and monotonic fence before work begins.
- Heartbeat and settlement require the current token and fence. Stale success and
  failure settlement are rejected after recovery.
- Recovery uses stable bounded selection with PostgreSQL row locks and
  `SKIP LOCKED`; concurrent recovery creates one next-generation outbox event.
- Automatic execution is bounded at three attempts. Retry delay is capped, retry
  exhaustion is terminal, and one manual ADMIN retry is tracked separately.
- Every retry publication is committed transactionally with its generation. The
  publisher remains the only RabbitMQ publisher.
- The Gateway reloads the Employee profile and rejects MEMBER and MANAGER direct
  GraphQL retry requests before calling Job Service. Job Service repeats ADMIN
  enforcement and optimistic version checks.
- GraphQL and frontend state omit lease tokens and fences. Errors and failure state
  remain sanitized and do not reveal internal addresses, credentials,
  authorization headers, or payload internals.
- Recovery health means process liveness plus Job PostgreSQL availability. It does
  not claim RabbitMQ health or a durable heartbeat.
- The retry-through-exhaustion browser journey produced three automatic failed
  attempts, denied MEMBER and MANAGER direct mutations, preserved cancel behavior,
  rejected concurrent and repeated requests, and completed generation 4 after one
  ADMIN retry. Persistence contained exactly 1 job, 4 attempts, 4 outbox rows, and
  1 result before exact cleanup.
- The worker-crash journey paused Work Service long enough for the real worker to
  claim generation 1, stopped that owning worker while the attempt remained
  `RUNNING`, waited for its persisted lease to expire, and then started recovery.
  Recovery produced exactly 1 `ABANDONED` attempt and exactly 1 generation-2 outbox
  row; the restarted worker then produced exactly 1 result.

## Failed attempts and corrections

- A heartbeat unit test exposed SQLite's inability to synchronize the timezone
  comparison used by an update expression. A locked ownership select replaced it,
  and the complete Job suite passed.
- The first Gateway run used the wrong working directory and could not locate the
  generated schema. Schema export and the complete configured suite then passed.
- Initial production build and Vitest runs were blocked by sandbox `spawn EPERM`.
  Complete unrestricted reruns passed.
- Root-level Job MyPy omitted the service-specific Celery/Kombu overrides. The
  configured Job-directory invocation passed for 14 source files.
- Initial isolated PostgreSQL runs used empty databases before migrations, so setup
  found no tables. Forward migrations were applied and all 5 Work and 15 Job cases
  passed; both run-owned databases were dropped.
- Initial `pip-audit` commands used an incompatible option and then encountered
  sandbox temporary-directory restrictions. The corrected unrestricted audit found
  `PYSEC-2026-4320`; affected `certifi` pins moved to `2026.10.19`, and all four
  lock audits passed.
- The first Phase 9 browser recovery run began while a restored service was still
  starting. Bounded health polling replaced the premature assertion; the complete
  journey then passed.
- The first real retry-through-exhaustion attempt stopped Work Service before
  dispatch, so dispatch correctly returned `SERVICE_UNAVAILABLE`. The corrected
  order dispatched before the outage. A second attempt used Compose start, which
  also restored the worker's dependencies; raw start of the exact worker container
  preserved the intended Work outage. Two later attempts reached the final repeated
  retry assertion and exposed missing safe Gateway mappings for
  `JOB_NOT_RETRYABLE` and `JOB_RETRY_CONFLICT`. Fixed application-owned messages
  and regression tests corrected that defect; the full 99-test Gateway suite and
  the complete browser journey passed.
- The earlier recovery journey synthesized an expired claim through internal Job
  Service code. The closure test now uses an actual Celery worker claim and stops
  the owning worker after claim. Its first strengthened run used the wrong Compose
  service name for the read-only persistence query; the corrected `job-db` query
  and complete journey passed.
- A corrected authentication collection initially reported two failures because
  `docker compose start keycloak` returned before the service was healthy. The
  setup boundary now uses bounded Compose health waiting with a 90-second limit;
  the complete affected collection then finished with 6 passed,
  1 intentional skip, and 0 failed.
- An initial strengthened recovery invocation skipped because its opt-in variables
  were absent. A subsequent OIDC initiation failed while the current frontend had
  incomplete runtime networking after a failed start, and callback profile lookup
  then failed while the current Gateway had no network endpoint. The retained Phase
  1 frontend occupied port 3010 and the retained Phase 1 Gateway occupied port 8010.
  Approval was given to stop only those exact older containers while leaving them
  present. Force-recreating only the current frontend and Gateway restored their
  port bindings, Compose DNS, health, and downstream connectivity. The observations
  establish incomplete Docker endpoint and network state after the failed starts;
  they do not establish a deeper Docker root cause. The complete strengthened
  recovery journey subsequently passed 1 of 1.
- Local restricted Vitest and production-build attempts were blocked by Windows
  `spawn EPERM`; identical permitted reruns passed. A host-Python Gateway MyPy
  invocation lacked the locked Gateway dependencies, and a container invocation
  encountered a MyPy 1.20.2 internal error; the configured locked environment
  passed strictly for all 8 Gateway source files.
- The first final connectivity probe guessed `/health` for services whose configured
  readiness route is `/health/ready`; the resulting 404 did not establish a service
  failure. The repeated probe used the Compose-configured routes and passed from
  frontend to Gateway and from Gateway to Employee, Work, Job, and Keycloak.

## Cleanup and retained state

The isolated `phase9_work_verify` and `phase9_job_verify` databases were created,
migrated, used only by this run, and dropped. The closure audit found one
unambiguously paired stale recovery job and project from an earlier Phase 9 run;
their exact identifiers and expected project key were supplied to service-owned
cleanup commands. Independent final counts were 0 Phase 9 jobs, 0 attempts,
0 durable results, 0 outbox rows, 0 projects, 0 tasks, 0 current-run Employee
profiles, 0 current-run Keycloak identities, and 0 Phase 9 temporary databases.
Ambiguous pre-existing null-linked idempotency records and identities were left
untouched. No volume was deleted or recreated.

The live schema reported Alembic head `20261020_05`. The migration supplies the
non-null execution generation and fence columns, nullable lease, heartbeat, and
recovery timestamps, generation-scoped outbox uniqueness, and the composite
recovery index over status, lease expiry, and identity. Fence monotonicity is
enforced by selecting the owning job row under lock and assigning the next maximum
fence; stale heartbeat and settlement paths require the matching persisted lease
token and fence. Clean zero-to-head, Phase 8 head to Phase 9 head, and repeated head
upgrade all passed against PostgreSQL 18.

Existing jobs without publication remain at generation 0; jobs with an existing
outbox row map to generation 1. Existing outbox rows and attempts map to generation
1, and each existing attempt's fence maps to its attempt number. Retry exhaustion
maps to false and manual retry count to 0. Existing result columns remain on their
owning job without reinterpretation. The existing attempt and outbox foreign keys
retain `ON DELETE CASCADE` to the job. The migration adds
`uq_job_publication_generation` across job, generation, and event type and
`ix_job_attempt_recovery` across status, lease expiry, and attempt ID; the existing
outbox claim index continues to bound retry publication selection. There is no
database check constraint that alone proves fence monotonicity: the PostgreSQL row
lock plus maximum-fence assignment and token-and-fence settlement predicates form
that barrier and are covered by concurrent PostgreSQL tests.

Pre-existing `RUNNING` attempts receive no invented lease token or lease expiry.
Because recovery selects only expired non-null leases, ambiguous running work is
retained and is not automatically retried. The isolated databases used to verify
zero-to-head and Phase 8-to-head were named `phase9_job_verify` and
`phase9_work_verify`; both were dropped, and the final temporary-database count was 0.

Final cleanup inspection reported 0 Compose one-off containers, the single expected
Compose network, 0 Playwright output paths, 0 audit environments, and 0 runtime
artifact paths in the deliverable set. Existing ignored cache directories remain
outside the deliverable set. The Playwright `test-results` directory was removed
after evidence capture. The completed acceptance run had all 15 expected containers
healthy, frontend-to-Gateway connectivity passed, and the Gateway resolved Employee
Service, Work Service, Job Service, and Keycloak over Compose DNS. The retained
Phase 1 frontend and Gateway remained present and stopped. Only the Compose-declared
loopback host bindings remained.
Those bindings were frontend 3010, Gateway 8010, Keycloak 8080, Employee PostgreSQL
5435, Work PostgreSQL 5436, Job PostgreSQL 5437, and Redis 6380; no unexpected host
port was published.

## Manual verification

Use credentials only from the ignored `.env`.

1. Open `http://localhost:3010/jobs`, choose a job, and confirm the attempt timeline
   shows attempt number, status, safe timestamps, recovery state, and retry state.
2. During an active export, refresh the detail page and confirm `RUNNING` persists
   without showing a lease token or fence.
3. For an eligible failed job, sign in as ADMIN, choose **Retry job**, cancel once,
   then confirm once. Confirm duplicate activation cannot create a second request.
4. Sign in as MEMBER or MANAGER and confirm the retry control is absent; a direct
   retry mutation must return `FORBIDDEN`.
5. Observe an expired test-owned execution recover through `ABANDONED`, a new queued
   generation, and eventual completion. Confirm the old attempt remains in history.
6. At three failed automatic attempts, confirm exhaustion is visible and no fourth
   automatic event appears. The single ADMIN retry is a separate allowance.
7. Repeat the essential detail journey at desktop, 768 px, and 390 px and confirm
   keyboard reachability and no document-level horizontal overflow.

These checks do not claim final visual quality or accessibility certification.
Subjective visual and UX redesign remains deferred to Phases 12 and 15.

## Accepted limitations

- Publication and execution are at least once; exactly-once behavior is not claimed.
- Deterministic PostgreSQL concurrency evidence is not load or performance
  certification, and the recovery process was not deployed as multiple replicas.
- There is no cross-service distributed transaction.
- The real recovery and multi-role infrastructure journeys run on desktop; the
  ordinary lifecycle covers desktop, 768 px, and 390 px.
- ADMIN retry, concurrent retry rejection, and retry exhaustion are covered at the
  service, PostgreSQL, Gateway, frontend, and real browser boundaries.
- Automatic retries are bounded. ADMIN manual retry is allowed only through the
  verified safe state transition.
- The generic missing or inactive-profile scenario remains intentionally skipped
  when its configured credentials identify the protected administrator. The
  ownership-proven disposable inactive-profile journey passed separately.
- Automated accessibility evidence is not accessibility certification.
- Subjective visual and UX redesign is deferred to Phases 12 and 15.

Phase 9 was **Accepted** by the owner on 2026-10-27. Phase 10 has not started.
