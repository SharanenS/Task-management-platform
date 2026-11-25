# Taskspace

Taskspace is being rebuilt as a portal-oriented corporate project and employee
management platform using Next.js, React, TypeScript, Python, FastAPI, Strawberry
GraphQL, PostgreSQL, Keycloak, Redis, RabbitMQ and Celery where required.

S0 through S10 are merged. S11 adds contextual leader task planning,
private instructions and acceptance criteria, and retained single-assignee
reassignment history. The approved runtime is applied and responsive acceptance
passed; owner website review and remote CI remain pending. See [S11 verification](docs/s11-verification.md) and the
[task-planning contract](docs/s11-task-planning-contract.md).
Gmail remains configured as dailygotasks@gmail.com; owner decisions and coordination send no email.
The calendar form detects local time automatically; see [calendar entry](docs/calendar-local-time.md).

## Source layout

| Path | Responsibility |
| --- | --- |
| apps/web | Independent authentication interface and server-side session boundary |
| services/gateway | Public GraphQL account-entry API and verified identity orchestration |
| services/project-work | Calendars, projects, membership, coordination, owner decisions and tasks |
| services/people | Authoritative accounts, employee associations and company-role grants |
| packages/security | Shared provider JWT validation; no business data ownership |
| legacy/frontend | Accepted baseline frontend used by historical verification |
| legacy/experiments/portal-web | Preserved uncommitted portal experiment; not the replacement app |
| legacy | Preserved services, tests, scripts and historical records |
| infrastructure | Existing operational configuration retained for the running legacy stack |
| scripts | Source checks and isolated authentication operations/acceptance |
| tests/structure | Isolation and CI path regression tests |
| docs | Current architecture, file inventory and S0 verification |

The architecture and reserved domain/module locations are defined in
[the S0 architecture record](docs/s0-architecture.md).
The authoritative product plan is the owner's read-only
Taskspace_Portal_Development_Plan.docx, version 1.1 dated 14 November 2026.
The earlier portal-refinement roadmap is historical material under legacy/docs.

## Verify S0 locally

Use Node 24.15.0, npm 11.5.1 and Python 3.13. Install dependencies only inside the
new app. Dependencies are pinned and the lockfile must remain synchronized.

```powershell
npm --prefix apps/web ci --ignore-scripts
.\scripts\test-s0.ps1
```

The Bash equivalent is bash scripts/test-s0.sh. Neither verification entrypoint
starts Docker, resets data, creates accounts or runs migrations.

The development origin is http://127.0.0.1:3020. Authentication also requires
the separate identity and session services. Do not run an additional development
server on that port while the web container owns it.
The authentication wrapper uses local private credentials without changing .env.
Starting the stack or applying migrations requires runtime approval; see docs/s2-verification.md.

## Execution isolation

The root compose.yaml declares only the new web application and uses the independent
project name taskspace-portals-development. It creates no database, queue,
worker, identity realm or session store. Do not launch it as part of source review.

The existing stack remains under its original project name
enterprise-task-platform-phase2. Its definition is legacy/compose.yaml.
Its running frontend at port 3010 is the legacy application.
The approved S2 stack extends S1 with a private people database, people service,
and GraphQL gateway. It retains the separate realm, identity database and session
store. Legacy accounts and data remain untouched. The gateway is published only
on 127.0.0.1:8020; the people service and both databases have no host ports.

Read-only configuration checks from the repository root are:

```powershell
docker compose --env-file .env -f compose.yaml config --quiet
docker compose --env-file .env -f legacy/compose.yaml config --quiet
```

The existing private .env remains at the root for legacy use. The new .env.example
contains only the new web port. The prior environment template is preserved at
legacy/.env.example. Do not copy legacy account/database secrets into the
replacement application.

Starting or changing containers, migrations, real accounts, data and deployments
requires separate authorization. The current data decision is to preserve legacy
data and create separate fresh development data for the replacement.

## Review and acceptance

See [S0 verification](docs/s0-verification.md) for actual results and limitations.
Local source recovery archives are kept outside the deliverable under
.local/recovery. Their exact location and restoration procedure are recorded
in the verification report.

Git history and GitHub changes remain manual owner actions. S2 development was
authorized after S1 merge; subsequent stages require their own review and authorization.

## Authentication and account-entry verification

Source-only checks do not start services:

```powershell
npm --prefix apps/web test
npm --prefix apps/web run format:check
npm --prefix apps/web run lint
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
python scripts/run_structure_tests.py
```

After runtime approval, the isolated development commands from the repository
root are:

```powershell
python scripts/account-entry-development.py preflight
python scripts/account-entry-development.py up --apply-migration
python scripts/account-entry-development.py status
python scripts/run-s1-acceptance.py --project desktop
python scripts/run-s1-acceptance.py --project tablet
python scripts/run-s1-acceptance.py --project mobile
python scripts/run-s1-acceptance.py --project desktop --recovery
```

The recovery opt-in requires separate outage approval and stops only the new identity and session services, one at a
time. Both the test and wrapper verify restoration. The wrapper then repeats the
full credentialed desktop lifecycle. No command deletes persistent volumes.

## S2 account entry

Each account has one company role: ADMIN, MANAGER, EMPLOYEE or HR. Team leadership
is a project-specific appointment for an employee; it is not a company role.
Company roles alone confer no project membership or private project authority.
Missing/inactive account or employee associations and missing roles are denied.
The people service reads current authority for every request rather than storing
roles in browser cookies or trusting identity-provider role claims.

The signed-in confirmation page reads only its own authorized account through
GraphQL. Future portals are not linked or simulated. No public account-creation,
role-grant or administrator bootstrap operation is introduced in S2.

Source-only backend verification uses the new service and test lockfiles:

```powershell
python -m pip install -r services/gateway/requirements.lock -r services/people/requirements.lock -r tests/account_entry/requirements.lock
python scripts/run-s2-source-checks.py
npm --prefix apps/web run codegen
```

Apply the initial people migration only after runtime authorization, using the
account-entry wrapper above. Credentials remain private under .local/account-entry;
root .env is not used. The wrapper checks ownership, changes only the verified
new-realm client API-audience mapper and revokes its bootstrap grant. Existing
identity accounts are not automatically associated with application profiles.
Use `python scripts/verify-account-entry-postgres.py` after approved startup to
verify migration parity and constraint probes which are always rolled back.

## S3 administrator portal

The implemented administrator routes are /admin, /admin/profile and /admin/security.
Current ADMIN authority is checked independently by the pages, GraphQL gateway
and private people service. The security entry uses the identity provider's own
reauthentication/password form; application JavaScript never receives passwords.

After explicit runtime/migration approval, start the stack using the account-entry
wrapper above, then provision the initial application administrator explicitly:

```powershell
python scripts/initial-admin.py --verify
```

The configurable username defaults to ADMIN. Its generated temporary credential
is private in .local/admin/initial-admin.json and must be changed on first login.
Existing administrators and changed passwords are preserved. The operator command
never resets an existing identity's password or automatically promotes an unrelated
identity. The new migration records ownership so interrupted setup can resume
without duplicating accounts. Ordinary service startup never resets credentials.

The combined browser wrapper now requires 24 cases, including admin navigation,
forced first-login password change, self-service password change, current-role
authorization and repeated provisioning safety. Runtime and provisioning approval
is required before these tests; only verified disposable identities are reset or
deleted. The dedicated initial account remains for manual review. See the S3
verification record for exact results, scope, private credential retrieval and limits.

## S4 account management (local acceptance verified)

The administrator account controls are at `/admin/accounts`. The people service
owns provisioning, current company access and audit history; GraphQL and every
protected page enforce current administrator authority. Creation and resets send
Keycloak activation/action links rather than exposing passwords.

The S4 development wrapper is
`python scripts/account-management-development.py up --apply-migration`.
Run it only after approving the migration, limited service
updates and local mailbox setup. Mailpit captures mail privately at
http://127.0.0.1:8025 with no external relay. Its SMTP port stays inside Compose.
Gmail sender: dailygotasks@gmail.com. Complete setup privately with
`python scripts/configure-email.py gmail`; use `python scripts/configure-email.py status`
to inspect the actual delivery mode. Google app passwords are entered with echo
disabled, never as command arguments or in chat. Email acceptance tests require
local capture and refuse to run against a live Gmail configuration. Gmail authentication and realm configuration passed; real inbox receipt still
needs verification. Credentials belong outside committed source.
See [S4 verification](docs/s4-verification.md) for actual evidence and gaps.

## S10 owner oversight

As ADMIN or the current MANAGER owner, open a project and choose Delivery oversight.
The page separates the original commitment, current approved deadline, forecast and
actual delivery. No planning data is fabricated: an empty escalation inbox and
“Not assessed” forecast are expected until the later task-planning workflow produces
inputs. Explicit leader absence requires a reason, scope, bounded dates and
confirmation; signing out never activates fallback.

After explicit runtime approval, use the repository-root wrappers:

```powershell
python scripts/owner-decisions-development.py up --apply-migration
python scripts/verify-owner-postgres.py
python scripts/run-s1-acceptance.py --project desktop --owner-decisions-only
python scripts/run-s1-acceptance.py --project tablet --owner-decisions-only
python scripts/run-s1-acceptance.py --project mobile --owner-decisions-only
```

These focused journeys send no email and verify removal of their owned fixtures.
The full lifecycle also includes email tests and therefore requires local mail
capture; it refuses to run against configured Gmail. See the S10 verification
record for actual results and pending review gates.

## S11 leader task breakdown

Open an assigned project and choose Work breakdown. Its current EMPLOYEE leader
can create tasks with instructions, acceptance criteria and one eligible assignee,
including themselves. Pending tasks can be edited or reassigned with a reason and
confirmation. The current owner and ADMIN have read-only oversight; contributors
see colleagues' summaries and only their own private task details. Removal of
membership immediately denies access without erasing history.

The approved local runtime and focused verification wrappers are:

```powershell
python scripts/task-breakdown-development.py up --apply-migration
python scripts/verify-tasks-postgres.py
python scripts/run-s1-acceptance.py --project desktop --tasks-only
python scripts/run-s1-acceptance.py --project tablet --tasks-only
python scripts/run-s1-acceptance.py --project mobile --tasks-only
```

Runtime updates require explicit approval. Focused tests use three receipt-owned
identities (owner, leader and contributor), send no email and verify exact cleanup.
No demonstration tasks or permanent test accounts are left in the portal. Task
scheduling, progress and completion review remain in their later planned stages.
