# Phase 4 verification

Status: **Accepted**

Phase 4 implements project management without starting Phase 5. Automated
functional acceptance completed on 2026-10-14, and the owner accepted Phase 4 on
2026-10-14. Subjective visual and UX redesign remains deferred to Phases 12 and 15. This acceptance does not claim final visual quality, performance or
load-testing certification, or accessibility certification.

## Coverage matrix

| Requirement                                                                            | Production implementation                                          | Automated evidence and layer                                                                              | Real PostgreSQL / Docker                                      | Remaining gap                                                     |
| -------------------------------------------------------------------------------------- | ------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- | ----------------------------------------------------------------- |
| Project creation, validation, normalization, and unique immutable key                  | Work Service schemas and transactional service                     | Work unit/service tests, gateway GraphQL tests, frontend component tests, project lifecycle browser tests | Both                                                          | None                                                              |
| Directory loading, success, empty, error, retry, search, status filter, and pagination | Cursor-paginated Work query and project directory                  | Work service tests and frontend component tests                                                           | Browser lifecycle uses real Docker                            | Forward-only service cursor contract                              |
| Stable ordering and bounded page size                                                  | Created-at and ID ordering with a maximum page size                | Work service pagination tests                                                                             | Service tests; clean PostgreSQL migration separately verified | None                                                              |
| Project detail and membership presentation                                             | Work detail endpoint; gateway batch-enriches stable employee IDs   | Work tests, gateway GraphQL tests, component tests, browser detail journeys                               | Real Docker                                                   | Missing or inactive profiles intentionally render a safe fallback |
| DRAFT, ACTIVE, ARCHIVED, and reactivation                                              | Explicit lifecycle transition rules                                | Work service, gateway, component, and browser lifecycle tests                                             | Real Docker                                                   | None                                                              |
| Archived read-only behavior and optimistic versions                                    | Work mutation guards and version checks                            | Work service and gateway tests                                                                            | Service tests                                                 | None                                                              |
| ADMIN and MANAGER creation; MEMBER denial                                              | Gateway reload plus independent Work authorization                 | Direct Employee/Work tests, direct GraphQL tests, multi-role browser journey                              | Real Docker                                                   | None                                                              |
| Current-profile reload and forged GraphQL denial                                       | Gateway reloads Employee Service profile before every operation    | Gateway tests and direct MEMBER browser GraphQL request                                                   | Real Docker                                                   | None                                                              |
| Project manager, contributor, and non-member boundaries                                | Work role checks on every project operation                        | Work tests and real manager/contributor/non-member journey                                                | Real Docker                                                   | None                                                              |
| Eligible active employee lookup                                                        | Employee Service eligible directory and bounded batch resolver     | Direct Employee Service and gateway tests                                                                 | Service tests                                                 | None                                                              |
| Membership add, role change, removal, duplicate, and final-manager protection          | Locked Work transactions and final-manager invariant               | Work tests, PostgreSQL concurrency tests, frontend tests, multi-role browser journey                      | Both                                                          | Large-scale contention stress is not included                     |
| Employee enrichment without N+1 requests                                               | One bounded Employee Service batch per project response collection | Gateway test covering multiple projects and memberships in one batch                                      | Service test                                                  | None                                                              |
| Work and Employee dependency failures                                                  | Bounded clients and sanitized GraphQL domain mapping               | Gateway tests plus real Work, Employee, and gateway outage/recovery browser tests                         | Real Docker                                                   | None                                                              |
| Persistence across restart                                                             | Work PostgreSQL named volume and forward-only migration            | Work restart browser test re-reads exact project and membership                                           | Real Docker                                                   | None                                                              |
| Responsive overflow, mobile navigation, keyboard Escape, and focus restoration         | Existing responsive shell and semantic controls                    | Project lifecycle plus foundation collection at desktop, 768 px, and 390 px                               | Real Docker                                                   | Subjective visual review is deferred                              |
| Browser token absence and exact cleanup                                                | Opaque server session; test-owned UUID/key/subject cleanup         | Authentication and lifecycle browser assertions                                                           | Real Docker                                                   | None                                                              |
| Clean database migration                                                               | Alembic revision `20261014_01`                                     | Upgrade on a fresh temporary PostgreSQL database, repeated upgrade, and schema inspection                 | Real PostgreSQL                                               | None                                                              |

## Service, GraphQL, and frontend results

Executed from the Phase 4 working tree on 2026-10-14:

| Check                                     | Exact result                                        |
| ----------------------------------------- | --------------------------------------------------- |
| Work Service pytest, ordinary environment | 33 passed, 2 skipped                                |
| Work PostgreSQL concurrency tests         | 2 passed                                            |
| Work Ruff lint and format                 | Passed                                              |
| Work MyPy                                 | Passed                                              |
| Employee Service pytest                   | 40 passed                                           |
| Employee Ruff lint and format             | Passed                                              |
| Employee MyPy                             | Passed                                              |
| Gateway pytest                            | 57 passed                                           |
| Gateway Ruff lint and format              | Passed                                              |
| Gateway MyPy                              | Passed                                              |
| Gateway schema export                     | Passed; committed schema regenerated                |
| Frontend GraphQL generation               | Passed; committed generated operations regenerated  |
| Frontend Vitest                           | 34 passed in 7 files                                |
| Frontend ESLint                           | Passed                                              |
| Frontend TypeScript                       | Passed                                              |
| Frontend Prettier                         | Passed                                              |
| Next.js production build                  | Passed; 18 routes                                   |
| Docker Compose configuration              | Passed                                              |
| Docker image build                        | Passed                                              |
| Work Python dependency audit              | No known vulnerabilities                            |
| Production npm audit                      | 0 vulnerabilities                                   |
| Full npm audit                            | 12 high-severity development-only `braces` findings |

The two ordinary Work skips are exactly the PostgreSQL-only concurrency tests.
They require `WORK_POSTGRES_TEST_URL` and intentionally do not run against the
ordinary SQLite suite. Both passed against a temporary real PostgreSQL database.

A final confirmation batch was initially launched concurrently from the repository
root. That invocation gave MyPy conflicting top-level `app` modules, made the
gateway schema test look for its relative schema in the wrong directory, and let
the Employee test process inherit the local `.env`. Vitest and the local Next.js
build also encountered sandbox `spawn EPERM` errors. Each command was rerun from
its service directory with isolated caches and, for the Node worker processes,
outside that process sandbox. The corrected results are the passing counts above;
the application code did not require a correction.

The Work dependency input contains direct requirements only. The installed
`pip-compile` 7.5.2 could not run with pip 26.2.1 because pip removed its
`stdlib_pkgs` interface. A pip dry-run report resolved the direct input, the lock
was generated from that report, and the temporary report was deleted. The Work
image builds from the resulting pinned lock.

## Migration verification

A temporary PostgreSQL 18 container and an isolated network were created without
a volume. `alembic upgrade head` succeeded twice. Inspection found revision
`20261014_01`, the `projects` and `project_memberships` tables, both project enum
types, eight indexes, two unique constraints, and one foreign key. The exact
temporary container and network were removed afterward.

The first Work container start exposed a migration defect: the migration created
PostgreSQL enum types explicitly and then attempted to create them again with the
tables. Removing the duplicate explicit creation corrected the migration. Two
early attempts to run PostgreSQL tests inside the production Work image also
failed because its intentional `.dockerignore` excludes `tests/`. The final run
used the local test suite against a temporary loopback PostgreSQL instance and
passed both concurrency tests.

## Docker-backed browser results

| Collection                                                                 | Project                 | Result              |
| -------------------------------------------------------------------------- | ----------------------- | ------------------- |
| Phase 1 foundation, Phase 2 authentication core, Phase 4 project lifecycle | Desktop                 | 6 passed, 4 skipped |
| Same combined collection                                                   | 768 px                  | 6 passed, 4 skipped |
| Same combined collection                                                   | 390 px                  | 6 passed, 4 skipped |
| Authentication refresh collection                                          | Desktop, 768 px, 390 px | 3 passed, 3 skipped |
| Refresh-failure/session-expiration recovery                                | Desktop                 | 1 passed            |
| Real Keycloak outage and recovery                                          | Desktop                 | 1 passed            |
| Phase 3 employee administration regression                                 | Desktop                 | 1 passed            |
| Gateway outage and recovery                                                | Desktop                 | 1 passed            |
| Employee Service outage and recovery                                       | Desktop                 | 1 passed            |
| Work persistence, outage, and recovery                                     | Desktop                 | 1 passed            |
| Manager, contributor, non-member, and final-manager journey                | Desktop                 | 1 passed            |

The complete responsive combined collection therefore finished with **18 passed,
12 skipped, and 0 failed**. Each project produced six passes and four intentional
skips. The skipped categories were:

- access-token refresh, gated by `RUN_AUTH_REFRESH_E2E=1` and exercised separately
  on all three projects;
- inactive-employee denial, an opt-in Phase 2 fixture scenario and inapplicable to
  the project viewport run;
- refresh-failure recovery, gated by `RUN_AUTH_FAILURE_E2E=1` and exercised
  separately on desktop;
- real Keycloak outage, gated by `RUN_LOGIN_OUTAGE_E2E=1` and exercised separately
  on desktop.

The initial combined 768 px/mobile run had two navigation timeouts because the
test assumed a desktop-visible Projects link. The test was corrected to exercise
the drawer and Escape focus restoration when the responsive drawer is present,
then navigate to the protected route. The entire three-project collection was
rerun and produced the zero-failure result above.

The multi-role run used three unique disposable identities. A real MANAGER created,
edited, activated, archived, and reactivated a project; added a contributor;
encountered final-manager protection; promoted a safe replacement manager; and
transferred management. The contributor could read the project but a forged
create/update was rejected. A non-member could not list or open the project. The
test removed only its exact project, profiles, and Keycloak identities.

The Work recovery run created one exact project, restarted Work, proved that its
project and membership persisted, stopped only Work, observed a sanitized public
GraphQL unavailable response, restored health in a cleanup path, and proved normal
queries recovered. Gateway, Employee Service, Keycloak, and Work outage scenarios
ran serially.

## Cleanup and safety

Post-run database checks found zero project rows with the Phase 4 lifecycle,
multi-role, or recovery markers and zero Employee profiles with the Phase 4
disposable prefix. The primary development administrator remains active, linked
by a non-null Keycloak subject, and has the `ADMIN` role. All nine Compose
containers are healthy.

One Phase 3 cleanup lookup initially used a Keycloak username query whose matching
semantics did not identify the exact test user. The Employee profile's stable
subject and email were then used to prove exact ownership before removing only
that disposable profile and identity. No broad cleanup was used. Ambiguous
pre-existing null-linked idempotency records were left untouched.

No screenshot, video, trace, credential, token, or temporary dependency-resolution
report is part of the deliverable set. Playwright output directories are ignored.

## Remaining limits and deferred review

- Cursor pagination is forward-only at the service contract; the frontend keeps
  visited cursors for a previous-page control within one browsing session.
- PostgreSQL concurrency coverage uses deterministic two-request contention tests;
  it is not a large-scale stress or performance test.
- The complete multi-role identity lifecycle is a desktop journey. The essential
  administrator project lifecycle and responsive shell run at desktop, 768 px,
  and 390 px.
- Automated keyboard, focus, responsive-overflow, and semantic-control checks are
  basic functional accessibility evidence, not accessibility certification.
- Subjective visual and UX review is intentionally deferred to the system-wide
  redesign in Phase 12 and final portfolio refinement in Phase 15.

These accepted limitations do not block Phase 4 functional acceptance. Phase 5
has not started.
