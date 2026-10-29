# Phase 10 verification — Workflow Automation

Status: **Accepted**

Owner acceptance completed on 2026-10-29. The complete executed evidence,
failed-attempt history, corrections, cleanup evidence, and residual limitations
remain recorded below.

Phase 11 has not started. This report records only checks that were executed; it
does not treat a blocked or skipped command as a pass.

## Event contract and guarantees

Work Service emits this committed version 1 contract only when a task enters
`DONE`:

| Field             | Meaning                                                        |
| ----------------- | -------------------------------------------------------------- |
| `eventId`         | Stable UUID of the Work outbox event and Workflow inbox record |
| `schemaVersion`   | Literal `1`                                                    |
| `eventType`       | Literal `TASK_COMPLETED`                                       |
| `projectId`       | Existing Work project UUID                                     |
| `taskId`          | Task that entered `DONE`                                       |
| `actorEmployeeId` | Stable Employee UUID that completed the transition             |
| `taskVersion`     | Optimistic task version after the transition                   |
| `occurredAt`      | UTC outbox creation timestamp                                  |

The Work transition and outbox insert share one PostgreSQL transaction. The Work
publisher sends persistent JSON to durable exchange `work.domain` with routing key
`work.task.completed.v1`; durable queue `workflow.task.completed` is distinct from
the Job worker queue. Workflow Service rejects malformed events and quarantines
unsupported event types or schema versions.

Processing is at least once. Source-event UUID uniqueness prevents duplicate inbox
records, `(rule_id, source_event_id)` uniqueness prevents duplicate logical
executions, and `workflow:<execution UUID>` is the deterministic Job Service
idempotency key. Duplicate publication or delivery can occur and exactly-once
delivery is not claimed.

## Service and trust boundaries

- Workflow Service owns rules, source events, executions, migrations, and its
  PostgreSQL database.
- Gateway is the only public business API. Workflow, Work, Job, database, and
  RabbitMQ endpoints remain internal to Compose.
- Gateway reloads the current Employee profile and Work project access before
  workflow operations. Workflow Service independently checks accessible and
  managed project identifiers received through the dedicated internal credential.
- The Workflow consumer uses a dedicated Job Service credential. It cannot use the
  general Gateway credential or assert an administrator role.
- Job execution reloads the current Employee profile and project access. A rule
  creator who is inactive or no longer has project access cannot authorize an
  export merely because the creator was authorized when the rule was created.

## Requirement-to-evidence matrix

| Requirement                              | Evidence                                                                                                                                                                    |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Atomic qualifying event                  | Work task regression verifies no event for `IN_PROGRESS` and one versioned event for `DONE`                                                                                 |
| Rule validation and lifecycle            | Workflow unit tests cover normalized creation, manager scope, disable, optimistic conflict, and bounded pagination                                                          |
| Duplicate delivery                       | Workflow unit test delivers one source event twice and observes one execution per enabled matching rule                                                                     |
| Disabled rule                            | The same unit test proves the disabled rule creates no execution                                                                                                            |
| Unsupported contract                     | Workflow unit test verifies quarantine and no execution                                                                                                                     |
| Deterministic Job idempotency            | Workflow unit test asserts the execution-derived key and one linked job                                                                                                     |
| GraphQL authentication and typed mapping | Gateway regressions cover unauthenticated rejection and typed rule mapping                                                                                                  |
| UI states and lifecycle                  | Frontend tests cover loading, directory, filters, empty/error retry, sanitized errors, form validation, fixed trigger/action, confirmation cancel, history, and job linkage |
| Migration upgrade                        | Live retained Work database and clean Workflow database both reached `20261028_01`                                                                                          |
| Production build                         | Relevant Work, Job, Workflow, Gateway, and frontend images built; Next.js compiled and generated all workflow routes                                                        |
| Runtime health                           | All 19 current Compose services reported healthy after migration correction                                                                                                 |

## Automated results

- Workflow Service deterministic suite: **10 passed, 3 intentional PostgreSQL-only skips, 0 failed**.
- Workflow PostgreSQL 18 contention suite: **3 passed, 0 failed** against a
  unique migrated database; the exact database was dropped afterward.
- Gateway: **101 passed, 0 failed**.
- Work Service: **51 passed, 9 intentional PostgreSQL-only skips, 0 failed**.
- Work focused publisher/task collection: **18 passed, 0 failed**.
- Work PostgreSQL 18 suite: **9 passed, 0 failed** against a unique database
  upgraded from `20261015_02` to `20261028_01`; the exact database was dropped.
- Job Service: **53 passed, 15 intentional PostgreSQL-only skips, 0 failed**.
- Frontend Vitest: **55 passed in 12 files, 0 failed** with one worker.
- Focused workflow frontend collection: **4 passed in 1 file, 0 failed**.
- Real Workflow lifecycle: **3 passed, 0 skipped, 0 failed** across desktop,
  768 px, and 390 px, serially with one worker and zero retries. Each run created
  one rule, completed one real task, observed one execution and one completed job,
  verified browser storage and overflow, then removed only its recorded rule,
  source event, execution, job, Work event, task, and project.
- Ruff: new and affected Python files passed after formatting.
- Workflow Service MyPy: passed, **9 source files checked**.
- Frontend TypeScript and ESLint: completed without diagnostics.
- GraphQL schema export and frontend code generation: completed successfully.
- `docker compose config --quiet`: passed.
- Docker builds: Work, Job, Workflow, Gateway, work-event publisher,
  workflow consumer, and frontend built successfully during Phase 10. The final
  frontend rebuild also passed after npm 11 repaired missing cross-platform
  optional-package lock entries exposed by Linux `npm ci`; it generated
  `/workflows`, `/workflows/new`, and `/workflows/[id]`. A final combined Python
  rebuild was interrupted during unusually slow dependency transfer and is not
  counted as a new pass; current-source service tests and static checks passed.
- Migration heads: Work `20261028_01`; Workflow `20261028_01`.
- Production npm audit after the security correction: **0 vulnerabilities**.
- Full npm audit after the security correction: **2 high development-only
  findings**: `undici@8.11.2` through `jsdom@30.1.2`, and `zod@4.6.5` through
  `eslint-config-next@16.4.0 > eslint-plugin-react-hooks@7.1.1` (including
  `zod-validation-error@4.0.2`). npm reports compatible dependency updates are
  available. The `undici` report comprises `GHSA-4qv8-2p9j-2685`,
  `GHSA-f72v-6w45-q472`, `GHSA-xjj6-f33q-929c`, `GHSA-4w7w-5xrc-9h26`,
  `GHSA-2m5v-pch6-74hx`, `GHSA-qrxm-fqhp-jwvm`, `GHSA-9fm3-97px-rjf6`, and
  `GHSA-55wc-3pg8-jfw6`; the `zod` report is `GHSA-mrhx-c7xc-m3w5` affecting
  versions below `4.6.6`. These packages are used by lint/test tooling rather
  than the production dependency set, whose audit is clean. Residual risk is
  limited to malicious or oversized data processed during local test and lint
  execution until the compatible tooling updates are applied.
- Final independent cleanup queries found **0 rules, 0 executions, 0 source
  events, 0 Work outbox events, 0 current-run projects, 0 current-run tasks, 0
  workflow-keyed jobs, 0 Job attempts, 0 durable Job results, 0 Job publication
  rows, 0 disposable Employee profiles, and 0 disposable Keycloak identities**.
  Temporary PostgreSQL databases and Compose one-off containers were also zero.
  The Playwright result directory was removed after its evidence was recorded.

The Work Service's nine skipped tests and Job Service's fifteen skipped tests are
the existing opt-in PostgreSQL collections when their explicit database flags are
absent from the ordinary unit command. They are not counted as passes.

## Failures and corrections

1. The first Docker build attempt failed before compilation because Docker Desktop
   could not resolve the registry CDN. The unchanged build command succeeded on
   retry.
2. Host Python collections could not import pinned service dependencies, so final
   service results were obtained from the pinned Docker images.
3. Vitest could not spawn its configuration helper in the restricted environment.
   The unrestricted one-worker run completed with exact results above.
4. The first live Work migration attempted to create `work_event_status` twice.
   The migration now explicitly creates the enum once and reuses it for the table.
5. The Work event publisher initially depended on the database and could start
   before Work migrations completed. It now waits for the healthy Work service.
   The retained database upgraded successfully without deleting data or volumes.
6. Container static checks initially attempted to write caches under the read-only
   application directory. Cache-free Ruff and `/tmp` MyPy invocations distinguish
   that environment restriction from source failures.
7. The final ESLint pass rejected synchronous state updates initiated directly
   from two mount effects. The initial loads now use a bounded zero-delay browser
   task with cleanup; ESLint, TypeScript, Prettier, and the focused component
   collection passed afterward.
8. The first Workflow PostgreSQL harness used the wrong settings variable and a
   stale image without the mounted test source. Its unique database was removed;
   the corrected mounted-source invocation migrated successfully.
9. The first real concurrent duplicate-event run exposed an unhandled inbox
   primary-key race. Workflow now durably claims the source event, reloads the
   winning record after a uniqueness conflict, and relies on the independent
   rule/event uniqueness fence. The corrected PostgreSQL run passed.
10. The first exact Workflow schema query used an ambiguous PostgreSQL
    text/`char` concatenation. Its unique database was removed, and the corrected
    cast produced the complete constraint, index, and enum definitions.
11. The first duplicate-delivery browser run stopped before duplicate publication
    because its verification SQL combined string concatenation with an
    unparenthesized PostgreSQL JSON extraction. This was a test-only operator
    precedence defect. The Work outbox schema was correct, and the Job payload
    column is PostgreSQL `jsonb`. Ownership-proven cleanup succeeded with zero
    `W10-` projects, zero Workflow rules, and zero workflow-keyed jobs remaining.
    No application defect or duplicate-delivery result is claimed from that run.
12. The corrected second duplicate-delivery run reached the real Workflow and Job
    paths and passed orchestration and deterministic uniqueness checks. It stopped
    before duplicate-delivery acceptance because the test queried durable result
    fields before the downstream Job reached `SUCCEEDED`. This was a test-ordering
    defect. Cleanup completed with zero `W10-` projects, zero Workflow rules, and
    zero workflow-keyed jobs remaining. No application pass or defect is claimed
    from this run.
13. The latest duplicate-delivery run reached a real `SUCCEEDED` Job and the
    worker completed successfully. The test expected `text/csv`, while the
    established export handler and accepted service tests use
    `text/csv; charset=utf-8`. This was a test-only contract expectation error.
    Cleanup completed with zero `W10-` projects, zero Workflow rules, and zero
    workflow-keyed jobs remaining. No application defect or duplicate-delivery
    pass is claimed from this run.
14. In the first serial recovery collection, the RabbitMQ, Work publisher, and
    Workflow consumer cases passed. The Workflow API case then failed because the
    test incorrectly assumed that stopping the API also stopped the independent
    Workflow consumer. The Job outage case did not run because Playwright serial
    mode stopped after that failure. Every executed case restored its exact
    stopped service to healthy state and completed ownership-proven cleanup with
    zero current-run `W10-` projects, Workflow rules, and workflow-keyed jobs.
    No application defect or five-case recovery pass is claimed from this run.
15. The final source-suite invocations first used long-running service containers,
    whose images either contained older tests or omitted test files. Employee's
    image also compared a placeholder against the live local configuration. The
    corrected disposable, current-source mounts produced the final results above;
    the earlier harness results are not counted as source-suite evidence.
16. A final Linux frontend image build exposed missing cross-platform optional
    Rolldown, Lightning CSS, and `fsevents` entries in the npm lock. Regenerating
    only lock metadata with the repository's npm 11 line corrected reproducible
    `npm ci`; the frontend image and production Next.js build then passed.
17. A final `pip-audit` rerun could not start because the runtime images do not
    contain that audit executable. Two disposable installation attempts were
    interrupted after bounded waits during unusually slow package transfer. Both
    containers used `--rm` and left no one-off container. The last completed lock
    audit remains the recorded `pip-audit` 2.10.1 result in
    `dependency-review.md`; no new Python audit pass is claimed by this closure
    run.

## Deterministic contention and recovery evidence

Two independent PostgreSQL sessions synchronize on a barrier before selecting
eligible Work events with `FOR UPDATE SKIP LOCKED`. Six ordered events split into
two disjoint batches of at most three; each event had one active lease owner and
each returned batch preserved `(created_at, id)` ordering. A separate two-session
expired-lease race produced one claimant and one new random token. The prior token
could settle neither success nor failure, the exact current token published the
event, and the published event could not be reclaimed or regressed.

The rollback test replaces only that test session's commit method after an
`IN_PROGRESS` task is durable. `DONE`, its status activity, and its outbox insert
are prepared in one transaction, then the controlled commit failure is raised.
After rollback, status/version, activity count, and outbox count match the
pre-request state. A normal retry completes and creates one activity and one
event.

The crash-after-acceptance test starts with a durable Workflow execution. Its
fake Job boundary stores accepted logical jobs by the real deterministic
`workflow:<execution UUID>` key and returns a stable job UUID; the Workflow commit
then fails. After rollback, retry sends the identical key, receives the same UUID,
and settles the one execution. The PostgreSQL assertions prove one execution and
one logical accepted job. This failure occurs after the accepted response, not
before submission.

## Migration shape and retained state

Work was migrated to accepted Phase 9 revision `20261015_02`, populated with one
project, membership, task, comment, and activity, then upgraded to independent
Work revision `20261028_01`. All five retained rows remained, repeated head was
safe, and completing the retained task created exactly one outbox event. The
outbox has 15 inspected columns, eight indexes, primary key
`work_outbox_events_pkey`, and enum `work_event_status` with `PENDING`,
`IN_FLIGHT`, `PUBLISHED`, and `FAILED`. It intentionally has no cross-table
foreign keys because the durable event must survive later project/task cleanup.

Workflow clean zero-to-head and repeated-head upgrades passed at independent
Workflow revision `20261028_01`. Exact inspection confirmed the four enum types,
all named indexes, unique constraint
`workflow_executions_rule_id_source_event_id_key`, and `ON DELETE CASCADE`
foreign keys from executions to rules and source events. Deleting one rule
removed only its execution; the shared source event, other rule, and other
execution remained. Rule deletion is development-cleanup behavior only; no public
delete mutation is exposed.

## Dependency security disposition

The initial production audit reported
`GHSA-2464-fhr4-w9xw`, **Unauthenticated Remote Code Execution in Image
Optimization API when SVG files are used**, through the direct `next` dependency.
The installed version was Next.js `16.4.0`; the advisory affects versions greater
than `16.0.0` through `16.4.0`, and the compatible patched line begins at
`16.4.1`. npm's initial “no fix available” result reflected advisory metadata at
the time of that audit rather than a package-lock, peer-dependency, or Node.js
constraint: Next.js `16.4.3` supports the existing React 19.3 and Node 24 setup.

The application does not configure remote image sources or deliberately accept
attacker-provided SVGs for optimization, which reduced reachability but did not
eliminate the exposed `/_next/image` implementation. Next.js was therefore
upgraded directly to `16.4.3` without `npm audit fix --force`. ESLint, TypeScript,
Prettier, all **55 frontend tests**, and the production build passed afterward;
the production audit now reports **0 vulnerabilities**. No owner risk acceptance
is required for this resolved production finding. The full audit's two remaining
high findings are confined to development dependencies and remain recorded for a
separate compatible dependency-maintenance pass.

## Browser and outage acceptance

The workflow pages are included in the successful production build, component
tests cover their objective states, and the real lifecycle passed at all three
required viewports.

The final duplicate-delivery journey passed **1 passed, 0 failed** on desktop
with one worker and zero retries. It published the identical RabbitMQ event UUID
twice and proved exactly one Workflow execution, exactly one actor-scoped
deterministic Job, exactly one successful attempt, one durable CSV result with
`text/csv; charset=utf-8`, and the expected generation-one Job publication row.
Ownership-proven cleanup returned every current-run resource count to zero. The
three earlier failures remain recorded above as test defects: PostgreSQL JSON
operator precedence, result inspection before Job `SUCCEEDED`, and the incorrect
`text/csv` expectation. None is represented as a product failure or pass.

All five serial recovery scenarios passed across focused runs; no single
uninterrupted five-test invocation is claimed. The initial serial invocation
passed RabbitMQ outage, Work event publisher outage, and Workflow consumer outage,
then stopped after the Workflow API test's invalid assumption; the Job Service
case did not run in that invocation. The corrected focused invocation passed the
Workflow API and Job Service cases: **2 passed, 0 failed**, desktop, one worker,
zero retries. In the corrected API case only `workflow` was stopped. Public
GraphQL returned `SERVICE_UNAVAILABLE` with the sanitized message “Workflow
automation is temporarily unavailable.” The independent consumer created one
execution and Job while the API was unavailable. After the API recovered, public
GraphQL exposed that same persisted execution and Job linkage, and refresh
created no duplicate.

The dedicated four-role browser journey passed **1 passed, 0 skipped, 0 failed**
on desktop with one worker, zero retries, and a duration of approximately 1.7
minutes. It protected the primary `ADMIN` while using disposable manager, member,
and non-member identities. The journey verified manager lifecycle permissions,
`ADMIN` override, member read-only behavior, non-member concealment,
removed-manager reauthentication and denial, and ownership-proven identity
cleanup.

The opt-in specifications were prepared as follows:

- `workflow-multi-role.spec.ts` uses a protected primary administrator plus
  unique disposable manager, member, and non-member identities. It records each
  Employee UUID and Keycloak subject immediately, verifies the stable link, and
  provisions the identities sequentially only after a Keycloak and Employee
  preflight proves every `w10-` marker unused. The primary subject is recorded
  before setup and revalidated after cleanup. The specification
  exercises manager lifecycle, administrator override, member read-only access,
  non-member concealment, direct GraphQL denial, removed-manager reauthentication
  and stale-creator denial, storage inspection, and ownership-proven identity
  cleanup. Partial provisioning uses exact username, email, marker, subject, and
  Employee-link evidence; ambiguous ownership fails closed.
- `workflow-duplicate-delivery.spec.ts` completes one unique task, reads its exact
  committed Work event, and injects that same payload twice through durable
  exchange `work.domain` and routing key `work.task.completed.v1` using Kombu
  inside the configured Workflow service. It does not add a public test endpoint
  or directly manufacture final rows. Independent PostgreSQL assertions require
  one source event, one execution, the execution-derived idempotency key, one
  actor-scoped job, one successful attempt, one durable CSV result, and the exact
  generation-one publication event.
- `workflow-recovery.spec.ts` declares five separate serial cases for `rabbitmq`,
  `work-event-publisher`, `workflow-consumer`, `workflow`, and `job`. Each uses
  only `docker compose stop <service>` and `docker compose start <service>`,
  restores its exact service in `finally`, polls `docker compose ps --format
json <service>` to bounded healthy readiness, checks RabbitMQ dependents, and
  aggregates labeled cleanup failures.

All three specifications discover non-null resulting job UUIDs from exact
current-run Workflow executions before deleting the rule. For every validated
execution UUID, cleanup also derives the exact `workflow:<execution UUID>` key and
queries every matching Job row independently. A job is cleanup-owned only when
its submitter matches the committed Work event actor and both its related-project
column and payload project match the current-run project. A linked job that
disagrees with the key lookup fails closed. Cleanup deletes proven jobs, then the
rule and its owned source/execution state, then the Work project. Exact-key,
marker, and recorded-UUID queries independently verify zero rules, executions,
source events, Work outbox events, projects, tasks, jobs, attempts, durable job
results, Job publication rows, disposable profiles and identities where created,
and current-run one-off containers. Cleanup stages preserve fixed operation
labels and sanitized diagnostics and continue after an earlier stage fails.

The multi-role specification tracks the rule's current owned name separately: it
starts with the unique creation name and changes to the unique final name only
after the rename mutation succeeds. Discovery and cleanup use that current name;
the final zero check searches both names so partial rename state cannot be missed.

The three flags are `RUN_WORKFLOW_MULTI_ROLE_E2E`,
`RUN_WORKFLOW_DUPLICATE_E2E`, and `RUN_WORKFLOW_RECOVERY_E2E`. Credentials remain
process-environment inputs from the ignored local environment. Static discovery,
formatting, lint, type checking, and the non-destructive Workflow component suite
are recorded separately. The multi-role, duplicate-delivery, and recovery flags
were enabled only for their recorded credentialed journeys; duplicate delivery
and all five recovery cases have the focused-run results recorded above.

## Final acceptance reconciliation

The final non-destructive reconciliation reran the current-source Workflow, Work,
Job, Employee, and Gateway suites; all five services' Ruff lint and format checks
and MyPy; schema export; frontend GraphQL generation, Vitest, ESLint, TypeScript,
Prettier, production build, Compose validation, npm audits, migration heads,
runtime health, Compose DNS, cleanup queries, and repository hygiene checks.
Workflow and Work migration heads are `20261028_01`. Production npm audit remains
at **0 vulnerabilities**; the full audit remains the two development-only high
findings and advisory set documented above.

All **19** current Compose services were healthy. Frontend resolved Gateway, and
Gateway resolved Employee, Work, Job, Workflow, and Keycloak over Compose DNS.
The retained Phase 1 frontend and Gateway containers remained present and stopped
and were neither started nor modified. The primary administrator remained uniquely
present, enabled, active, `ADMIN`, complete, and linked through its matching stable
Keycloak subject.
Final corrected-specification static verification found **21 Playwright cases in
3 files** across the configured desktop, tablet, and mobile projects. Explicit
desktop-only guards prevent duplicate destructive execution in the tablet and
mobile projects. The focused Workflow Vitest collection passed **4 tests in 1
file** after the unchanged command was rerun outside the restricted process-spawn
environment; ESLint, TypeScript, and Prettier passed. No opt-in flag was enabled.
The “no opt-in flag” condition applied only to that earlier static-preflight step;
the later recorded multi-role, duplicate-delivery, and recovery journeys enabled
their respective opt-in flags.

The intended viewport matrix is desktop, 768 px, and 390 px. Subjective visual and
UX review remains deferred to Phases 12 and 15; automated viewport evidence is not
final visual or accessibility certification.

## Manual verification instructions

1. Sign in at `http://localhost:3010`, open **Workflows**, and create a rule for a
   project where the account is `PROJECT_MANAGER`.
2. Open an `IN_PROGRESS` task in that project and change its status to `DONE`.
3. Return to the rule detail page and observe one execution in history.
4. Open **resulting job** and verify the project task export completes with a CSV
   result.
5. Disable the rule, complete a different task, and confirm no execution is added
   for that later event.
6. For recovery checks, stop only the exact RabbitMQ, work-event publisher, or
   workflow-consumer service under test; restore it in a `finally` path, wait for
   health, and confirm the committed intent produces one logical execution and job.
7. Verify an administrator can manage every rule, a current project manager can
   manage only that project, a contributor can view but not mutate, and a
   non-member receives concealed denial.
8. Clean up only identities, projects, tasks, rules, executions, events, and jobs
   whose current-run ownership identifiers were recorded before creation. Leave
   ambiguous or pre-existing records untouched.

## Limitations

- The current Python lockfiles were not successfully re-audited during final
  closure. The interrupted attempts remain recorded above, and no new audit pass
  is claimed.
- The combined final Python image rebuild was interrupted and is not claimed as a
  pass.
