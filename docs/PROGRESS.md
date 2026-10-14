# Project progress

Last updated: 2026-10-14

## Phase 1 — Project Foundation and Frontend Design System

Status: **Accepted**

Delivered:

- Responsive Next.js application shell and reusable interface states.
- Clearly labeled demonstration dashboard content.
- Live GraphQL System Status and interactive Design System pages.
- FastAPI and Strawberry gateway with `systemInfo`, health endpoints, bounded
  query complexity, sanitized failures, and generated client types.
- Docker, automated, browser, accessibility, outage, and recovery verification.

## Phase 2 — Authentication and Real Application Shell

Status: **Accepted**

Delivered:

- Keycloak Authorization Code Flow with PKCE, strict state and nonce validation,
  exact redirect targets, disabled registration, and a reproducible realm.
- Redis-backed server sessions with opaque cookies, CSRF-protected logout, a
  distributed refresh lock, and explicit expiry and failure states.
- Protected shell with Employee Service-backed identity and role-aware navigation.
- Same-origin GraphQL transport that supplies access tokens only on the server.
- Gateway JWT signature and claim validation plus authenticated `me` composition.
- Employee Service with owned PostgreSQL database, Alembic migration, stable
  Keycloak-subject link, application role, and active access status.
- Development-only identity/profile bootstrap with credentials held in `.env`.
- Unit, integration, and opt-in Docker-backed browser coverage.

Acceptance completed on 2026-10-14. Automated, Docker-backed, end-to-end, and
manual checks passed. The final development dependency audit records 12
high-severity `braces` findings in repository-controlled code-generation and lint
tooling; the production dependency audit reports zero vulnerabilities. Phase 3 has
not started.
