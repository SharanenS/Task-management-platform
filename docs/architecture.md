# Architecture decisions — Phases 1–4

## Fixed boundaries

One company is deployed per stack. There is no tenancy or public registration.
GraphQL is the only public business API. Health, OIDC callback, logout, and
infrastructure endpoints are explicit HTTP exceptions. The gateway owns no domain
data. Employee, Work Management, Workflow, and Job Execution remain independent
bounded services, each with its own database and migrations when introduced.

Employee Service and Work Service are implemented. Workflow, queues, and job
execution remain outside Phase 4.

## Project management

Work Service owns project metadata, lifecycle state, membership roles, optimistic
versions, and its PostgreSQL schema. It has no host-published business endpoint;
the gateway is the only public project API. The service-to-service credential is
separate from the Employee Service credential.

Before every project query or mutation, the gateway validates the access token and
reloads the actor's current Employee Service profile. Inactive or missing profiles
fail closed. Work Service independently applies application-role and project-role
rules from the asserted actor identity. An `ADMIN` may view and govern all projects;
a `MANAGER` may create projects and administer projects where they are a project
manager; contributors have read-only access to their projects.

Projects move from `DRAFT` to `ACTIVE` to `ARCHIVED`, with reactivation from
`ARCHIVED` to `ACTIVE`. Archived projects are read-only until reactivated. There
is no public hard-delete operation. Version checks reject stale metadata and
lifecycle updates, and the final project manager cannot be demoted or removed.

Employee Service remains the source for eligible active employee profiles. Its
internal project-member endpoints expose only stable ID, display name, and email.
The gateway validates an employee before adding a membership and resolves project
responses through one bounded Employee Service batch per GraphQL operation. Work
Service stores only the stable employee ID and never copies employee-owned profile
data. Missing or newly inactive profiles fail closed for selection and render as
unavailable in an existing membership response.

## Task management

Work Service owns tasks, project-scoped numbering, assignment, lifecycle,
comments, and append-only activity in the existing Work PostgreSQL schema. The
Phase 5 migration follows the accepted Phase 4 revision. Project row locking plus
a unique `(project_id, number)` constraint makes task references concurrency-safe;
task row locks and optimistic versions serialize competing mutations.

The task state machine permits `TODO` to move to `IN_PROGRESS`, `BLOCKED`, or
`CANCELLED`; `IN_PROGRESS` to move to `TODO`, `BLOCKED`, `DONE`, or `CANCELLED`;
`BLOCKED` to move to `TODO`, `IN_PROGRESS`, or `CANCELLED`; `DONE` to reopen as
`IN_PROGRESS`; and `CANCELLED` to reopen as `TODO`. Archived projects reject all
task writes while preserving readable task, comment, and activity history.

Application administrators manage tasks everywhere. Project managers manage every
task in their projects. Contributors may create tasks and comments and may change
status only on tasks assigned to them. Non-members cannot infer task data. The
gateway reloads the current Employee profile before every operation and validates
an active assignee; Work Service independently rechecks current project membership
inside the assignment transaction.

Comments are immutable plain text. Activity records use a constrained activity
type and non-sensitive structured change data and are committed atomically with
the related Work mutation. Task, comment, and activity responses resolve Employee
references in bounded batches. The board uses a bounded query per status lane and
reports `hasMore`; it never loads the full task collection into the browser.

## Employee administration

The public GraphQL gateway is the only employee-administration API. It validates
the bearer token, reloads the actor's current Employee Service profile for every
administrative operation, and requires an active `ADMIN`. Employee Service repeats
the authorization check and owns directory queries, profile data, application
roles, active status, idempotency records, and reconciliation state. Its internal
HTTP endpoints require the existing service credential and are not host-published.

Keycloak remains the source of identity and credentials. Employee Service uses a
dedicated confidential service-account client; the browser never receives its
secret or administrative token. The bootstrap assigns only `manage-users`,
`view-users`, and `query-users`. Calls use a bounded timeout and translate upstream
details to fixed domain errors.

Provisioning records an idempotency key, creates a disabled owned Keycloak user,
persists the profile linked by stable subject, then enables the identity. Temporary
credentials stay only in Keycloak and require replacement at first login. A failed
cross-system step leaves access disabled and records `RECONCILIATION_REQUIRED`.
Reconciliation safely restores agreement before a separate activation when needed.
Role and status changes prevent self-lockout and removal or deactivation of the
final active administrator. Repeated status requests are idempotent.

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
Employees navigation entry is visible only to an `ADMIN`. Phase 3 enforces
administrative authorization independently at both the gateway and Employee Service
boundaries; hidden navigation is only a presentation rule.

## Development bootstrap and persistence

The committed Keycloak realm contains a public PKCE client, exact local redirect,
logout, and origin values, an audience mapper, and no users or usable secrets.
Public registration is disabled. `scripts/bootstrap-development.ps1` reads only
the ignored local `.env`, creates or updates a development Keycloak user, obtains
its stable subject, and invokes an internal Employee Service bootstrap command.

Keycloak, Employee Service PostgreSQL, Work Service PostgreSQL, and Redis each use
a distinct named volume.
Readiness checks verify database connectivity or service endpoints before dependent
containers start. Host-published ports bind to loopback.

## Threats and mitigations

| Threat                                | Mitigation                                                                                 |
| ------------------------------------- | ------------------------------------------------------------------------------------------ |
| Authorization response substitution   | One-time state, nonce, PKCE, and transaction expiry                                        |
| Token theft by browser script         | Opaque `HttpOnly` session; tokens remain server-side                                       |
| Open redirect                         | Strict relative return-path validation and exact registered URIs                           |
| Cross-site logout                     | Cookie, request header, and session CSRF values must match                                 |
| Refresh storm                         | Redis distributed lock with expiry                                                         |
| Forged gateway identity               | JWT signature and required claim validation                                                |
| Spoofed employee lookup               | Internal endpoint credential and unexposed service port                                    |
| Identity without application access   | Employee profile and active status are mandatory                                           |
| Information leakage                   | Sanitized HTTP and GraphQL failures; sensitive values are not logged                       |
| Unauthorized project access           | Current Employee profile reload plus Work Service project-role enforcement                 |
| Forged internal project actor context | Unexposed Work endpoint, dedicated service credential, and validated gateway actor context |
| Membership race or orphaned project   | PostgreSQL constraints, locked mutations, version checks, and final-manager protection     |
| Work Service information leakage      | Sanitized gateway mapping and bounded internal client behavior                             |

## Dependency choices

`openid-client` implements the standards-sensitive authorization, token, and ID
token processing while the application retains transaction storage, cookie policy,
session lifecycle, authorization, and error handling. The official Redis client
supports durable shared sessions and atomic lock acquisition. PyJWT performs strict
gateway JWT validation with cached JWKS lookup. SQLAlchemy, Alembic, and psycopg
provide explicit Employee Service and Work Service ownership of their respective
models, migrations, and PostgreSQL schemas.
