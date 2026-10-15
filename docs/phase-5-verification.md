# Phase 5 verification

Status: **Accepted**

Phase 5 adds task management to Work Service without adding a service, database,
or public REST business API. The Compose stack remains nine services. Phase 6 has
not started. The owner accepted Phase 5 on 2026-10-15 after automated functional,
authorization, security, lifecycle, concurrency, persistence, outage, recovery,
responsive-overflow, and basic accessibility verification passed. Subjective
visual and UX redesign remains deferred to Phases 12 and 15. Acceptance does not
claim final visual quality, accessibility certification, performance or
load-testing certification, or cross-service distributed transaction guarantees.

## Automated coverage matrix

| Requirement                                                                           | Implementation and automated evidence                                                                                                                                                                                                         | Layer                              | Remaining owner review                    |
| ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------- | ----------------------------------------- |
| Task model, validation, normalization, and stable reference                           | Typed Work models/schemas; service tests                                                                                                                                                                                                      | Unit/service                       | None                                      |
| Concurrency-safe project numbering and unique reference                               | Locked project counter plus database constraint; four-thread PostgreSQL test                                                                                                                                                                  | Real PostgreSQL                    | No large-scale stress claim               |
| List pagination, ordering, search, status, priority, assignee, and unassigned filters | Bounded opaque-cursor Work query and service tests                                                                                                                                                                                            | Service                            | None                                      |
| Bounded board lanes and `hasMore`                                                     | Maximum 25 per status lane; component and browser tests                                                                                                                                                                                       | Service/component/browser          | None                                      |
| Detail and cross-project concealment                                                  | Project-scoped lookup and membership authorization                                                                                                                                                                                            | Service/Gateway                    | None                                      |
| Explicit status state machine and reopen                                              | `test_exhaustive_status_transition_matrix_is_atomic` covers all 25 ordered pairs, including the explicit idempotent same-state policy                                                                                                         | Service                            | None                                      |
| Metadata and stale-version conflicts                                                  | Locked task mutation and optimistic version; PostgreSQL competing-update test                                                                                                                                                                 | Service/PostgreSQL                 | None                                      |
| Assignment and unassignment                                                           | `test_assignment_requires_manager_current_membership_and_version` plus `test_project_lock_prevents_assignment_membership_removal_race`; project-row serialization and assigned-member removal guard                                           | Gateway/service/PostgreSQL/browser | Cross-service atomicity is not claimed    |
| Contributor creation and restrictions                                                 | `test_manager_contributor_and_admin_create_tasks_with_atomic_activity`, `test_non_member_cannot_create_or_infer_task`, `test_archived_project_rejects_every_task_mutation`, and `test_current_contributor_profile_can_create_unassigned_task` | Service/Gateway/browser            | None                                      |
| ADMIN and project-manager control                                                     | Work authorization tests and real ADMIN/MANAGER browser journeys                                                                                                                                                                              | Service/browser                    | None                                      |
| Non-member concealment and denial                                                     | Direct detail/comment mutations denied in real browser journey                                                                                                                                                                                | Service/browser                    | None                                      |
| Inactive or missing current profile                                                   | `test_task_creation_requires_current_available_employee_profile` proves the current profile is reloaded before Work is called                                                                                                                 | Gateway                            | None                                      |
| Due date                                                                              | `test_due_date_contract_create_update_clear_invalid_and_stale`, Gateway date scalar coverage, and create-form GraphQL variable assertion                                                                                                      | Service/Gateway/component          | Date-only contract; no reminders          |
| Comments                                                                              | `test_task_comment_and_activity_cursor_boundaries_are_stable`, invalid/length coverage, and `renders HTML-like comment content as inert plain text`                                                                                           | Service/component/browser          | Editing and deletion intentionally absent |
| Append-only activity                                                                  | `test_failed_mutations_leave_no_activity_and_success_data_is_allowlisted`, exhaustive transition rollback assertions, and `test_activity_history_has_no_public_edit_or_delete_mutation`                                                       | Service/Gateway                    | No public mutation exists                 |
| Archived project behavior                                                             | All task writes rejected and reads retained; browser archive/reactivate journey                                                                                                                                                               | Service/browser                    | None                                      |
| Dependency failure sanitization                                                       | Work and Employee error mapping plus real gateway, Employee, Keycloak, and Work outages                                                                                                                                                       | Gateway/browser                    | None                                      |
| Persistence and recovery                                                              | Task, comment, activity, project, and membership survive Work restart                                                                                                                                                                         | Real Docker                        | None                                      |
| Responsive and basic accessibility behavior                                           | Semantic controls, keyboard-capable forms, overflow/storage checks at three widths                                                                                                                                                            | Component/browser                  | Not accessibility certification           |
| Exact cleanup                                                                         | Project-key/UUID cleanup cascades only the test-owned task records                                                                                                                                                                            | Real Docker                        | None                                      |

## Exact automated results

Executed from the Phase 5 working tree on 2026-10-15:

| Check                                                     | Result                                                |
| --------------------------------------------------------- | ----------------------------------------------------- |
| Work Service pytest without PostgreSQL URL                | 48 passed, 5 skipped                                  |
| Work PostgreSQL integration tests                         | 5 passed                                              |
| Work Ruff lint and format                                 | Passed                                                |
| Work MyPy                                                 | Passed for 8 source files                             |
| Clean migration from zero through Phase 5                 | Passed; revisions `20261014_01` then `20261015_02`    |
| Repeated migration at Phase 5 head                        | Passed                                                |
| Existing preserved Work database upgrade                  | Passed; head `20261015_02`, three task tables present |
| Employee Service pytest                                   | 40 passed                                             |
| Employee Ruff lint and format                             | Passed                                                |
| Employee MyPy                                             | Passed for 10 source files                            |
| Gateway pytest                                            | 75 passed                                             |
| Gateway Ruff lint and format                              | Passed                                                |
| Gateway MyPy                                              | Passed for 7 source files                             |
| Gateway schema export                                     | Passed                                                |
| Frontend GraphQL generation                               | Passed                                                |
| Frontend Vitest                                           | 42 passed in 9 files                                  |
| Frontend ESLint and TypeScript                            | Passed                                                |
| Frontend Prettier                                         | Passed                                                |
| Next.js production build                                  | Passed, including three task routes                   |
| Docker Compose configuration and application image builds | Passed                                                |
| Work dependency audit                                     | No known vulnerabilities                              |
| Production npm audit                                      | 0 vulnerabilities                                     |
| Full npm audit                                            | 12 high-severity development-only `braces` findings   |

Collection confirmed 53 Work tests: 33 in `test_work.py`, 15 in `test_tasks.py`,
and 5 in `test_postgres.py`. The earlier apparent reduction was caused by replacing
16 separately parametrized status-transition cases with one exhaustive loop over
all 25 ordered status pairs; no test file was omitted or deselected.

The five ordinary Work skips are the PostgreSQL-only membership/final-manager,
task-number/task-version contention, and assignment-versus-membership-removal race
tests. They require `WORK_POSTGRES_TEST_URL`. All five passed against an isolated
PostgreSQL 18 container without a volume. The test container was removed exactly
after the run.

The assignment race has two valid serialized outcomes. Assignment may commit and
membership removal is then rejected with `MEMBER_HAS_ASSIGNED_TASKS`, or membership
removal may commit and assignment is then rejected with `INVALID_ASSIGNEE`. The
final assertion proves a newly assigned task never points to a removed project
member. This protects Work Service consistency; no cross-service transaction with
Employee Service is claimed.

Task, comment, and activity cursor tests cover malformed cursors, sizes below one
and above 50, stable UUID ordering with equal timestamps, and forward continuation
without duplicates or omissions. Due dates use a PostgreSQL `date` and GraphQL
`Date`, preserving date-only semantics without machine-local timezone conversion.

## Docker-backed browser results

| Collection                                                                                                                            | Result                                    |
| ------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| Phase 1 foundation, Phase 2 authentication core, Phase 4 project lifecycle, and Phase 5 task lifecycle at desktop, 768 px, and 390 px | 21 passed, 12 intentional skips, 0 failed |
| Phase 5 task lifecycle final corrected collection                                                                                     | 3 passed                                  |
| MANAGER, contributor, non-member, project protection, and task authorization                                                          | 1 passed                                  |
| Work task/comment/activity persistence, outage, and recovery                                                                          | 1 passed                                  |
| Phase 3 employee administration regression                                                                                            | 1 passed                                  |
| Gateway and Employee Service outage/recovery                                                                                          | 2 passed                                  |
| Keycloak refresh-failure and login-outage recovery                                                                                    | 2 passed                                  |

The 12 combined-collection skips are the four established opt-in authentication
categories repeated for each viewport: access-token refresh, inactive-employee
fixture, refresh-failure recovery, and real Keycloak outage. Dedicated recovery
runs exercised refresh failure and Keycloak outage successfully. The inactive
fixture is unchanged from accepted Phase 2 coverage.

The first Phase 5 viewport run failed all three projects because a heading query
matched both the project name and “Project tasks”. The selector was narrowed to an
exact accessible name. The next run passed tablet and mobile but desktop exposed
another partial accessible-name collision between “Tasks” and “Taskspace”. That
selector was also made exact. The entire three-project collection was rerun and
passed 3/3. No application defect was hidden by retries.

An initial temporary PostgreSQL command failed before resource creation because a
PowerShell cryptography overload was unavailable, and the sandbox could not access
Docker. It was rerun with a runtime-generated GUID value and approved Docker
access. Clean migration, repeated migration, and all four PostgreSQL tests that
existed at that point then passed, followed by exact container/network cleanup.

Vitest initially encountered the known sandbox `spawn EPERM` restriction. It was
rerun with local worker spawning enabled and passed. A first pip-audit invocation
used an incompatible `--disable-pip` combination; the normal isolated audit was
then executed and found no known vulnerabilities.

The coverage pass found one Work consistency defect: serialized membership removal
could commit after assignment and leave the task assigned to a former member.
`remove_member` now rejects removal while that member owns assigned tasks. The
deterministic PostgreSQL race passed without sleeps. The service boundary also now
normalizes and validates comment length before creating either the comment or its
activity row; this mirrors the internal request-schema boundary and makes direct
service use fail atomically.

The existing desktop multi-role browser collection initially stopped twice at the
primary administrator OIDC callback with the sanitized
`AUTHORIZATION_RESPONSE_INVALID` classification. Investigation found that the
sign-in page used an automatically prefetched link for the state-changing login
route. Prefetch and click could create separate OIDC transactions, allowing the
late response to replace the transaction cookie. Disabling prefetch for that link
removed the race without weakening state, nonce, PKCE, issuer, or token validation.
The real core authentication journey then passed once and passed five consecutive
fresh-context repetitions with one worker and no retries. The updated multi-role
journey passed 1/1 and cleaned its exact identities and project.

Callback diagnostics now emit only fixed application-owned classifications:
`TRANSACTION_MISSING`, `TRANSACTION_ALREADY_CONSUMED`,
`STATE_VALIDATION_FAILED`, `AUTHORIZATION_RESPONSE_INVALID`,
`ID_TOKEN_INVALID`, `TOKEN_RESPONSE_INVALID`, `UPSTREAM_RESPONSE_INVALID`,
`UPSTREAM_TIMEOUT`, `EMPLOYEE_PROFILE_LOOKUP_FAILED`,
`SESSION_CREATION_FAILED`, and `UNKNOWN`. Unit tests inject sensitive samples in
error names, codes, messages, causes, and nested causes and prove that none enters
console output or the sanitized redirect.

The first combined post-correction browser run produced three task-lifecycle
failures because the test accepted the already-present `IN_PROGRESS` transition
button as proof that the mutation had persisted, then unmounted the comment form
before its request was sent. Waiting for the persisted `Version 2.` result fixed
the synchronization boundary. The next complete run produced 20 passes, 12 skips,
and one mobile authentication failure: the server-rendered profile button was
clicked before React hydration attached its handler. The button now remains
disabled until React's client snapshot is available. A complete 33-test rerun with
one worker and no retries finished with 21 passes, 12 explained skips, and zero
failures. An intermediate run had 15 passes and 18 skips because the project and
task opt-in flags were omitted from a fresh shell; the final run explicitly enabled
both lifecycle categories.

The assigned-member guard is verified through every public boundary. Work Service
returns `MEMBER_HAS_ASSIGNED_TASKS`, preserves membership and assignment on
rejection, prioritizes final-manager protection, and permits removal after
unassignment. Gateway maps the domain code to a fixed message without forwarding
the Work response. The frontend retains the member and shows the understandable
failure. The real multi-role journey observes the rejection, unassigns the task,
and then removes the member successfully.

An initial activity-payload assertion ordered UUID activity identifiers as if they
were chronological and failed once. The assertion was corrected to compare the
exact activity-type set and select the event by its type. The complete Work suite
then passed 48 tests with the five PostgreSQL-only tests intentionally skipped.

A final frontend rerun after the hydration correction produced 39 passes and three
independent five-second timeouts while test files ran concurrently. No assertion
failed. The complete unchanged suite was rerun and passed 42/42 in 9 files; timeout
limits and assertions were not weakened.

## Cleanup and limitations

Every browser journey used a unique project key and removed only its exact project
UUID/key pair. Cascading Work constraints removed its tasks, comments, activity,
and memberships. The multi-role journey removed only its exact disposable
Employee profiles and Keycloak identities. Ambiguous pre-existing records were
left untouched.

Final cleanup checks found zero test-owned `T5-`, `MR-`, `REC-`, or `E2E-`
projects, zero disposable `p4-` Employee profiles, zero disposable `p4-` Keycloak
identities, and zero temporary test containers. All nine Compose containers were
healthy. The primary administrator remained active, enabled, and assigned ADMIN;
its single Employee profile remained linked to its single Keycloak identity by the
stable subject.

The board deliberately uses independently bounded status lanes with a `hasMore`
indicator; additional records are available through the filtered list. Task list,
comment, and activity cursors are forward-only. PostgreSQL contention coverage is
deterministic rather than a performance or load test. The multi-role lifecycle is
desktop-only, while the essential task lifecycle runs at all three required
widths. Automated keyboard and semantic-control checks provide basic accessibility
evidence, not certification. Subjective visual and UX review remains deferred to
Phases 12 and 15.

These limitations do not block Phase 5 functional acceptance. Phase 5 was accepted
by the owner on 2026-10-15. Phase 6 has not started.
