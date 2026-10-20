# Phase 8 verification — Transactional Outbox and Reliable Job Publication

Status: **Accepted**

Owner acceptance completed on **2026-10-20**.

## Verified boundary

Dispatch no longer publishes to RabbitMQ. It locks and validates a `SUBMITTED`
job and commits the `QUEUED` transition with exactly one schema-version-1
`EXECUTE_JOB` outbox event in one Job PostgreSQL transaction. Database uniqueness
on job and event type prevents duplicate publication intent.

The independent `job-publisher` polls PostgreSQL, claims bounded batches in stable
creation-time and UUID order with `FOR UPDATE SKIP LOCKED`, and commits a random
lease token before external publication. RabbitMQ receives only the job UUID in
the JSON task body; the stable outbox event UUID is message metadata. Settlement
requires the exact current token. Fixed classified failures receive capped
automatic backoff, expired claims are reclaimable, and published events cannot be
claimed or regressed.

Eligible committed intent survives RabbitMQ and publisher outages and resumes
automatically after recovery. Publication is at least once. Exactly-once delivery
is not claimed, and duplicate publication remains possible. Atomic worker claim
prevents duplicate logical execution. Publisher leases apply only to publication.

## Requirement-to-evidence matrix

| Requirement                                      | Evidence                                                                       |
| ------------------------------------------------ | ------------------------------------------------------------------------------ |
| No request-path broker operation or compensation | Dispatch unit/API tests and endpoint dependency inspection                     |
| Atomic state and one outbox event                | SQLite and PostgreSQL atomic/unique tests                                      |
| Concurrent dispatch                              | PostgreSQL barrier test: one winner and one event                              |
| Safe concurrent claims                           | PostgreSQL two-claimer barrier test proves disjoint bounded batches            |
| Lease recovery and fencing                       | Fresh/expired lease, new-token, stale-token, and exact-token tests             |
| Recoverable failures                             | Fixed connection/ambiguous classifications, future eligibility, capped backoff |
| Duplicate-delivery safety                        | Worker duplicate-claim PostgreSQL test and real worker journey                 |
| Legacy states                                    | Migration maps queued to reconciliation and execution states to published      |
| Safe owner state                                 | Gateway owned-job test; schema has no lease token                              |
| ADMIN diagnostics                                | Gateway and frontend state/filter/pagination/error tests                       |
| MEMBER/MANAGER denial                            | Direct GraphQL tests deny both before the Job Service call                     |
| Responsive lifecycle                             | Real desktop, 768 px, and 390 px journeys                                      |
| Broker recovery                                  | Serial outage proves durable dispatch and recovery without redispatch          |
| Publisher recovery                               | Serial outage proves pending intent and automatic recovery                     |

## Migration verification

Revision `20261020_04` is the head. Two uniquely named current-run PostgreSQL 18
databases were created and both were removed afterward.

- Clean zero-to-head, Phase 7 head-to-head, and repeated head upgrades passed.
- The understood partial condition—enum exists while the table does not—passed.
- `SUBMITTED` produced no event. `RUNNING`, `SUCCEEDED`, and execution `FAILED`
  mapped to `PUBLISHED`. Ambiguous `QUEUED` mapped to
  `RECONCILIATION_REQUIRED`, which the claim query excludes.
- All enum values, primary key, unique constraint, claim/job indexes, and the
  cascading job foreign key were inspected. Exact deletion left zero orphans.
- Downgrade remains explicitly destructive and unsupported.

The first live attempt created the enum and then failed by trying to recreate it
during table creation. The correction uses `create_type=False` plus
`checkfirst=True`, covering only that understood enum-only condition. The publisher
now starts after the migrated Job Service health gate.

## Exact automated results

- Job Service: **48 passed, 12 PostgreSQL-only skipped**. The skips are the opt-in
  tests in `tests/test_postgres.py`.
- Job PostgreSQL: **12 passed** in `tests/test_postgres.py`, covering Phase 6
  idempotency/persistence, Phase 7 claim/retry, atomic outbox dispatch, uniqueness,
  concurrent dispatch, disjoint claims, ordering/bounds, lease reclaim, token
  settlement, immutable publication, and definite/ambiguous retry.
- Gateway: **94 passed**.
- Employee Service: **40 passed**. An initial live-environment run failed one
  placeholder assertion; the isolated safe-placeholder rerun passed 40/40.
- Work Service: **48 passed, 5 intentional PostgreSQL-only skips**. Its accepted
  PostgreSQL suite was unchanged by Phase 8.
- Frontend: **50 passed in 11 files**.
- Ruff, formatting, and MyPy passed for all Python services. GraphQL schema export,
  frontend generation, ESLint, TypeScript, Prettier, and production build passed.
- Compose validation and application image builds passed.
- Production npm audit: **0 vulnerabilities**. Full npm audit: **12 high-severity
  development-only `braces` findings**, unchanged from accepted earlier phases.

The first `pip-audit` attempts were unavailable in the host/runtime environments.
A temporary 2.10.1 installation then used an incompatible flag combination. One
corrected invocation was initially blocked when automatic command approval could
not run at the usage limit. The later accepted every-pinned-package
`--no-deps --disable-pip` run completed for all four locks with **no known
vulnerabilities**. The temporary auditor directory was removed.

## Docker-backed results

- Primary lifecycle: **3 passed, 0 failed** across desktop, 768 px, and 390 px.
  Each showed not-requested then published state, one successful attempt/result,
  persistence after refresh, no storage token, no overflow, and exact cleanup.
- RabbitMQ/worker recovery: **1 passed, 0 failed**, one worker, zero retries.
  Dispatch succeeded while RabbitMQ was stopped, retained intent with no attempt,
  and published/executed automatically after recovery without another dispatch.
- Publisher recovery: **1 passed, 0 failed**, one worker, zero retries. Dispatch
  while the publisher was stopped retained `PENDING`; restart produced
  `PUBLISHED`, one successful attempt, and one result.
- Abandoned-lease, stale-token, ambiguous-confirmation, and multi-publisher
  invariants passed at deterministic PostgreSQL/service layers. No public lease or
  republish control exists.

## Cleanup and limitations

Final queries reported zero Phase 8 marker jobs, outbox events, projects, tasks,
and Employee profiles; zero temporary Phase 8 databases; and zero one-off Phase 8
publisher containers. The earlier recovery run created no disposable Keycloak
identity; the final diagnostics journey created and exactly removed its three
run-owned identities and profiles. Playwright runtime output was removed. All
**14** Compose services are healthy. The bootstrap confirmed the primary
administrator remains linked; one active linked ADMIN exists.
Existing accepted data and the ambiguous pre-existing identity were untouched.

Publisher health proves that the container process is running and Job PostgreSQL
is reachable; it deliberately excludes RabbitMQ. This phase has no durable
heartbeat table or multi-replica publisher deployment. Concurrency evidence is
deterministic rather than load certification. Subjective visual and UX redesign
remains deferred to Phases 12 and 15.

A worker crash after execution claim can still leave a job `RUNNING`. Phase 9
execution leases, fencing, stale-worker protection, recovery daemon, and
administrative execution retry have not started.

## Final acceptance-closure run

The final clean non-outage Phase 1-8 browser collection ran with one worker,
fresh contexts, and zero retries: **27 passed, 18 intentionally skipped, 0
failed**. Desktop ran the Employee Administration and multi-role Project and Job
journeys; those destructive shared-identity journeys intentionally skip in the
768 px and 390 px projects. The slow refresh, disposable inactive-profile,
refresh-failure, and Keycloak-outage checks intentionally skip in this collection
because each has a separate opt-in gate and serial recovery run. The applicable
foundation, authentication, project, task, and job lifecycle journeys passed at
all three viewports.

The corrected serial recovery collection finished **13 passed, 0 failed**, one
worker, and zero retries. It covered Keycloak, Gateway, Employee Service, Work
Service, Job Service, Job PostgreSQL, RabbitMQ, Celery worker, Job publisher, and
the disposable inactive-profile scenario. A first setup enabled the legacy
profile-state test with the active primary credentials, so that test correctly
reached the application instead of access denied; the run reported 13 passed and
1 failed. The corrected collection excluded that invalid credential pairing and
used the dedicated disposable inactive-profile journey, which passed. No
application assertion was weakened.

The five Work PostgreSQL tests passed against the uniquely created PostgreSQL 18
database `phase8_work_verify_20261020_7cd6a80f`. It was migrated from zero to the
Work head and dropped only after the successful run. Three earlier confirmed
unique temporary databases were also dropped after test-invocation corrections:
the image did not contain tests, the initial URL used a placeholder password, and
the next database had not yet been migrated. No existing database or volume was
recreated or removed.

The real serial multi-role journey passed after provisioning unique run-owned
MEMBER, outsider, and MANAGER identities. ADMIN opened `/jobs/publications`, saw
the current published event, exercised the `PUBLISHED` filter and bounded
pagination metadata, and received only safe diagnostic fields. The response and
page exposed no lease token, raw error, broker URL, credential, authorization
header, or internal service address. MEMBER navigation remained absent, direct
route access redirected to access denied, and direct GraphQL diagnostics were
forbidden. MANAGER direct GraphQL diagnostics were forbidden. The owning MEMBER
could still read publication state through their owned job. All test-owned jobs,
outbox rows, project data, Employee profiles, and Keycloak identities were
removed.

This journey found that the diagnostics GraphQL boundary denied MEMBER while the
page route itself still rendered its shell. The publications page now performs a
server-side ADMIN session-role check and redirects other roles. Two selector-only
test attempts then failed because `Status` also named a header link and because
the first `PUBLISHED` text was a hidden option. Semantic combobox and visible-card
selectors corrected those test defects; the complete journey then passed.

The real worker recovery journey published the same exact outbox event UUID and
job more than once through RabbitMQ while the worker was stopped. After worker
recovery, the job was `SUCCEEDED`, publication was `PUBLISHED`, and exactly one
successful attempt and one durable result existed. The PostgreSQL lease test
separately proves lease expiry, reclaim with a new token, rejection of stale-token
settlement, exact-token settlement, and published immutability. This is
at-least-once publication with idempotent logical execution, not exactly-once
delivery.

The publisher recovery journey was extended to retain a unique `PENDING` event,
stop Job PostgreSQL, and start the publisher while its database was unavailable.
The publisher could not report healthy or mark false success. After PostgreSQL and
Job Service health returned, Compose safely started the publisher; without a new
dispatch, the event became `PUBLISHED` with exactly one successful execution and
result. Recovery in this scenario uses the configured container startup/restart
policy rather than claiming an in-process database reconnection. Exact job,
outbox, and project cleanup passed.

The **12 passed** Job PostgreSQL cases jointly cover Phase 6 actor-scoped
idempotency and persistence; Phase 7 worker claim and retry persistence; atomic
outbox dispatch and the unique event constraint; concurrent dispatch; disjoint
publisher claims with stable ordering and batch bounds; fresh and expired leases;
new-token ownership; stale-token rejection and exact-token settlement; definite
and ambiguous retry scheduling; published immutability; and duplicate worker
claim. Transaction rollback is also exercised by the atomic dispatch/service
suite, while retained-state migration behavior is verified by the dedicated
PostgreSQL migration matrix described above.

After the route correction, frontend Vitest passed **50 tests in 11 files**;
ESLint, TypeScript, Prettier, and the Next.js production build passed. The Docker
frontend build also passed. All earlier final service suites, Python static
checks, schema export, GraphQL generation, Compose validation, application image
builds, four Python lock audits, and npm audits retain the exact clean results and
documented development-only findings recorded above.

Phase 8 is **Accepted**. Request-path direct publication is removed. Committed
eligible intent survives broker outage and publication resumes automatically.
Publisher leases remain publication-only. A worker crash after execution claim
can still leave `RUNNING`; Phase 9 execution leases, fencing, stale-worker
protection, recovery daemon, and administrative execution retry have not started.

Final read-only cleanup queries reported Phase 8 marker jobs **0**, outbox events
**0**, projects **0**, tasks **0**, current-run Employee profiles **0**, current-run
Keycloak identities **0**, temporary databases **0**, one-off publisher containers
**0**, Playwright output directories **0**, audit temporary environments **0**, and
runtime artifacts in the deliverable **0**. All 14 Compose containers were
healthy. Keycloak contained exactly one primary administrator and it was enabled;
the Employee profile was active with role `ADMIN`, and the two stable subject
identifiers matched. The ambiguous pre-existing identity was left untouched.
