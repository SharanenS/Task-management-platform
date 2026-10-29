# Dependency review — 2026-10-21

The Phase 1 npm audit reported 12 high-severity development dependency entries stemming
from [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm).
`braces <=3.0.3` can exhaust the stack when parsing deeply nested patterns. The
paths are GraphQL Code Generator and Next.js ESLint tooling, which consume
repository-controlled patterns here. They do not accept public request input.

The Phase 2 final audit on 2026-10-14 reported zero production vulnerabilities.
The full development audit still reported 12 high-severity entries through `braces`
in GraphQL Code Generator and Next.js ESLint dependency paths. npm offered only a
forced, breaking downgrade of GraphQL Code Generator, so the finding remains
documented with the repository-controlled input constraint above.
The Gateway, Employee Service, Work Service, and Job Service Python locks reported
no known vulnerabilities when every pinned package was checked with `pip-audit`
2.10.1. This includes the locked Celery transport dependency chain.

The Phase 9 audit identified `PYSEC-2026-4320` in the previously pinned
`certifi 2026.7.22`. Gateway, Employee Service, and Job Service locks now pin the
fixed `certifi 2026.10.19`; all four Python locks then reported no known
vulnerabilities. The production npm audit remains clean, while the full audit
retains the 12 documented development-only `braces` findings above.

Phase 2 adds `openid-client` 6.8.8 and `redis` 6.3.0. `openid-client` was selected
for standards-compliant Authorization Code, PKCE, ID-token, and refresh processing;
the application still owns cookie policy, server session storage, CSRF defense,
return-path validation, authorization, and sanitized failures. The official Redis
client provides the shared session store and atomic refresh lock.

The gateway adds PyJWT 2.15.1 with cryptography support for strict RS256/JWKS claim
validation. The Employee Service uses SQLAlchemy 2.1.4, Alembic 1.20.0, and psycopg
3.3.6 for its owned PostgreSQL model and migrations. Python versions are pinned in
service-specific lock files.

Node 24 LTS is required by the current toolchain. `.nvmrc`, the npm engine
constraint, and Docker images agree on that major version. Direct npm dependencies
and transitive resolutions are locked. Python dependencies are pinned in
`gateway/requirements.lock`, `services/employee/requirements.lock`,
`services/work/requirements.lock`, `services/job/requirements.lock`, and
`services/workflow/requirements.lock`; these locks include verification tooling and
are also used by local containers. `services/work/requirements.in` records its
direct dependencies; the lock contains the independently resolved pinned versions.
Work Service uses the same reviewed FastAPI, SQLAlchemy, Alembic, psycopg,
Pydantic, and Uvicorn package families as Employee Service, so Phase 4 introduces
no new Python package family. Production image slimming and separate production
dependency locks are deferred to deployment work.

Job Service uses the same reviewed FastAPI, SQLAlchemy, Alembic, psycopg,
Pydantic, and Uvicorn package families. Phase 6 introduces no new Python package
family.

Phase 7 adds Celery 5.6.3, Kombu 5.6.2, AMQP 5.4.1, and HTTPX 0.28.1 to the Job
Service lock. Celery and Kombu provide the dedicated JSON-only worker and durable
RabbitMQ routing; HTTPX provides bounded internal Employee and Work requests.
RabbitMQ 3.13.7 is pinned to the locally verified immutable image digest
`sha256:606d8c0d6b3c18d1da9afc53bc7cdb2a8d5486df91b5a9830e9e07626c9ae281` without
publishing broker or management ports. The management interface remains
unreachable from the host.

Phase 10 reuses the reviewed FastAPI, SQLAlchemy, Alembic, psycopg, Pydantic,
HTTPX, Kombu, and AMQP package families. Workflow Service has its own pinned lock;
Work Service adds Kombu and its AMQP transport dependencies for the dedicated
task-event publisher. No new frontend dependency was introduced.
