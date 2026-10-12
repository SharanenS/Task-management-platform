# Enterprise Task Platform

A GraphQL-first enterprise work platform, developed in verified full-stack slices.
**Current scope: Phase 1 — Project Foundation + Frontend Design System.**

The Taskspace interface contains a responsive dashboard shell, explicit sample
content, a live GraphQL connection screen, and interactive component previews.
Authentication and business features arrive in later phases.

## Run with Docker

Start Docker Desktop with Linux containers, then from the repository root:

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose ps
```

Open http://localhost:3010. Live diagnostics: http://localhost:3010/system.
Gateway development explorer: http://localhost:8010/graphql.
Health endpoints: `/health/live` and `/health/ready` on port 8010.
GET GraphQL queries are disabled; use POST or the development explorer.

```powershell
docker compose logs --tail 100
docker compose stop gateway
# In the browser, refresh status to verify the unavailable state.
docker compose start gateway
# Retry to verify recovery.
docker compose down
```

Compose is a local development verification environment, not an AWS deployment.
The frontend image runs an optimized production build. Rebuild after source edits.
There are no persistent volumes or databases in Phase 1.
The isolated Compose name is `enterprise-task-platform-phase1`. Ports 3010/8010
avoid the older local project on 3000/8000. Override host ports in `.env` if needed.

## Run natively on Windows

Prerequisites: Node.js 24.15 or newer in the Node 24 LTS line, Python 3.13, npm 11.21+.
Run from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r gateway/requirements.lock
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir gateway --host 127.0.0.1 --port 8010 --no-access-log
```

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://localhost:3010. Native development defaults to gateway port 8010.
If needed, copy `frontend/.env.example` to `frontend/.env.local` and edit the
server-side `GATEWAY_URL`. Restart Next.js after changing it. Root `.env` controls
Compose and gateway settings; it is ignored by Git.

## Verify

From the repository root:

```powershell
cd gateway
..\.venv\Scripts\python.exe export_schema.py
..\.venv\Scripts\python.exe -m pytest
..\.venv\Scripts\python.exe -m ruff check .
..\.venv\Scripts\python.exe -m ruff format --check .
..\.venv\Scripts\python.exe -m mypy app
cd ../frontend
npm run codegen
npm run lint
npm run typecheck
npm test
npm run format:check
npm run build
```

With both servers running (native or Compose):

```powershell
npx playwright install chromium
npm run test:e2e
```

The real container-outage test is opt-in and must run by itself against the default
Compose ports. It stops only this project's gateway and restarts it in a `finally`
block:

```powershell
$env:RUN_DOCKER_RECOVERY="1"
npx playwright test docker-recovery --project=desktop --workers=1
Remove-Item Env:RUN_DOCKER_RECOVERY
```

Generated TypeScript files are included in the source for reproducible builds. After schema
changes, regenerate both SDL and client documents and review the diff. Never
manually duplicate response types. The schema consistency test detects stale SDL.

## Repository

| Directory | Responsibility |
| --- | --- |
| `frontend/` | Next.js App Router, Tailwind, UI components, generated GraphQL client |
| `gateway/` | FastAPI + Strawberry, safe metadata, health checks, tests |
| `services/` | Documented future service boundaries; no running domain services yet |
| `docs/` | Architecture decisions and phase acceptance |

Read [architecture decisions](docs/architecture.md) and the
[manual acceptance checklist](docs/phase-1-acceptance.md).
See the [dependency review](docs/dependency-review.md) for the known development
tooling advisory and production audit result.
Actual implementation checks are recorded in the [verification report](docs/phase-1-verification.md).

The final architecture has four independently deployable domains, each with its
own PostgreSQL database. Keycloak handles authentication; RabbitMQ and Celery
handle asynchronous transport/execution. These components are intentionally
introduced only as their functional phases require them.
