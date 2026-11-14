# S0 architecture and ownership decisions

Reference baseline is Taskspace_Portal_Development_Plan.docx version 1.1,
14 November 2026. Its SHA-256 is
08af1dd1024824bbc91d7f0433e2e35e45db8b3e7084c9650edb99314199d6fd.
The reference document is external to the repository and remains read-only.

## Decisions adopted for S0

The owner selected separate fresh development data for the replacement while
preserving legacy data. Existing users, projects, tasks, identity realms,
sessions, databases, volumes and queues remain untouched.

The accepted frontend baseline is materialized at legacy/frontend from the
verified committed-source archive. The pre-S0 uncommitted portal frontend is
preserved separately at legacy/experiments/portal-web. Its root redirect does
not match the accepted domain browser tests, so it is not used by legacy CI.
All other previous application source remains under legacy. The new web app does not import or render that source
and has no redirect to it. Only a preparation page exists in S0; authentication
and protected entry are S1 and S2 work.

The committed baseline is fc8fc6f632eaca55f8e54ffdcc65b048d0e83592.
The working branch remains portal-r1-baseline. Source restructuring does not
change history or establish a new accepted commit. The owner decides the next
branch and commit manually after reviewing the dirty worktree.

## Domain ownership

These are chosen responsibility boundaries, not empty deployable skeletons.
Services will be introduced only when a functional stage requires them.

| Intended deployable path | Owns | Introduction |
| --- | --- | --- |
| services/gateway | Public Strawberry GraphQL API, authenticated actor resolution, orchestration and response privacy | S1–S2 as needed |
| services/people | Application identity associations, Keycloak provisioning integration, employment records and organization structure | S2–S5 as needed |
| services/project-work | Calendar, projects, membership, leadership, assignments, task execution, reviews, dependencies, extensions and coordination | S6 onward |
| services/notifications | Notification inbox, authorized content and idempotent delivery | Relevant notification stage |
| services/jobs | Durable exports/reports with execution ownership and recovery | When a required background operation is implemented |
| services/workflow | Event/rule automation only where an approved requirement warrants it | When required |

Identity/access and people initially share the people service and authoritative
identity association. Keycloak owns credentials. There is no second identity
database or separate HR employee copy. A later separation into
services/identity-access requires a demonstrated ownership or scaling need.

Coordination initially belongs to project-work because update requests and
internal meetings depend on project authority. Reviews, scheduling and deadline
approvals stay transactional in the work domain. Notifications and automation
react to committed decisions rather than redefining them.

GraphQL is the only public business API. Private service communication uses
authenticated internal HTTP with a trusted gateway actor context and independent
domain authorization. Client-supplied roles or employee IDs never establish
authority. Exact identity-provider and trusted-service controls must be audited
during S1/S2 before their source is retained.

## Frontend structure

apps/web/src/app owns Next.js route composition and layouts. The implemented
S0 route is the preparation page only. The following module locations are reserved
in this design and will be created with their functional stage:

| Location | Responsibility |
| --- | --- |
| src/portals/admin | Admin views and navigation from S3 |
| src/portals/manager | Manager views and navigation from S7 |
| src/portals/employee | Employee views and navigation from S15 |
| src/portals/hr | HR views and navigation from S18 |
| src/project-workspace | Authorized project-context views including leader work |
| src/shared/auth | Audited server session and identity protocol integration |
| src/shared/api | Typed GraphQL operations and transport |
| src/shared/ui | Necessary shared controls and design tokens |

These modules are not placeholder dashboards. Team leadership remains
project-specific and does not create a global TEAM_LEADER company role.
The new Next.js tracing and build roots stay inside apps/web.

## Existing capability assessment

The isolated backend has six independently built Python application services:
Gateway, Employee, Work, Job, Workflow and Notification. Each domain service
has its own database credentials/data ownership. Gateway is the public business
boundary and uses per-service internal credentials. Docker Compose also includes
Keycloak, Redis, RabbitMQ, PostgreSQL and observability processes.

Employee currently combines Keycloak account provisioning with a minimal
employment profile. It has ADMIN, MANAGER and MEMBER roles. Its mechanisms are
candidates for a later audited people implementation; HR is not implemented.
Work owns the existing task/project rules and outbox. Job owns durable report
execution, leases and terminal events. Workflow and Notification consume events
through their respective inbox/idempotency paths. These reliability mechanisms
must be assessed against new requirements before reuse.

The previous R1/R2 visual work and later portal shell are isolated with the
implementation that produced them. Their existence is not evidence of acceptance
under this new roadmap. No source file from that interface is imported by the
new application.

## Data and runtime isolation

The current legacy project name remains enterprise-task-platform-phase2.
No running resource is recreated by S0. Existing bind-mounted Keycloak and
observability configuration remains at infrastructure so those mount sources
stay intact. Legacy Compose paths explicitly refer to ../infrastructure.

The replacement Compose name is taskspace-portals-development, with web port
3020. S0 has no database, message consumer, publisher, identity provider or
Redis connection. Thus it cannot consume legacy messages or write legacy data.

Before S1 starts infrastructure, its own identity realm/client, session store,
database credentials, ports, volumes and messaging virtual host must be named
and checked against the legacy inventory. No old consumer may be started against
new queues, or vice versa. Future SQL, outbox and inbox schema changes belong to
the owning service and need explicit migration approval.

## Runtime and package baseline

| Area | Inspected version or pin |
| --- | --- |
| New app Node | 24.15.0 |
| New app npm | 11.5.1, matching the inspected local npm |
| Python host | 3.13.5 |
| Python CI family | 3.13 |
| Next.js | 16.4.3 |
| React / React DOM | 19.3.0 |
| TypeScript | 6.0.3 |
| Tailwind / Tailwind PostCSS | 4.3.3 |
| ESLint / Next lint configuration | 9.39.5 / 16.4.0 |
| Prettier | 3.9.9 |
| Legacy FastAPI / Strawberry | 0.143.0 / 0.334.2 |
| Legacy SQLAlchemy / Alembic / Psycopg | 2.1.4 / 1.20.0 / 3.3.6 |
| Legacy Celery / Kombu | 5.6.3 / 5.6.2 |
| Legacy Python verification tooling | Preserved in service-specific locks |

The new dependency graph starts from inspected exact versions, with a separate
lockfile containing only the new app's required packages. It excludes the old
app's GraphQL client, session, chart and testing packages until needed.
The old frontend's package-manager declaration remains untouched in legacy.
No local global toolchain was upgraded.

## CI and verification ownership

All six existing CI jobs remain mandatory. Their execution directory is legacy
and their cache paths point to relocated lockfiles. Existing isolated-stack and
report validators remain in legacy/scripts with their fail-closed checks.
Their source paths, Compose project names, queue names and persistent identifiers
remain consistent. Their ownership validator explicitly protects both the legacy
and replacement development project names from isolated teardown.

The new S0 job verifies structure regressions, formatting, lint, types and the
new production build. The aggregate quality gate requires that job as well.
Source-boundary checks reject new imports from legacy, root-level resurrection
of the old app, unpinned application dependencies, wrong Docker context, missing
CI cache paths and a missing required legacy CI gate.

Recovery and acceptance evidence is maintained in s0-verification.md.
