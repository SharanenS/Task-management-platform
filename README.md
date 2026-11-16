# Taskspace

Taskspace is being rebuilt as a portal-oriented corporate project and employee
management platform using Next.js, React, TypeScript, Python, FastAPI, Strawberry
GraphQL, PostgreSQL, Keycloak, Redis, RabbitMQ and Celery where required.

S0 source isolation is merged. S1 introduces a new authentication experience.
S1 is locally verified; owner review and remote CI remain. See
docs/s1-verification.md for actual evidence.
Company-role access and functional portals are later stages.

## Source layout

| Path | Responsibility |
| --- | --- |
| apps/web | Independent authentication interface and server-side session boundary |
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

The S1 development origin is http://127.0.0.1:3020. Authentication also requires
the separate identity and session services. Do not run an additional development
server on that port while the web container owns it.
The authentication wrapper uses local private credentials without changing .env.
Starting the stack requires explicit runtime approval; see docs/s1-verification.md.

## Execution isolation

The root compose.yaml declares only the new web application and uses the independent
project name taskspace-portals-development. It creates no database, queue,
worker, identity realm or session store. Do not launch it as part of source review.

The existing stack remains under its original project name
enterprise-task-platform-phase2. Its definition is legacy/compose.yaml.
Its running frontend at port 3010 is the legacy application.
The approved S1 authentication stack uses a separate realm, identity database
and session store. Legacy accounts and data remain untouched.

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

Git history and GitHub changes remain manual owner actions. S1 starts only after
S0 review and explicit authorization.

## S1 verification entrypoints

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
python scripts/auth-development.py preflight
python scripts/auth-development.py up
python scripts/auth-development.py status
python scripts/run-s1-acceptance.py --project desktop
python scripts/run-s1-acceptance.py --project tablet
python scripts/run-s1-acceptance.py --project mobile
python scripts/run-s1-acceptance.py --project desktop --recovery
```

The recovery opt-in stops only the new identity and session services, one at a
time. Both the test and wrapper verify restoration. The wrapper then repeats the
full credentialed desktop lifecycle. No command deletes persistent volumes.
