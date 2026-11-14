# Phase 11 verification — Notifications and Reports

Status: **Complete. Acceptance verified on 2026-11-04.**

Phase 12 has not started. The responsive lifecycle passed across separately
recorded desktop, tablet, and corrected mobile runs. The credentialed desktop
multi-role and duplicate-delivery journeys passed, along with all six desktop
outage/recovery cases and the strengthened Job domain publisher rerun.
The worktree is ready for owner review and manual commit.

## Architecture and contracts

- Notification Service owns its PostgreSQL inbox and recipient-scoped notification
  records. Gateway is the only public API boundary.
- Work Service commits `TASK_ASSIGNED` intent in the task-assignment transaction.
  Unchanged and self assignments do not emit a notification event.
- Job Service commits `REPORT_SUCCEEDED` or `REPORT_FAILED` intent in the terminal
  report transaction. Intermediate retries do not emit terminal events.
- Work and Job publishers use durable RabbitMQ messages. Notification consumer
  processing is at least once; source-event and recipient uniqueness makes
  duplicate delivery idempotent. Exactly-once delivery is not claimed.
- Notification reads and mutations always use the current Employee UUID supplied
  by Gateway after profile reload. Foreign notification identifiers return the
  same concealed not-found result as missing identifiers.
- Report requests use Job Service actor-scoped idempotency. CSV artifacts are
  exposed only for a successfully completed report and use the established
  `text/csv; charset=utf-8` contract.

## Deterministic PostgreSQL evidence

All database tests used PostgreSQL 18 and uniquely named disposable databases.
Each database was dropped with an exact name after its run; no retained database
or volume was removed.

| Boundary     | Result                  | Migration evidence                                                |
| ------------ | ----------------------- | ----------------------------------------------------------------- |
| Notification | **27 passed, 0 failed** | clean zero-to-head, `20261029_01` to `20261029_02`, repeated head |
| Work         | **61 passed, 0 failed** | accepted `20261028_01` to `20261029_02`, repeated head            |
| Job          | **73 passed, 0 failed** | accepted `20261020_05` to `20261029_06`, repeated head            |

The Notification concurrency test uses two independent SQLAlchemy sessions, a
two-party synchronization barrier, and simultaneous delivery of one source-event
UUID. Both callers resolved to the same notification UUID; exactly one inbox row
and one logical notification remained. PostgreSQL schema inspection confirmed the
named recipient/source uniqueness constraint, recipient/time and unread indexes,
the source-event foreign key with `ON DELETE CASCADE`, and exact inbox and
notification enum labels.

Work PostgreSQL coverage proves disjoint bounded publisher claims, deterministic
claim ordering, fresh and expired lease behavior, random replacement tokens,
exact-token settlement, published-event non-regression, completion rollback, and
assignment rollback without task, activity, or outbox leakage. Job PostgreSQL
coverage proves fenced execution settlement, bounded recovery, generation-safe
ADMIN retry, atomic report terminal settlement, no terminal event on an
intermediate retry, one success event, and persisted artifact metadata.

Retained-row fixtures upgraded one Work project, membership, task, comment,
activity, and published outbox event from the accepted Phase 10 head. All six rows
and relationships remained, and the prior outbox row received a nullable
`recipient_employee_id` without changing its prior state. The exact UUID column
and recipient index were inspected. The Job fixture upgraded two jobs, one
successful attempt, durable result metadata, and one generation-one publication
row. All retained rows and the checksum remained unchanged. Domain-event schema
inspection confirmed the status enum, job/event uniqueness, claim and recipient
indexes, and job foreign key with `ON DELETE CASCADE`; a two-job regression proves
deleting one job removes only its owned domain event.

## Authorization matrix

- Notification list, unread count, mark-one, and mark-all operations reload the
  current Employee profile and pass only that Employee UUID to Notification
  Service. Missing and inactive profiles return `FORBIDDEN` before any downstream
  call. Foreign and missing notification UUIDs share the same concealed result.
- Notification Service outages return only `SERVICE_UNAVAILABLE` and
  `Notifications are temporarily unavailable.` Internal URLs, credentials,
  payloads, broker metadata, and exception text are absent.
- ADMIN, project-manager, and project-member report request mutations revalidate
  current project membership through Work Service before submission, denying
  non-members and removed members with `FORBIDDEN` or `PROJECT_NOT_FOUND`.
- Report and report artifact queries (`report`, `reportArtifact`, `reports`)
  forward the current active Employee profile to Job Service, which independently
  enforces requester ownership and ADMIN override: only the submitter
  (`submitter_employee_id`) and system `ADMIN` may read or download a report.
  Non-owners (including fellow project members and project managers querying
  another actor's report) receive the concealed response code `JOB_NOT_FOUND`
  with message `The job was not found.` Reports are requester-isolated rather
  than project-shared.
- Pending and failed reports return `ARTIFACT_UNAVAILABLE`; only an authorized
  successful report exposes persisted CSV content, checksum, row count, and the
  fixed content type. Idempotency conflicts and invalid cursors retain typed,
  sanitized mappings. The public schema contains no inbox, broker, lease-token,
  or domain-outbox fields.

## Consumer classification

Consumer entry-point tests cover task assignment, successful report, failed
report, duplicate delivery, and post-commit/pre-ack redelivery. Valid duplicates
acknowledge the existing logical notification. Unsupported schema, unknown event
type, malformed/non-mapping payload, missing or invalid UUID fields, inconsistent
assignment data, self-assignment, and unsupported report type are rejected
without an inbox or notification row. These cases use fixed classifications:
`INVALID_EVENT`, `UNSUPPORTED_SCHEMA`, `UNSUPPORTED_EVENT`, and
`UNSUPPORTED_REPORT`. Arbitrary event fields never enter public title or message.
Unexpected infrastructure exceptions are neither acknowledged nor permanently
rejected, preserving broker redelivery.

## Previously recorded source verification

- Notification Service combined ordinary, cleanup, and PostgreSQL collection:
  **27 passed**.
- Work Service ordinary collection: **51 passed, 10 intentional PostgreSQL-only
  skips**. Explicit PostgreSQL collection: **10 passed**.
- Job Service ordinary collection: **55 passed, 17 intentional PostgreSQL-only
  skips**, with one existing Starlette deprecation warning. Explicit PostgreSQL
  collection: **17 passed**.
- Gateway: **117 passed**.
- Frontend: **59 passed in 13 files** with one worker.
- Notification, Work, Job, and Gateway Ruff, formatting, and MyPy checks passed.
- Frontend ESLint, TypeScript, Prettier, GraphQL generation, and production build
  passed. The production build generated `/notifications`, `/reports`, and
  `/reports/[id]`.
- `docker compose config --quiet` passed.
- The affected images built successfully at an earlier verification point. Later
  read-only parity inspection found that the currently running Notification API
  and Notification consumer no longer matched current host `service.py` and
  `models.py`. The earlier build result therefore does not establish current
  runtime parity. At that point, the next acceptance run required rebuilding and
  recreating only the Notification API and Notification consumer from current
  source. That rebuild and parity verification were subsequently completed. The
  earlier mismatch was relevant but did not prove the root cause of the missing
  notification, and no runtime lifecycle pass is claimed from that run.
- Production npm audit: **0 vulnerabilities**.
- Python lock audit: all six current lockfiles (Gateway, Employee, Work, Job,
  Workflow, and Notification) reported **no known vulnerabilities** with
  `pip-audit` 2.10.0 using their fully pinned dependency sets.
- Full npm audit: **2 high development-only package findings**. `undici` has
  GHSA-4qv8-2p9j-2685, GHSA-f72v-6w45-q472, GHSA-xjj6-f33q-929c,
  GHSA-4w7w-5xrc-9h26, GHSA-2m5v-pch6-74hx, GHSA-qrxm-fqhp-jwvm,
  GHSA-9fm3-97px-rjf6, and GHSA-55wc-3pg8-jfw6 for installed affected range
  `8.0.0–8.12.1`; `zod` has GHSA-mrhx-c7xc-m3w5 for versions below `4.6.6`.
  npm reports fixes available. Neither package is in the production dependency
  audit.

## Compose evidence

All **23** services configured by `compose.yaml` are running and healthy. The
frontend received HTTP 200 from `gateway:8000`; Gateway resolved Employee, Work,
Job, Workflow, Notification, and Keycloak. Work publisher, Notification consumer,
and Job domain publisher resolved their databases and RabbitMQ. The retained
Phase 1 frontend and Gateway remain present and stopped.

## Browser acceptance specifications

The following opt-in specifications are implemented and statically discovered:

| Specification                                | Opt-in flag                              |                                                  Discovered cases |
| -------------------------------------------- | ---------------------------------------- | ----------------------------------------------------------------: |
| Responsive report and notification lifecycle | `RUN_NOTIFICATION_REPORT_E2E`            |                                       3, one per viewport project |
| Four-role authorization                      | `RUN_NOTIFICATION_REPORT_MULTI_ROLE_E2E` |                 3 discovered; tablet and mobile are guarded skips |
| Duplicate RabbitMQ delivery                  | `RUN_NOTIFICATION_REPORT_DUPLICATE_E2E`  |                 3 discovered; tablet and mobile are guarded skips |
| Serial outage and recovery                   | `RUN_NOTIFICATION_REPORT_RECOVERY_E2E`   | 18 discovered; 6 desktop cases and 12 guarded tablet/mobile skips |

All journeys use `DEV_USER_USERNAME`, `DEV_USER_PASSWORD`,
`KEYCLOAK_ADMIN_USERNAME`, and `KEYCLOAK_ADMIN_PASSWORD` so final cleanup can
revalidate the protected administrator's stable subject. The multi-role,
duplicate-delivery, and outage/recovery journeys also require `PHASE4_E2E_TEMP_PASSWORD` and `PHASE4_E2E_PASSWORD`. No
credential is embedded in source or printed by a helper.

The desktop-only duplicate and recovery specs require their respective flags
to equal `1`. Duplicate delivery publishes to the two existing notification
queues and reads their acknowledgement counters through the internal RabbitMQ
management API. It does not stop services. Recovery stops one service per case
and checks its health after starting it. The RabbitMQ case also checks the
health of its six dependent publishers, consumers, and worker. A separate
post-run Compose check verifies every configured service.

Current-run ownership uses a `P11-<base36 time>-<UUID prefix>` marker. Projects,
tasks, identity usernames and emails, report idempotency keys, Employee UUIDs,
Keycloak subjects, notification UUIDs, source-event UUIDs, and report Job UUIDs
are captured and validated before they enter discovery or cleanup. The multi-role
journey records each Employee-to-Keycloak subject link immediately and refuses
any identity whose subject matches the protected administrator.

Cleanup restores stopped services independently and waits for bounded health
before data cleanup. It discovers exact owned rows, deletes report Jobs through
Job Service's development cleanup command, deletes notification/source-event
pairs through Notification Service's new scoped cleanup command, deletes the
exact Work project through Work Service cleanup, and removes disposable Employee
and Keycloak identities only after stable-subject verification. Cleanup stages
continue after an earlier failure and aggregate fixed safe stage labels. Final
queries use exact IDs or markers; no table-wide delete, generated container name,
database removal, volume removal, or Compose down operation is present.

Notification cleanup requires an exact notification UUID, source-event UUID, and
recipient Employee UUID. It queries every notification for that source event and
requires exactly one row matching all three identifiers before deletion. It
refuses partial, multiple, inconsistent, or foreign ownership; is safe to rerun
only when both exact rows are absent; and retains unrelated rows. Migration
`20261029_02` adds `uq_notification_source_event`, enforcing one logical
notification per source event in PostgreSQL. The focused cleanup suite passed
**7 tests**, and the PostgreSQL collection passed **5 tests**.

Static verification found **27 tests in 4 browser files**. Prettier, ESLint, and
TypeScript passed. The focused notification/report component collection passed
**4 tests in 1 file** after a restricted `spawn EPERM` attempt was rerun in the
permitted environment. Playwright `--list` performed discovery only during the
static preflight.

The three responsive lifecycle cases were later executed. Gateway repeatedly
returned HTTP 200 while reading each report Job, but the captured 30-minute logs
contained no Job worker `received` or `succeeded` entry for those reports and no
observed execution publication by `job-publisher`. Later source-parity and runtime
log inspection disproved the stale-Gateway theory: host and container source had
the same dispatch logic, and runtime logs showed successful submit and dispatch
HTTP calls. A Gateway rebuild succeeded, but source parity was already present;
the rebuild neither proved nor corrected the original failure.

A deterministic Gateway regression verifies the `project`, `submit`, and
`dispatch` sequence and the resulting `QUEUED` payload; its focused run passed
**1 test with 111 deselected**, and the complete Gateway suite passed **117
tests**. No runtime lifecycle pass or deeper dispatch root cause is claimed.

Execution-publication inspection proved that dispatch commits the `QUEUED` Job,
generation one, and one immediately eligible generation-one `EXECUTE_JOB` row in
the same transaction. The row starts `PENDING`, unleased, with no publication or
failure metadata and can be claimed immediately. A forced uniqueness conflict
proved rollback retains the Job as generation-zero `SUBMITTED` with its original
version. The focused SQLite collection passed **17 tests**. The first temporary
PostgreSQL command omitted migrations and failed before either selected test ran;
the exact database was dropped. The corrected fresh PostgreSQL 18 database ran
the complete migration chain through `20261029_06`, passed the two selected
transaction tests with **17 deselected**, and was dropped in `finally`.

The two example lifecycle Job rows had already been removed by safe cleanup, so
their publication state cannot be reconstructed. Current runtime inspection found
no eligible or leased publication row: the database contained one unrelated old
`PUBLISHED` row. The running publisher process could connect to PostgreSQL and
RabbitMQ, and its process remained alive. Its health check proves PostgreSQL and
process liveness only; it has no broker or durable loop-heartbeat assertion. The
unfiltered publisher log for the inspected hour was empty, so it contained no
publisher error or positive loop evidence.

The configured `jobs` RabbitMQ vhost had a durable `job.execution` queue with one
consumer, zero ready messages, and zero unacknowledged messages. Job worker logs
showed the broker-loss error, bounded reconnection attempts, successful
reconnection, and later successful Job executions. This proves the worker
recovered after the observed RabbitMQ restart and is not currently stuck. Because
the original rows are gone and publisher logging does not expose claims, the
historical failure remains unclassified. Remaining hypotheses are a historical
publication/claim or delivery failure, an execution timing/correlation issue, or
UI freshness; the evidence does not distinguish among them.

The next lifecycle run now checks, in bounded order, exact Job generation and
state, one eligible generation-one publication intent, transition to `PUBLISHED`,
one attempt, final Job success, and UI freshness. Failures emit only fixed labels:
`MISSING_PUBLICATION_INTENT`, `INELIGIBLE_PUBLICATION_ROW`,
`PUBLISHER_CLAIM_FAILURE`, `BROKER_PUBLICATION_FAILURE`,
`WORKER_DELIVERY_FAILURE`, `EXECUTION_FAILURE`, and `UI_FRESHNESS_FAILURE`. No
credential, payload, URL, or raw exception is included. Playwright was not
executed after adding these checks.

The corrected desktop lifecycle run subsequently passed the exact Job publication
diagnostics, worker execution, final `SUCCEEDED` Job state, web-first report UI
assertion, artifact metadata and CSV content, and CSV download. It then failed
because exact report-notification discovery returned zero rather than one within
60 seconds. An earlier attempt at this point had failed while repeatedly reloading
and immediately counting the status locator; replacing that test-only
synchronization with a web-first assertion corrected the test, and the latest run
passed that boundary. Neither attempt is recorded as a complete lifecycle pass.

Post-failure inspection used the correct RabbitMQ vhost, `jobs`. It verified the
durable `notification.report.terminal` queue, one active consumer, zero ready and
unacknowledged messages, and the binding from durable exchange `job.domain` with
routing key `job.report.terminal.v1`. Job domain publisher and Notification
consumer both use the same vhost, and the active consumer connection matched the
Notification consumer. Relevant services were healthy; publisher and consumer
logs for the diagnostic window were empty. Cleanup had already removed the exact
Job, terminal event, notification, and project rows, so the event boundary cannot
be reconstructed and no RabbitMQ topology or application root cause is claimed.

Read-only SHA-256 parity inspection found exact host/container matches for Job
service, Job models, Job domain publisher, and the Notification consumer
entrypoint. The running Notification API and consumer contained older
Notification `service.py` and `models.py` than the host. The differences are the
processed-source reload and source-event uniqueness corrections already covered by
the current deterministic suite. This mismatch is relevant runtime evidence but
does not prove why the first delivery produced no notification. No service was
rebuilt, restarted, or recreated during this correction pass.

The lifecycle specification now adds a second bounded diagnostic chain after Job
success. It proves one exact immediately eligible `REPORT_SUCCEEDED` terminal
event with schema version one and matching recipient, report, and project; waits
for that event to become `PUBLISHED`; waits for the same UUID to enter the
Notification inbox and become `PROCESSED`; and proves exactly one matching
`REPORT_SUCCEEDED` notification. Fixed failure labels are
`MISSING_REPORT_EVENT_INTENT`, `INELIGIBLE_REPORT_EVENT`,
`REPORT_EVENT_PUBLISHER_CLAIM_FAILURE`,
`REPORT_EVENT_BROKER_PUBLICATION_FAILURE`, `NOTIFICATION_CONSUMER_FAILURE`, and
`NOTIFICATION_MATERIALIZATION_FAILURE`. The captured event UUID is retained for
exact cleanup verification in both databases. The helper now passes the validated
UUID to the owning test immediately after exact event discovery, before any
publication, inbox, or materialization poll can fail. The redundant notification
discovery check is immediate and uses `NOTIFICATION_DISCOVERY_FAILURE`. The test
budget is 420 seconds while every individual wait remains bounded. Playwright was
not executed after these diagnostics were added.

The Notification API and consumer were subsequently rebuilt and recreated from
current source. Before the next desktop run, both containers matched the host
`service.py` and `models.py` SHA-256 hashes, migration `20261029_02` was at head,
both durable Notification queues had one consumer and no ready or unacknowledged
messages, and the Notification API, consumer, Job domain publisher, and RabbitMQ
were healthy. That desktop run used one worker and zero retries. It passed Job
execution-publication intent and settlement, worker delivery and execution, final
Job state `SUCCEEDED`, report detail UI, artifact metadata, CSV content, and CSV
download. It then failed at `MISSING_REPORT_EVENT_INTENT`: the exact successful
report Job UUID had zero matching rows in `job_domain_outbox` at the diagnostic
point. Job domain publication, RabbitMQ delivery, Notification inbox processing,
and Notification materialization were therefore not reached. Cleanup ran, so no
retrospective row claim is made, and this run is not a browser lifecycle pass.

Read-only Job source parity identified the cause of that missing intent. The Job
API and Job domain publisher matched current host source for `main.py`,
`service.py`, `models.py`, `tasks.py`, `schemas.py`, and
`domain_event_publisher.py`. The running Job worker matched current `tasks.py` and
`schemas.py`, but had older `main.py`, `service.py`, and `models.py`; its image did
not contain `domain_event_publisher.py`. Direct fixed-marker inspection confirmed
that the worker's `service.py` contained none of `_add_terminal_event`,
`REPORT_SUCCEEDED`, or `JobDomainEvent`. The current `tasks.py` imports
`settle_success` directly from that stale module, so its successful runtime
settlement committed the Job and artifact without creating the terminal event.
This source mismatch proves the observed boundary failure and does not identify a
RabbitMQ or Notification defect.

Only `job-worker` requires a current-source rebuild and recreation before the next
desktop lifecycle run. The matching Job API and Job domain publisher do not
require recreation for this correction.

The worker does not use an internal HTTP claim or settlement endpoint. Its Celery
task opens Job database sessions and calls `claim_job` and `settle_success`
directly. No endpoint was added merely for testing. A new regression exercises
that actual Celery task boundary twice and proves one attempt, one successful Job,
the complete CSV artifact, and one immediately eligible `REPORT_SUCCEEDED` event
with exact Job, recipient, and project ownership, schema version one, `PENDING`
state, zero attempts, and no lease, publication, or failure metadata. The focused
Job API, execution, and domain-event collection passed **25 tests**.

A fresh uniquely named PostgreSQL 18 database was proven absent, migrated through
`20261029_06`, and used for the complete Job PostgreSQL collection. All **20
tests** passed. The added uniqueness-failure regression forces two terminal rows
for the same Job and event type, observes the PostgreSQL constraint failure, and
proves that Job success, attempt success, artifact metadata, completion time, and
the terminal event all roll back. Existing PostgreSQL cases also prove no event
for an intermediate retry, stale fencing cannot change the successful generation
or create another event, and the terminal event remains unique. The exact
temporary database was dropped and independently returned a final count of zero;
the exact copied temporary test file was removed from the Job container.

After the current Job worker was restored, the responsive lifecycle passed on
desktop and tablet in separate runs with one worker and zero retries. The first
mobile run passed Job
publication, worker execution, final `SUCCEEDED` state, terminal report-event
creation and publication, Notification inbox processing and exact materialization,
report UI, CSV artifact and download, notification visibility, mark-read, and
read-state persistence after reload. It then failed only the final document-width
assertion on `/notifications`.

Source inspection proved that the mobile application header exceeded its available
width. At 390 px, its 20 px horizontal padding on each side leaves 350 px, while
the nonwrapping navigation/title group plus the Gateway status, Notifications, and
user controls require more than that width. The full visible `Gateway connected`
label was the removable mobile-only width; the link already has an application-owned
accessible label and status indicator. The correction keeps the status dot and link
visible, makes the dynamic status text visually hidden below `sm` while retaining it
for assistive technology, makes the title group shrinkable, and truncates only the
page title when necessary. Notification page
headers and cards now stack below `sm`, their content column uses `min-w-0`, long
title/message content wraps, and action and pagination groups wrap. These changes
reduce intrinsic width while keeping content and controls reachable; they do not
clip or globally hide overflow.

The lifecycle width assertion still fails on real overflow and now reports the
fixed label `MOBILE_HORIZONTAL_OVERFLOW`, document widths, and at most eight
structural candidates. Candidate diagnostics contain only element tags, safe role
or test identifiers, bounded non-sensitive class names, and rounded rectangle
values. They never include notification text, identity data, UUIDs, URLs,
credentials, storage, raw HTML, or arbitrary text content. The corrected focused
mobile rerun passed in **48.1 seconds** with one worker and zero retries. The
desktop, tablet, and corrected mobile results establish the three configured
viewport lifecycle passes across explicitly separate runs; they were not one
combined Playwright invocation.

Focused notification/report component tests passed **4 tests**, and focused
Gateway-status component tests passed **4 tests**. The complete frontend
unit/component collection was executed one file at a time with one worker and
passed **59 tests in 13 files**. The notification coverage preserves actions and
behavior while asserting the mobile/desktop responsive class contract,
shrinkable content column, wrapped unbounded placeholder content, and reachable
actions. ESLint, TypeScript, and Prettier passed. The Next.js `16.4.3` production
build compiled successfully, completed its TypeScript and page-data stages, and
generated fresh production manifests. Playwright discovery found the existing
desktop, tablet, and mobile lifecycle cases. No opt-in journey was executed during
the later static verification pass.

The current frontend image built successfully, was recreated, and became healthy.
The frontend resolved Gateway. An exploratory `GET /health` returned HTTP 404
because Gateway does not expose that route; this was a diagnostic-command error,
not an application or Compose defect. The corrected frontend-to-Gateway GraphQL
`SystemInfo` request returned HTTP 200 with status `AVAILABLE`.

Exact identifier-based lifecycle cleanup is the primary cleanup proof. The final
inspection returned zero `P11-` Work projects, zero Notifications globally, and
zero Notification source events globally. It also found zero report Jobs and zero
Job domain events created during the final ten-minute inspection window; those
two time-bounded checks are not global counts. All 23 current Compose services
were healthy, no Compose one-off containers remained, and the retained Phase 1
frontend and Gateway containers remained present and stopped. A broad diagnostic
query referenced nonexistent `notifications.received_at`; it is recorded only as
a diagnostic-command error and provides no cleanup evidence.

The next desktop lifecycle rerun must load its required credentials explicitly
from the ignored repository `.env`; `npx` does not load that file automatically.
This wrapper reads and exports the values without printing them, rejects missing
values before Playwright starts, restores the repository directory, and removes
every exported variable:

```powershell
$repositoryDirectory = (Get-Location).Path
$requiredNames = @(
  "DEV_USER_USERNAME",
  "DEV_USER_PASSWORD",
  "KEYCLOAK_ADMIN_USERNAME",
  "KEYCLOAK_ADMIN_PASSWORD"
)
$environmentValues = @{}

Get-Content -LiteralPath (Join-Path $repositoryDirectory ".env") | ForEach-Object {
  $line = $_.Trim()
  if (-not $line -or $line.StartsWith("#")) {
    return
  }

  $separator = $line.IndexOf("=")
  if ($separator -lt 1) {
    return
  }

  $name = $line.Substring(0, $separator).Trim()
  if ($requiredNames -notcontains $name) {
    return
  }

  $value = $line.Substring($separator + 1).Trim()
  if (
    $value.Length -ge 2 -and
    (($value.StartsWith('"') -and $value.EndsWith('"')) -or
      ($value.StartsWith("'") -and $value.EndsWith("'")))
  ) {
    $value = $value.Substring(1, $value.Length - 2)
  }
  $environmentValues[$name] = $value
}

foreach ($name in $requiredNames) {
  if (-not $environmentValues.ContainsKey($name) -or
    [string]::IsNullOrWhiteSpace($environmentValues[$name])) {
    throw "Required development credential variable is absent: $name"
  }
}

try {
  [Environment]::SetEnvironmentVariable(
    "RUN_NOTIFICATION_REPORT_E2E",
    "1",
    "Process"
  )
  foreach ($name in $requiredNames) {
    [Environment]::SetEnvironmentVariable(
      $name,
      $environmentValues[$name],
      "Process"
    )
  }

  Set-Location -LiteralPath (Join-Path $repositoryDirectory "frontend")
  npx playwright test tests/e2e/notification-report-lifecycle.spec.ts `
    --project=desktop `
    --workers=1 `
    --retries=0
  if ($LASTEXITCODE -ne 0) {
    throw "Playwright lifecycle run failed with exit code $LASTEXITCODE."
  }
}
finally {
  Set-Location -LiteralPath $repositoryDirectory
  [Environment]::SetEnvironmentVariable(
    "RUN_NOTIFICATION_REPORT_E2E",
    $null,
    "Process"
  )
  foreach ($name in $requiredNames) {
    [Environment]::SetEnvironmentVariable($name, $null, "Process")
  }
}
```

Focused deterministic verification passed **3 Job domain-event tests** and **15
Notification consumer/service tests**. These tests prove exact terminal-event
ownership mapping, fixed exchange and routing-key publication, publisher
settlement, inbox processing, and exact notification ownership mapping. They did
not reproduce a materialization defect in current source.

All 23 services remained healthy during these attempts. Cleanup removed the three
owned `P11-` projects, and an independent exact project query returned zero. No
Compose one-off containers remained. A separate Job cleanup SQL probe was invalid
because it referenced the Work `projects` table from the Job database. That probe
is recorded only as a diagnostic-command error and provides no Job cleanup
evidence.

## Failures and corrections

1. The first combined image build encountered a transient package-index lookup
   failure for Ruff. The unchanged Notification build succeeded on retry.
2. Initial Work, Job, and Gateway test commands used stale images that did not
   contain tests. They are not counted; current source was mounted for the final
   runs.
3. A new Gateway test expected a UUID while the established fixture uses employee
   identifier `actor`. The test assertion was corrected; Gateway then passed 104
   tests.
4. Two Notification cascade attempts used an expired ORM object after PostgreSQL
   had correctly deleted its row. The test retained the UUID before deletion;
   the fresh run passed all eight tests.
5. The first Work assignment rollback test referenced a nonexistent activity
   attribute. It was corrected to the typed `ASSIGNMENT_CHANGED` activity; the
   fresh PostgreSQL run passed all ten tests.
6. Restricted frontend process spawning produced `spawn EPERM`. The unrestricted
   one-worker suite and production build passed and are the recorded results.
7. The expanded artifact tests found that `ARTIFACT_UNAVAILABLE` was omitted from
   the safe GraphQL allowlist, producing a generic error. The fixed
   application-owned code was added; the full Gateway rerun passed 116 tests.
8. The first Job retained-row fixture command was split at the semicolon inside a
   content-type literal. No fixture row was inserted and no retained-data pass was
   claimed. The exact database was removed; a fresh shell-safe fixture preserved
   two jobs, one attempt, one publication, and result metadata through the upgrade.
9. The first focused component invocation was blocked by restricted Windows
   process spawning with `spawn EPERM`. The same one-worker command passed four
   tests with the required process permission; the blocked attempt is not counted
   as a test result.
10. The first retained-row migration command for the new Notification uniqueness
    constraint had an incorrectly quoted inline Python fixture and failed before
    inserting a row. Its exact temporary database was dropped, and no migration
    result was claimed. The corrected `20261029_01` to `20261029_02` run and
    repeated-head check passed in a fresh temporary database.
11. The first complete Notification rerun after adding source-event uniqueness
    produced **26 passed, 1 failed**: one concurrent duplicate-delivery caller
    observed the already-processed source but returned no notification. The
    processed-source path now reloads the unique notification. The fresh complete
    PostgreSQL-backed rerun passed **27 tests**.
12. The final focused component rerun again encountered restricted process
    spawning. An escalated attempt could not be reviewed, the Vite runner loader
    was incompatible with a CommonJS dependency, and the native loader with the
    default fork pool received `spawn EPERM`; none is counted as a test pass. The
    native loader with one worker-thread pool executed the same focused file and
    passed **4 tests**.
13. The three responsive lifecycle cases repeatedly read their report Jobs through
    Gateway with HTTP 200, but did not observe worker receipt, worker success, or
    job-publisher execution publication within the captured 30-minute logs. The
    current source already dispatches newly submitted report Jobs, and the added
    deterministic dispatch regression plus the full **117-test** Gateway suite
    passed. The runtime evidence remains unresolved and is not counted as a
    lifecycle pass or a proven application defect.
14. A Job cleanup SQL probe incorrectly referenced the Work-owned `projects` table
    from the Job database. It is a diagnostic-command error only. No cleanup claim
    is derived from it; the independently verified cleanup evidence is limited to
    zero owned `P11-` Work projects and zero Compose one-off containers.
15. Rebuilding Gateway was a diagnostic action only. The build succeeded, but the
    running and host source already contained identical report submit-and-dispatch
    logic, and runtime logs already showed both HTTP calls succeeding. The rebuild
    did not establish or correct the original failure.
16. The first focused PostgreSQL publication-boundary command created an empty
    temporary database without applying migrations. Both selected tests failed in
    fixture setup on missing tables, no behavior result was claimed, and the
    database was dropped. The corrected run applied every Job migration through
    `20261029_06`, passed **2 tests with 17 deselected**, and dropped its database.
17. The first corrected desktop lifecycle attempt used immediate locator counts
    after repeated reloads and failed despite the Job succeeding. A web-first
    assertion corrected that test synchronization. The next desktop run passed
    Job execution, UI state, artifact verification, and download, then found zero
    exact report notifications within 60 seconds. Cleanup ran before retrospective
    inspection, so no event-boundary or product defect is inferred from that run.
18. Read-only parity inspection found current Job source in its API and publisher
    containers, but older Notification service and model modules in both the
    Notification API and consumer images. Current deterministic tests pass the
    corrected processed-source and unique-source behavior. The mismatch is
    recorded without rebuilding, restarting, or claiming it caused the missing
    first notification.
19. After the Notification API and consumer were rebuilt and current-source parity
    was established, the next desktop lifecycle passed Job execution, UI,
    artifact, and download boundaries but failed at
    `MISSING_REPORT_EVENT_INTENT`. The exact successful Job had no terminal event
    intent at observation time; downstream publication and Notification paths were
    not reached, and no lifecycle pass is claimed.
20. Expanded Job parity inspection found stale `service.py` and `models.py` in the
    running Job worker. Its settlement module lacked terminal-event creation while
    the Job API and domain publisher matched current source. The deterministic
    current-source worker-boundary and PostgreSQL tests passed, so no production
    source correction or migration was made.
21. The first host focused-test command used the default PostgreSQL URL and failed
    during collection because host Python lacked `psycopg`. The explicit SQLite
    focused collection then passed **25 tests**. This import failure is not counted
    as a behavioral result.
22. The normal Job container user could not remove the root-owned temporary test
    copy after the PostgreSQL run. The exact file was then removed as root and its
    absence verified. The exact temporary database had already been dropped and
    independently returned a final count of zero.
23. After current Job worker restoration, desktop and tablet responsive lifecycle
    cases passed. Mobile completed every functional, persistence, artifact, and
    notification boundary but failed the final horizontal-overflow assertion. The
    source-level header width defect was corrected without clipping content. The
    corrected focused mobile rerun then passed in 48.1 seconds with one worker and
    zero retries. This completes the viewport evidence across separate runs, not
    a single combined invocation.
24. One broad cleanup diagnostic referenced nonexistent
    `notifications.received_at`. It is a diagnostic-command error only. Cleanup
    evidence comes from the independent exact project, Job, terminal-event, and
    Notification source-event zero counts.
25. The first focused Vitest command used the removed `--minWorkers` option and
    stopped before running tests. The supported command was then blocked by the
    restricted process environment with `spawn EPERM`. Unrestricted one-worker
    focused runs passed four notification/report tests and four status tests. A
    combined full-suite invocation returned no final summary and is not counted;
    the deterministic per-file run passed all **59 tests in 13 files**.
26. The first production-build invocation continued beyond the tool's output
    window, and an immediate second invocation correctly refused the active build
    lock. The first waited capture wrapper also incorrectly reused one file for
    both output streams and did not start a build. After the lock cleared, the
    corrected waited build completed and generated fresh `BUILD_ID`, prerender,
    and route manifests. The overlapping and invalid invocations are not counted
    as build results.
27. Earlier Playwright commands launched from the repository root used the wrong
    configuration boundary. They are command errors and are not test results; the
    recorded lifecycle results use the frontend Playwright configuration.
28. A connectivity diagnostic incorrectly requested the absent Gateway
    `/health` route and received HTTP 404. The corrected frontend-to-Gateway
    GraphQL `SystemInfo` request returned HTTP 200 and `AVAILABLE`; the 404 is not
    an application or Compose defect.
29. The first desktop four-role runtime attempt used a 300-second test timeout and
    exceeded it, completing after approximately 5.8 minutes with one worker and
    zero retries. Playwright reported the labeled `restore administrator session`
    cleanup stage as failed, although the final snapshot showed the protected
    administrator authenticated on the overview page. Independent read-only
    checks found zero `P11-` Work projects, zero report Jobs and Job domain events
    in the inspected recent window, zero Notifications, and zero Notification
    source events; all 23 Compose services remained healthy. The supplied checks
    did not independently establish both Employee and Keycloak disposable-identity
    zero counts, so no identity-cleanup claim is added. This attempt establishes
    neither an application defect nor a four-role pass.

30. The stale Work event publisher image mismatch was real and was corrected
    through container rebuild, recreation, semantic-token verification, exact source
    parity, DNS, queue, and health checks. The subsequent desktop four-role run
    emitted `ADMIN_SETUP_COMPLETE` and `CLEANUP_COMPLETE`, but failed while waiting
    for the member notification. Source inspection proved the test created the task
    with `assigneeEmployeeId: member.employeeId` in `CreateTaskInput`, which bypasses
    the explicit `assignTask` transaction that owns Phase 11 `TASK_ASSIGNED` event
    creation. This is a test synchronization and contract defect, not an
    application defect, and no four-role pass is claimed.
31. The corrected multi-role assignment transaction and diagnostic pipeline ran on
    desktop. `ADMIN_SETUP_COMPLETE` was emitted. Unassigned task creation followed
    by explicit ADMIN `assignTask` completed successfully. The assignment event
    (`TASK_ASSIGNED`) was published, consumed by Notification Service, processed in
    the inbox, and materialized for the member without failure. The project manager
    authenticated, requested a report via `requestProjectTaskReport`, and successfully
    queried the report (`MANAGER_BOUNDARY_COMPLETE` was emitted). Next, the
    disposable project member authenticated and queried the manager-owned report
    (`report(id: $id)`). Public GraphQL returned error code `JOB_NOT_FOUND` and message
    `The job was not found.`, failing the test assertion at line 471 (`expect(result.errors).toBeUndefined()`).
    `CLEANUP_COMPLETE` was emitted. Source and architecture inspection proved this was
    a test expectation defect, not an application defect: under the accepted Job
    Security contract (Phases 6–10 and `docs/architecture.md`), jobs and reports are
    strictly submitter-owned with ADMIN override (`actor.application_role == "ADMIN" or
    job.submitter_employee_id == actor.employee_id`). Reports are not project-wide;
    project membership allows requesting reports, but non-owners receive concealed
    `JOB_NOT_FOUND`. The multi-role test was corrected so the member asserts concealed
    `JOB_NOT_FOUND` on the manager's report and artifact, requests and reads their own
    owned report, and reads their private notifications; outsider and removed-manager
    boundaries verify concealment across foreign reports and denial on new report requests;
    and cleanup discovers, validates, and removes both manager-owned and member-owned
    reports. No four-role pass is claimed. Phase 11 remains Implementation in progress;
    Phase 12 remains unstarted.
32. The corrected multi-role report-authorization boundary ran on desktop with valid
    environment variables (`MULTI_ROLE_ENV_READY`). All five preceding milestones passed:
    `ADMIN_SETUP_COMPLETE`, `MANAGER_BOUNDARY_COMPLETE`, `MEMBER_BOUNDARY_COMPLETE`,
    `NON_MEMBER_BOUNDARY_COMPLETE`, and `REMOVED_MANAGER_BOUNDARY_COMPLETE`. After ADMIN
    invoked `setEmployeeActive(employeeId, active: false)` for the disposable outsider,
    the test logged out and attempted to sign in with the outsider's replacement password,
    expecting a navigation to `/access-denied` within five seconds. The browser remained
    on Keycloak's login endpoint and did not reach `/access-denied`, failing the expectation.
    `INACTIVE_PROFILE_BOUNDARY_COMPLETE` was not emitted. `CLEANUP_COMPLETE` was emitted.
    Investigation of the Employee Service architecture, `admin_service.py`, `keycloak_admin.py`,
    and accepted Phase 3 identity tests (`employee-administration.spec.ts`) proved that
    `setEmployeeActive(active: false)` synchronously disables the user in Keycloak
    (`keycloak.set_enabled(subject, False)`). When a disabled identity attempts login at Keycloak,
    Keycloak halts authentication and re-renders the login form with a disabled-account error;
    no authorization code or tokens are ever issued, and the browser never reaches the
    application callback. The application's `/access-denied` route is intended solely for
    valid Keycloak identities whose Employee profile is unlinked or inactive in PostgreSQL
    (as tested by `app.development_access set-active` in `inactive-profile.spec.ts`).
    Therefore, this failure was a test expectation defect, not an application defect.
    The first edit replaced the redirect assertion, but its visibility selector
    could match the login form alone. That edit had no credentialed pass.

33. On 2026-11-04 the credentialed desktop rerun passed **1 test** in 3.8 minutes.
    The repository-root credential-safe wrapper loaded the ignored development
    credentials and ran the following from `frontend` with one worker and zero
    retries:

    ```powershell
    npx playwright test tests/e2e/notification-report-multi-role.spec.ts --project=desktop --workers=1 --retries=0
    ```

    The run emitted `ADMIN_SETUP_COMPLETE`, `MANAGER_BOUNDARY_COMPLETE`,
    `MEMBER_BOUNDARY_COMPLETE`, `NON_MEMBER_BOUNDARY_COMPLETE`,
    `REMOVED_MANAGER_BOUNDARY_COMPLETE`, `INACTIVE_PROFILE_BOUNDARY_COMPLETE`,
    and `CLEANUP_COMPLETE`. The inactive-identity milestone confirms the exact
    Employee and Keycloak state, visible Keycloak rejection, HTTP 401
    unauthenticated session response, and absence of the application session
    cookie. Cleanup verified zero rows for the scoped Work, Job, and
    Notification resources and the three disposable identities in Employee and
    Keycloak. The primary administrator was restored to the original Employee
    UUID and ADMIN role, with its original enabled Keycloak subject and active
    Employee profile verified after cleanup. Focused ESLint and frontend
    typecheck passed, as did 18 focused Vitest tests across auth,
    notification/report, and system. No services were rebuilt or recreated.

34. On 2026-11-04 the credentialed duplicate-delivery run passed **1 desktop
    test** in 2.5 minutes with one worker and zero retries. The repository-root
    credential-safe wrapper loaded the six required development variables, set
    `RUN_NOTIFICATION_REPORT_DUPLICATE_E2E=1`. The command ran from `frontend`.

    ```powershell
    npx playwright test tests/e2e/notification-report-duplicate-delivery.spec.ts --project=desktop --workers=1 --retries=0
    ```

    The test replayed the exact assignment and terminal-report payloads twice
    each using RabbitMQ publisher confirms. Each target queue's acknowledgement
    count advanced by at least two before the test checked that each source
    event still had one inbox row and one notification. The report retained one
    Job, one successful attempt, and one CSV artifact. The run emitted
    `DUPLICATE_DELIVERY_COMPLETE` and `DUPLICATE_CLEANUP_COMPLETE`. Cleanup
    verified zero owned Work, Job, and Notification rows, removed the exact
    disposable identity from Employee and Keycloak, and revalidated the
    protected administrator's original enabled Keycloak subject and active
    Employee profile. No service was interrupted.

35. On 2026-11-04 the approved credentialed outage/recovery suite passed all
    **6 desktop cases** in 14.6 minutes. The repository-root wrapper set
    `RUN_NOTIFICATION_REPORT_RECOVERY_E2E=1` and ran the following command from
    `frontend` with one worker and zero retries.

    ```powershell
    npx playwright test tests/e2e/notification-report-recovery.spec.ts --project=desktop --workers=1 --retries=0
    ```

    | Interrupted service | Recovered application evidence |
    | --- | --- |
    | RabbitMQ | A committed assignment and accepted report recovered to one assignment notification and one report notification. The report succeeded, and the broker and its six dependent services reached healthy state. |
    | Work event publisher | Assignment intent persisted while publication was paused. One assignment notification materialized after restart. |
    | Notification consumer | Assignment intent persisted and no assignment notification appeared during the outage. One appeared after the consumer restarted. |
    | Notification API | GraphQL returned the sanitized `SERVICE_UNAVAILABLE` response, the consumer persisted the assignment notification during the outage, and the disposable recipient could read it after the API restarted. |
    | Job domain publisher | The report request was accepted during the publisher outage, the report succeeded, and one report notification appeared after restart. The original run did not require the terminal outbox row to be pending before restart. |
    | Job worker | The report was submitted or queued during the worker outage, succeeded after restart, and produced one report notification. |

    Each case emitted its outcome and scoped-cleanup completion labels. Cleanup
    verified the applicable exact Work, Job, Notification, Employee, and Keycloak
    removals and revalidated the primary administrator's original enabled
    Keycloak subject and active Employee profile. The wrapper's final Compose
    status read failed after Playwright had returned six passes. A separate
    Compose query then confirmed **23 of 23 services running and healthy**.
    The independent query required no fallback start or rebuild.

36. The owner approved one targeted Job domain publisher rerun on 2026-11-04.
    The same credentialed desktop recovery command with
    `--grep 'job-domain-publisher outage'` passed **1 test** in 1.1 minutes.
    With the publisher stopped, the exact report reached `SUCCEEDED` with
    one pending `REPORT_SUCCEEDED` outbox event and zero matching
    notifications. After the publisher restarted, exactly one notification
    appeared. The run emitted its pending-intent, outcome, and scoped-cleanup
    completion labels. Independent postflight verification again confirmed
    the publisher and all **23 of 23 Compose services running and healthy**.

## Browser specification safety corrections

- Duplicate-delivery and every recovery case that expects `TASK_ASSIGNED` now
  provision a unique disposable member, immediately record its username, email,
  Employee UUID, Keycloak subject, and stable profile link, add it to the owned
  project, and assign the task from the administrator to that different member.
  Self-assignment is not used as positive notification evidence.
- Disposable identity deletion maintains a current `ownershipVerified` flag.
  Profile and Keycloak deletion run only after exact username, email, Employee
  UUID, subject, and profile-link revalidation. Failed verification records a
  cleanup failure and suppresses both deletions. Final checks query Employee and
  Keycloak independently, then revalidate the primary administrator in both
  systems against its original subject.
- Notification and Job discovery now occur inside labeled cleanup stages. Known
  report UUIDs remain only as ownership-validated fallbacks. Work cleanup,
  identity cleanup, exact zero counts, administrator verification, and service
  health still run if discovery fails.
- RabbitMQ recovery waits for Work event publisher, Notification consumer, Job
  publisher, Job domain publisher, Job worker, and Workflow consumer in both the
  normal recovery path and independent `finally` stages. The journey still
  requires the owned notification and report outcome; health alone is insufficient.
- The responsive lifecycle no longer replaces browser `crypto.randomUUID`. It
  discovers exactly one report by current-run project UUID, requester UUID,
  report type, and a bounded five-minute creation window, then validates the
  exact report UUID before cleanup.
- Static four-role preflight confirms a desktop-only destructive guard and three
  guarded tablet/mobile skips; protected primary ADMIN, disposable manager,
  disposable member, and disposable non-member boundaries; unique run-owned
  usernames, emails, Employee UUIDs, and Keycloak subjects; manager report
  lifecycle permissions; ADMIN override; member read-only access; non-member
  concealment; and removed-manager reauthentication and denial. Positive
  assignment notification evidence targets the disposable member rather than
  self-assignment.
- The four-role specification now asserts empty local and session storage for
  authenticated roles. Cleanup discovers both the exact assignment notification
  and any exact manager report notification, deletes a report Job only after its
  project, submitter, type, and UUID ownership query succeeds, retains the known
  Job UUID for final zero-count verification, continues through labeled stages,
  verifies each disposable identity before deletion, and revalidates the
  protected administrator's original subject afterward.
- The first four-role runtime attempt exposed a test cleanup defect: restoration
  always started a new interactive sign-in even when the protected administrator
  was already authenticated. The corrected helper first queries the public `me`
  boundary. If that profile is the captured administrator Employee UUID with role
  `ADMIN`, it preserves the valid session. Otherwise it invokes the supported
  CSRF-protected logout endpoint when a server session exists, follows the
  returned identity-provider end-session URL, clears browser cookies, signs in as
  the administrator, and rechecks the same public Employee UUID and role. It then
  independently verifies that the protected Keycloak subject still matches the
  originally captured subject. Diagnostics are fixed labels only.
- The four-role budget is now a bounded **480 seconds**. The first attempt took
  approximately 5.8 minutes, and the larger budget covers the serial role
  boundaries plus the complete in-test `finally` cleanup without weakening any
  individual bounded wait or adding sleeps.
- The four-role specification now creates the disposable project task unassigned
  without `assigneeEmployeeId`, asserts that the initial assignee is null,
  explicitly validates GraphQL errors, and executes a separate ADMIN `assignTask`
  mutation using the task's returned optimistic version as `expectedVersion`. It
  verifies the returned task ID, assignee Employee UUID, and incremented version,
  then diagnoses the assignment pipeline in bounded order before waiting on
  notification materialization. The diagnostic chain uses fixed labels
  `MISSING_ASSIGNMENT_EVENT_INTENT`, `INVALID_ASSIGNMENT_EVENT_OWNERSHIP`,
  `INELIGIBLE_ASSIGNMENT_EVENT`, `ASSIGNMENT_EVENT_PUBLISHER_CLAIM_FAILURE`,
  `ASSIGNMENT_EVENT_BROKER_PUBLICATION_FAILURE`,
  `ASSIGNMENT_NOTIFICATION_CONSUMER_FAILURE`, and
  `ASSIGNMENT_NOTIFICATION_MATERIALIZATION_FAILURE`. The validated Work event
  UUID is captured immediately upon discovery, retained for `finally`, and
  verified in exact zero-count cleanup for both Work outbox and Notification
  source events.
- The four-role specification respects the submitter-owned report security
  contract. The member asserts concealed `JOB_NOT_FOUND` when attempting to read
  the manager's report and report artifact, requests and verifies their own
  member-owned report, and verifies their private assignment notification. Outsider
  and removed-manager boundaries assert concealment on all foreign reports and
  denial when requesting new project reports. The cleanup sequence discovers,
  validates ownership of, and removes both manager-owned and member-owned report
  jobs.
- The inactive-identity check requires one matching Employee row with the
  captured UUID, username, email, Keycloak subject, and inactive state. It also
  requires one exact Keycloak username with the captured subject and email and
  with `enabled = false`. After submitting the disposable identity's working
  replacement password, the test requires the visible disabled-account rejection
  on the exact public issuer origin configured in the running frontend and under
  that realm's login-action path. The application session endpoint must return
  HTTP 401 with `authenticated: false`, and the browser must have no application
  session cookie. Rejection diagnostics use fixed labels.

## Acceptance change-set review

The final review included modified tracked files and the untracked Phase 11
implementation, migrations, verification record, and tests. The scan found
no local secret-value matches or high-confidence credential signatures in the
candidate files. The GraphQL client outputs matched a fresh in-memory generation
from the exported schema, and Gateway's schema export test matched the runtime
schema. Test results, local environment files, dependency directories, and build
output were outside the candidate change set. The authorization checks covered
active-profile enforcement, notification recipient scope, report submitter
ownership with ADMIN override, and current project access at report request.

The acceptance rerun passed frontend ESLint, TypeScript, Prettier, and all
**59 frontend tests in 13 files**. Gateway passed **117 tests**. Ordinary
service runs passed **22 Notification**, **51 Work**, and **57 Job** tests.
Their PostgreSQL-only skips were excluded from those pass counts. The separate
PostgreSQL collections passed **5 Notification**, **10 Work**, and **20 Job**
tests in isolated databases after applying migrations to head. Each database
removal was verified by exact name. An initial Notification PostgreSQL attempt
overlapped the approved Notification API outage and produced no test result.
Its database was removed before the successful rerun. Ruff lint and format
checks and MyPy passed for Gateway, Notification,
Work, and Job. A single Gateway test signature needed formatting; its behavior
was unchanged. Compose configuration validation passed. Live migration heads
were Notification `20261029_02`, Work `20261029_02`, and Job `20261029_06`.
The live Work recipient column had UUID type, and the new Notification
source-event and Job terminal-event uniqueness constraints were present.

The local default Turbopack production build failed in its CSS worker both in
and outside the sandbox. The worker exited before Turbopack could connect.
`npm run build -- --webpack` passed compilation, TypeScript, page generation,
and production tracing, and included `/notifications`, `/reports`, and
`/reports/[id]`. The build fallback required no source or configuration change.

## Acceptance boundary and limitations

- Desktop, tablet, and corrected mobile responsive lifecycle cases passed across
  separately recorded runs with one worker and zero retries. The credentialed
  desktop multi-role and duplicate-delivery journeys also passed.
  All six desktop outage/recovery cases and the strengthened Job domain
  publisher assertion passed. The lifecycle and four-role evidence was carried
  forward from the recorded runs.
- Delivery is at least once; exactly once and distributed transactions are not
  claimed.
- Reports currently use the existing project-task CSV export job type.
- Subjective visual and UX refinement remains deferred to Phases 12 and 15.
