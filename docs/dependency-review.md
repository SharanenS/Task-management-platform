# Dependency review — 2026-10-14

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
The gateway, Employee Service, and Work Service Python locks reported no known
vulnerabilities when checked with `pip-audit` 2.10.1.

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
`gateway/requirements.lock`, `services/employee/requirements.lock`, and
`services/work/requirements.lock`; these locks include verification tooling and
are also used by local containers. `services/work/requirements.in` records its
direct dependencies; the lock contains the independently resolved pinned versions.
Work Service uses the same reviewed FastAPI, SQLAlchemy, Alembic, psycopg,
Pydantic, and Uvicorn package families as Employee Service, so Phase 4 introduces
no new Python package family. Production image slimming and separate production
dependency locks are deferred to deployment work.
