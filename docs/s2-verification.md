# S2 account entry and permission foundation

Date: 16 November 2026.
Status: READY FOR MANUAL COMMIT. Local S2 scope is implemented and verified.
Owner review, manual Git actions and remote CI remain. S3 has not started.

## Scope and policy decision

The owner confirmed one company role per account on 16 November 2026. The allowed
roles are ADMIN, MANAGER, EMPLOYEE and HR. An employee may later be appointed team
leader for a particular project; leadership is not a company role, and no global
TEAM_LEADER grant exists. HR project participation remains unresolved in the plan.
This implementation grants no project authority from a company role.

The authoritative Taskspace_Portal_Development_Plan.docx remains read-only and
unchanged (SHA-256 08af1dd1024824bbc91d7f0433e2e35e45db8b3e7084c9650edb99314199d6fd).
S3, initial company administrator provisioning and account-management UI have not
started. There are no placeholder portals or public role-management mutations.

## Boundaries delivered

- services/gateway: public FastAPI/Strawberry GraphQL API. Only the current viewer
  is exposed. Bearer tokens require RS256 signature, issuer, API audience, expiry,
  issued-at, subject, Bearer type and the authorized web client. No client actor ID
  or role header grants authority.
- services/people: private FastAPI service and independent token validation, plus
  a distinct constant-time checked gateway credential. Authoritative accounts,
  employee profiles and single company-role grants live in its own PostgreSQL
  database. An issuer/subject pair is unique; profile and role associations cannot
  duplicate an account. TEAM_LEADER is rejected by the database role constraint.
- packages/security: shared identity protocol validation only. It owns no database
  or role rules. Provider origin checks include host, scheme and port.
- apps/web: server-side GraphQL transport uses the existing opaque S1 session;
  tokens remain server-only. The confirmation page rechecks active account,
  profile and role on each request. Missing/inactive associations are denied;
  service failures do not create authenticated application authority.
- The GraphQL SDL is exported from the executable schema. Operation types and the
  actual request document are generated together. Schema/type drift is checked.

## Approved runtime scope

The owner approved adding gateway, people and people-db to the new portal project,
applying the initial migration to its separate fresh people database, recreating
only the new web service as required and configuring the exact existing new-realm
web client's API audience. Only owned disposable identities and application
account/profile records may be created/deleted by acceptance. Legacy data and
primary administrator stay intact. No local intentional outage was approved in
this S2 run.

compose.account-entry.yaml is an explicit override of the preserved S1 stack.
The root web-only Compose definition stays unchanged. New persistent data belongs
to taskspace-portals-development_portal_people_data. People and its database have
no host port; gateway uses loopback 8020. A separate private credential file is
created under .local/account-entry; root .env is not modified.

Migration upgrade runs inside the owned people service; there is no volume reset,
broad cleanup or destructive migration. The audience change affects only access
tokens for the verified new-realm web client; user credentials and roles are not
rewritten. The bootstrap administrator grant used for the mapper is revoked.

## Verification underway

Source tests cover account/profile inactivity and absence, issuer association,
role constraints, current-state changes without reissuing tokens, forged JWTs and
headers, direct GraphQL access, private service credentials, upstream failure,
exact provider origins, migration/model parity and committed schema parity.

The browser fixture verifies its exact disposable Keycloak identity against the
run receipt before creating a matching application account. Cleanup validates
account UUID, issuer, subject and profile UUID/name, removes only those exact
associations, verifies absence and preserves the bootstrap identity and grants.
The S2 browser case reuses the same session while account/profile state and role
change, then removes the account association and verifies denial.

Final executed results, failures and limitations will be recorded below. Skips
or discovery runs are not acceptance passes. All changes remain unstaged; Git
history actions belong to the owner.

## Executed results

| Check | Actual result |
| --- | --- |
| Backend source tests in a separate environment matching the new lockfiles | 46 passed; zero skips, including startup mapper regressions |
| Existing authentication unit/protocol tests | 21 passed; zero skips |
| Repository isolation/CI regressions | 13 passed; zero skips |
| PostgreSQL initial migration | Applied successfully to the new people database |
| PostgreSQL schema/model parity | Passed |
| PostgreSQL unique identity, one-role, foreign-key and role-value constraints | Passed; exact named constraints checked |
| PostgreSQL integration probe cleanup | All probes rolled back; exact IDs checked absent |
| Desktop complete authentication/account-entry journey | 6/6 passed; zero skips; one worker; zero retries |
| Tablet complete authentication/account-entry journey | 6/6 passed; zero skips; one worker; zero retries |
| Mobile complete authentication/account-entry journey | 6/6 passed; zero skips; one worker; zero retries |
| Focused S2 case after test transport correction | 1/1 passed; not substituted for full journeys |
| ESLint, TypeScript, app formatting, Python Ruff lint/format | Passed |
| Executable schema versus committed GraphQL SDL | Passed |
| Generated GraphQL request/types reproducibility | Passed; generation produced identical bytes |
| Web, gateway and people production image builds | Passed |
| Production app dependency audit | Zero known vulnerabilities |
| Gateway and people lockfile audits | Zero known vulnerabilities in each |
| Compose preflight, ports and ownership | Passed |
| Independent application-data cleanup check | Zero accounts, employee profiles or role grants remained |
| Scoped identity cleanup | All six S2-run receipts clean, including the failed attempts |
| Administrator/retained identity preservation | Fixture exact-ID checks passed; independent active-state checks passed |
| Administrator grant cleanup | Fixture, audience-configuration and independent diagnostic grants revoked |
| Services after browser runs | Seven new services healthy; legacy service IDs and health unchanged |
| Candidate-source scan | No local credential values or generated/private artifacts found |
| Git index | Unchanged; no staged changes |
| Immutable product plan | Original SHA-256 unchanged |

Machine-readable source evidence is in ignored test-results/reports/s2/backend.xml.
Combined browser reports are in ignored test-results/reports/s1/{desktop,tablet,mobile}-lifecycle.json;
the existing authentication runner now requires all six cases, exact seven-service
ownership and account cleanup in addition to its earlier identity/grant checks.
The focused case report is desktop-account-entry.json in the same directory.
A focus run, discovery or skipped test cannot stand in for a complete lifecycle.
The separate S2 CI source job and combined runtime job are mandatory in the
aggregate quality gate; all six legacy gates remain required. There are nine
required jobs plus the aggregate gate. No real-service outage was run locally.

## Failures diagnosed and corrected

The initial complete desktop attempt passed the five S1 cases and failed the new
S2 case. A focused reproduction identified TypeError: fetch failed in the test's
Node HTTP transport at the same-session role-change boundary. The reporter had
initially omitted assertion details; sanitized private diagnostics now include
fixed checkpoints, scrubbed error messages and source locations. Bearer tokens,
JWTs, credentials and raw protocol addresses are omitted.

The test now uses Playwright's request client, buffers responses and uses fresh
HTTP connections with zero transport retries. This avoids retaining unread error
responses or reusing idle connections in that fixture; the precise low-level
socket failure was not established by the original error. No authorization,
cleanup, status or same-session assertion was weakened, and no timeout changed.
The subsequent focused case and all three complete journeys passed. Cleanup was
verified even for both failed attempts. Sanitized failure records remain private
under .local/auth/failures; no failure is counted as a pass.

Early source checks found a test-header type mismatch and formatting issues;
these were corrected before the passing checks. The tested S2 Python environment
is separate from the pre-existing root environment and matches the service locks.

## Limits and manual handoff

Remote S2 CI and production deployment are not yet claimed. Local acceptance uses
HTTP on explicit loopback/private development boundaries; a deployed HTTPS journey
was not exercised. Existing S1 recovery evidence is historical; its CI opt-in
continues to test identity/session restoration on the extended stack, but no local
S2 outage was authorized or run. Unchanged legacy suites were not rerun locally;
their mandatory CI gates remain in place.

The full app development dependency audit reports 10 findings (nine moderate,
one high), compared with the eight previously recorded S1 development findings.
The two additional moderate entries are the GraphQL generation CLI and
its graphql-config dependency, through minimatch. Production app and both new
Python service dependency audits are clean. No broad audit-fix upgrade or
assertion suppression was applied. FastAPI's test client emits a deprecation
warning for the pinned httpx test transport; all source checks still pass.

The preserved manual-review Keycloak identity remains active. It is deliberately
not auto-associated with a company account/profile, so it now sees the restricted
entry view after successful authentication. A credentialed identity is distinct
from application authority. Persistent account provisioning and the initial
company administrator remain S3/S4 work; test associations are removed.

Review the source and this record, then stage, commit and push manually. Proposed
commit: feat: add S2 account entry and server authorization.
No branch, index, commit, push or PR action was performed. Do not start S3 until
S2 owner review and required remote CI evidence are complete.

## CI startup correction: imported audience mapper defaults

The supplied PR #26 CI attempt built the images and brought identity, its database,
the session store and people database to healthy state. It failed before the
"API audience verified" checkpoint. Eight other required jobs, including the
separate account-entry source job, passed; the aggregate gate correctly failed
because authentication runtime acceptance had not run.

A read-only inspection of the real provider representation reproduced a strict
configuration mismatch. Keycloak 26.7.5 adds introspection.token.claim=true and
userinfo.token.claim=false to the audience mapper; all three originally expected
configuration fields matched. The initial local setup created a missing mapper
and did not compare its readback, whereas a fresh CI realm already imported the
mapper and entered the failing exact-comparison branch.

Both the dedicated mapper manifest and embedded realm import now state those two
existing provider defaults explicitly. Exact comparison remains required; unknown
keys, duplicate named mappers, changed audiences or changed token claims are still
rejected. Mapper creation now reads back and validates the stored representation.
Known identity-configuration failures emit fixed diagnostic codes without provider
response bodies, credentials, raw protocol addresses or query parameters.

Verification of this correction:

- All 46 backend source tests passed with zero skips. Eleven new cases cover the
  original mismatch, fresh-import representation, repeated idempotent setup,
  six genuine configuration drifts, duplicate mappers, creation readback and
  invalid readback. Grant revocation is asserted on success and rejection.
- The real existing provider mapper passed setup twice without any mapper update;
  each temporary administrator grant was revoked.
- Full credentialed desktop journey passed 6/6 with zero skips, one worker and
  zero retries. Exact disposable identity/account cleanup, bootstrap preservation,
  seven healthy services and unchanged legacy IDs/health were verified.
- Ruff lint/format, all 13 structure tests and whitespace checks passed.
- Tablet/mobile evidence remains the earlier complete 6/6 runs; UI/application
  code did not change in this follow-up. No service rebuild, recreation, outage,
  migration, timeout change, role change or broad cleanup was performed.

The observed provider representation is retained privately in
.local/account-entry/audience-representation.json. The original CI failure is not
counted as a pass. A new remote run on the follow-up commit must prove fresh CI
startup and the full required acceptance/recovery scope before merge. The product
plan and Git index remain unchanged; these follow-up files remain unstaged.
