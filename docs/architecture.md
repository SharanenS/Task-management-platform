# Architecture decisions — Phases 1 and 2

## Fixed boundaries

One company is deployed per stack. There is no tenancy or public registration.
GraphQL is the only public business API. Health, OIDC callback, logout, and
infrastructure endpoints are explicit HTTP exceptions. The gateway owns no domain
data. Employee, Work Management, Workflow, and Job Execution remain independent
bounded services, each with its own database and migrations when introduced.

Phase 2 implements only the Employee Service. Work administration, workflow,
queues, and job execution remain outside this phase.

## Browser and session boundary

Next.js acts as a backend for frontend. A cryptographically random opaque session
identifier is stored in an `HttpOnly`, `SameSite=Lax`, path-wide cookie. Production
HTTPS enables `Secure`. Access, refresh, and ID tokens are stored only in Redis
under an eight-hour session TTL. A separate browser-readable random CSRF value is
matched against both a request header and the server session for logout.

Protected page middleware performs the inexpensive cookie-presence redirect. The
server layout then loads and validates the authoritative session. A missing or
unrefreshable session goes to the explicit session-expired page. Client JavaScript
receives only the employee profile and CSRF value; it never receives tokens.

## OIDC flow

Sign-in creates cryptographically secure state, nonce, PKCE verifier, and one-time
transaction identifiers. The transaction is stored in Redis for ten minutes, and
its opaque identifier is placed in an `HttpOnly` callback-scoped cookie. Callback
processing atomically consumes the transaction, then `openid-client` validates the
authorization response, issuer-bound ID token, state, nonce, and PKCE exchange.
Return paths must begin with one slash and cannot begin with two, preventing an
external redirect.

The browser-visible issuer is `http://localhost:8080/realms/taskspace`. Containers
cannot use the browser hostname to reach Keycloak, so server-side token and JWKS
requests use `http://keycloak:8080`. Token validation always requires the public
issuer exactly. Plain HTTP is allowed only when an explicit local setting is true
and the issuer host is loopback. Production configurations require HTTPS.

Expired access tokens are refreshed server-side. A Redis `NX` lock with a short
TTL allows one refresh per session and prevents refresh storms. A waiter reloads
the updated record. Refresh failure deletes the local session. Logout first deletes
the Redis session and cookies, then returns an exact Keycloak end-session URL with
the configured post-logout redirect.

## Gateway and Employee Service

The public gateway validates RS256 access-token signatures through a cached JWKS
client and requires issuer, audience, expiration, issued-at, and subject claims.
Key rotation is supported by key-ID lookup and cache refresh. The gateway calls
the Employee Service with the validated subject and a constant-time checked
internal service credential. It never persists employee data.

The Employee Service owns UUID, unique Keycloak subject, email, display name,
application role (`ADMIN`, `MANAGER`, or `MEMBER`), active status, and timestamps.
Its PostgreSQL schema is owned by Alembic. Missing and inactive profiles both deny
access without revealing which condition occurred. The internal endpoint is not
published to the host.

The GraphQL `me` query returns only ID, display name, email, and application role.
Missing or invalid authentication maps to `UNAUTHENTICATED`; a missing or inactive
profile maps to `FORBIDDEN`; a dependency failure maps to `SERVICE_UNAVAILABLE`.
Messages are sanitized. The existing public `systemInfo` query remains available.

## Same-origin GraphQL transport

The frontend `/graphql` route forwards the request body to the public gateway. If
a valid session exists, the route adds its bearer access token server-side. The
route preserves GraphQL as the single business contract and adds no REST business
operations. The authenticated shell uses Employee Service-backed `me` data. The
Employees navigation entry is visible only to an `ADMIN`; server-side enforcement
remains mandatory when Phase 3 operations are added.

## Development bootstrap and persistence

The committed Keycloak realm contains a public PKCE client, exact local redirect,
logout, and origin values, an audience mapper, and no users or usable secrets.
Public registration is disabled. `scripts/bootstrap-development.ps1` reads only
the ignored local `.env`, creates or updates a development Keycloak user, obtains
its stable subject, and invokes an internal Employee Service bootstrap command.

Keycloak, Employee Service PostgreSQL, and Redis each use a distinct named volume.
Readiness checks verify database connectivity or service endpoints before dependent
containers start. Host-published ports bind to loopback.

## Threats and mitigations

| Threat | Mitigation |
| --- | --- |
| Authorization response substitution | One-time state, nonce, PKCE, and transaction expiry |
| Token theft by browser script | Opaque `HttpOnly` session; tokens remain server-side |
| Open redirect | Strict relative return-path validation and exact registered URIs |
| Cross-site logout | Cookie, request header, and session CSRF values must match |
| Refresh storm | Redis distributed lock with expiry |
| Forged gateway identity | JWT signature and required claim validation |
| Spoofed employee lookup | Internal endpoint credential and unexposed service port |
| Identity without application access | Employee profile and active status are mandatory |
| Information leakage | Sanitized HTTP and GraphQL failures; sensitive values are not logged |

## Dependency choices

`openid-client` implements the standards-sensitive authorization, token, and ID
token processing while the application retains transaction storage, cookie policy,
session lifecycle, authorization, and error handling. The official Redis client
supports durable shared sessions and atomic lock acquisition. PyJWT performs strict
gateway JWT validation with cached JWKS lookup. SQLAlchemy, Alembic, and psycopg
provide explicit Employee Service ownership of models, migrations, and PostgreSQL.
