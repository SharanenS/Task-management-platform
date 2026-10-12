# Phase 1 verification — 2026-10-12

Status: **Accepted**

Phase 1 delivers the project foundation, responsive application shell, reusable
interface states, FastAPI and Strawberry GraphQL gateway, typed frontend GraphQL
integration, health endpoints, and a two-service Docker Compose environment.

## Acceptance review

The complete browser acceptance checklist passed on 2026-10-12:

- Docker Desktop updated successfully.
- Both Phase 1 containers reported healthy.
- The application loaded successfully at `http://localhost:3010`.
- The browser console remained clean.
- The real GraphQL `systemInfo` request succeeded.
- Overview, System Status, and Design System pages behaved as specified.
- Layouts passed at 768 px and 390 px viewport widths.
- No unwanted page-level horizontal overflow was present.
- Desktop and mobile keyboard navigation passed.
- Focus states were visible.
- Mobile navigation opened correctly and Escape dismissed it with focus restored.
- Stopping the gateway produced the correct unavailable state.
- Error and Retry states behaved correctly.
- Gateway recovery succeeded without restarting the frontend.
- Demonstration content was clearly identified and could not be mistaken for
  connected business data.

## Automated verification

The original Phase 1 automated verification passed:

| Check | Result |
| --- | --- |
| Gateway Pytest suite | 7 passed |
| Ruff lint and formatting | Passed |
| mypy strict checks | Passed for all application modules |
| GraphQL Code Generator | Schema and operation documents generated successfully |
| ESLint | Passed |
| TypeScript | Passed |
| Prettier | Passed |
| Vitest | 4 passed |
| Playwright desktop/mobile | 6 passed |
| Real Docker outage test | 1 passed |
| Production frontend build | Passed |
| Docker Compose build and health checks | Passed |
| Production npm audit | No reported production dependency vulnerabilities |

A final repository-readiness verification was initiated on 2026-10-12. Its exact
results are recorded below after execution.

### Final repository-readiness verification

- Gateway schema export: passed.
- Frontend GraphQL code generation: passed.
- Gateway tests: 7 passed.
- Gateway lint: passed.
- Gateway formatting check: passed for 6 files.
- Gateway type check: passed for 4 source files.
- Frontend lint: passed.
- Frontend type check: passed.
- Frontend unit and component tests: 4 passed.
- Frontend formatting check: passed.
- Frontend production build: passed; 5 static routes generated.
- Production frontend dependency audit: no vulnerabilities reported.
- Browser tests: 6 passed across desktop and mobile projects; 2 opt-in recovery variants skipped by the standard run.
- Explicit gateway recovery browser test: 1 passed.
- Docker Compose configuration validation: passed.
- Production container image builds: frontend and gateway passed.
- Running containers: frontend and gateway healthy.
- Frontend HTTP check: `http://localhost:3010` returned HTTP 200 with HTML content.
- Public GraphQL check: `systemInfo` returned the expected application identity, version, environment, and `AVAILABLE` status.

### Workspace-root reproducibility

Next.js 16.4.0 initially warned that a package lock outside the repository could
cause it to infer an incorrect workspace root. The frontend configuration now
sets `turbopack.root` to the directory containing `next.config.ts`, resolved at
runtime without a machine-specific path. This resolves to the frontend directory
for local commands and to `/app` in the existing container build context.

Final verification after this change:

| Command | Result |
| --- | --- |
| `npm run typecheck` | Passed |
| `npm run lint` | Passed |
| `npm run build` | Passed; 5 static routes generated and no unrelated-lockfile warning appeared |
| `docker compose build` | Passed for the frontend and gateway; no unrelated-lockfile warning appeared |

## Dependency review

The production frontend dependency audit previously reported no vulnerabilities.
The development dependency tree has a documented upstream `braces` advisory; see
[dependency review](dependency-review.md). The affected packages are build and
repository tooling and do not process public application requests in Phase 1.

## Scope boundary

Phase 1 is accepted. Authentication, protected routes, user sessions, Keycloak
integration, and role-aware navigation belong to Phase 2 and have not been started.

No repository history or remote operation is part of Phase 1 acceptance. Review
and publication remain separate repository-owner actions.
