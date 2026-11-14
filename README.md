# Taskspace

Taskspace is being rebuilt as a portal-oriented corporate project and employee
management platform using Next.js, React, TypeScript, Python, FastAPI, Strawberry
GraphQL, PostgreSQL, Keycloak, Redis, RabbitMQ and Celery where required.

S0 establishes source isolation and reproducible verification. Authentication
begins in S1. No replacement portal or sign-in workflow is claimed in S0.

## Source layout

| Path | Responsibility |
| --- | --- |
| apps/web | Independent new application with an honest preparation page |
| legacy/frontend | Accepted baseline frontend used by historical verification |
| legacy/experiments/portal-web | Preserved uncommitted portal experiment; not the replacement app |
| legacy | Preserved services, tests, scripts and historical records |
| infrastructure | Existing operational configuration retained for the running legacy stack |
| scripts | S0 source and build verification |
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

The optional local development command is npm --prefix apps/web run dev.
Its default port is 3020 and it displays only the S0 preparation page.
S0 verification does not start that server automatically.

## Execution isolation

The root compose.yaml declares only the new web scaffold and uses the independent
project name taskspace-portals-development. It creates no database, queue,
worker, identity realm or session store. Do not launch it as part of source review.

The existing stack remains under its original project name
enterprise-task-platform-phase2. Its definition is legacy/compose.yaml.
Its running frontend at port 3010 is the legacy application.
New authentication and data will use a separate environment after authorization.

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
