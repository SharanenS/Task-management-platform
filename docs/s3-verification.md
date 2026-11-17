# S3 admin shell and initial account

Date: 16 November 2026.
Status: READY FOR MANUAL COMMIT. Local S3 scope is implemented and verified.
Owner review, manual Git actions and remote CI remain. S4 has not started.

## Delivered scope

The new administrator portal provides /admin, /admin/profile and /admin/security,
with responsive navy/cyan navigation, keyboard focus/skip navigation, current
account details and secure sign-out. Only implemented destinations appear.
There are no fake business metrics, future portal links or imports of the old UI.
Company ADMIN accounts route into the portal after authentication; other company
roles retain their S2 entry behavior until their own functional stages.

Every protected page checks current administrator access on the server, including
the page itself rather than relying only on a potentially reused layout. Public
GraphQL adminWorkspace requires admin:workspace:read; the people service separately
checks the active account/profile, single ADMIN company role and verified bearer.
Forged role/actor headers do not grant access. The new capability grants no project
membership or project-specific leadership authority.

The security page starts the provider-supported UPDATE_PASSWORD action using a
POST with exact Origin checks, new state/nonce/PKCE and a fixed implemented return
route. The transaction is bound to the current verified subject, preventing the
callback from replacing that session with another identity. Passwords are entered
only at the identity provider. Unsupported action destinations and malformed
subject bindings are rejected. A cancelled action is not presented as a password
change success. The supported protocol is documented in the official
[Keycloak 26.7.5 administration guide](https://www.keycloak.org/docs/26.7.5/server_admin/index.html).

## Initial administrator provisioning

The owner approved a dedicated ADMIN login, a generated strong temporary password
and required first-login password change. Keycloak canonicalizes the username to
admin; ADMIN is the configured login name. The existing review identity was not
promoted. The Keycloak setup administrator remains a distinct operational account.

Provisioning is an explicit operator command: python scripts/initial-admin.py --verify.
Ordinary service startup does not create or reset credentials. The operator command
verifies the exact owned people container, passes secrets through standard input
rather than command arguments and revokes each temporary provider administrator
grant. Runtime API processes receive no permanent provider administrator secret.

Migration 0002_initial_admin adds only durable provisioning ownership/state. A
PostgreSQL advisory lock serializes initial provisioning. Before a new identity is
created, its operation UUID, canonical username, unique email marker and creation
window are committed. An interrupted response can resume only a matching owned
identity. An unrelated existing username is neither adopted nor promoted. Account,
profile, company ADMIN role and completed state are committed together.

Existing application administrators are inspected and preserved. Their credentials
are never written; there is no existing-password reset operation in the provisioner.
An inactive administrator, disabled identity, changed pending request or completed
bootstrap whose administrator was removed requires review instead of silently
creating, reactivating or escalating another account.

Initial credentials live only in ignored .local/admin/initial-admin.json with
restricted permissions on Unix. They are initial credentials, not a current-password
store after the user changes the password. No password or provider token appears
in committed source, reports or screenshots. Root .env was not modified.

## Approved runtime and actual persistent data

The owner approved the new provisioning-state migration, updates to only web,
gateway and people, scoped tests and creation of the dedicated initial account.
No identity/session/database service was intentionally stopped, no volume was
removed and no legacy data or source was changed.

After browser fixture cleanup, independent SQL checks found zero application
accounts, profiles, roles or provisioning operations. A two-connection PostgreSQL
check proved the actual provisioning lock excludes a second connection and releases
correctly. The explicit fresh-provisioning command then created the approved ADMIN;
its repeated invocation returned the same identity/account without another create.

Independent final checks found exactly one active application administrator,
one associated profile and one ADMIN role, with matching COMPLETE provisioning
state. The provider still requires UPDATE_PASSWORD for that dedicated identity;
its password change remains for the owner to perform manually. The retained review
identity and active Keycloak bootstrap administrator were independently preserved.
The diagnostic grant used for this verification was revoked.

## Executed verification

| Check | Actual outcome |
| --- | --- |
| Backend authorization/provisioning/schema/migration source suite | 57 passed; zero skips |
| Authentication unit/protocol suite | 22 passed; zero skips |
| Repository/CI boundary regression suite | 14 passed; zero skips |
| Full desktop lifecycle including S1/S2/S3 | 7/7 passed; zero skips |
| Full tablet lifecycle including S1/S2/S3 | 7/7 passed; zero skips |
| Full mobile lifecycle including S1/S2/S3 | 7/7 passed; zero skips |
| Focused S3 case | Passed after correcting a provider input assertion |
| Non-admin direct page and GraphQL requests | Denied, including forged actor/role headers |
| Temporary credential gate | No app session before required password change; portal reached afterward |
| Self-service password change | Reauthentication and subject-bound callback completed |
| Password preservation | Repeated provisioning preserved changed disposable-admin credentials; prior password rejected and new password accepted |
| Role revocation with existing session | Admin page and direct GraphQL access denied |
| Scope and privacy | Owned identity/account checks; no future or legacy navigation; no horizontal overflow |
| Migration/model parity and PostgreSQL constraints | Passed; rollback-owned probes checked absent |
| Actual provisioning concurrency lock | Exclusive across two real connections; release checked |
| Fresh initial administrator and idempotence | Created once; exact identity/account preserved on repeat |
| Production web/gateway/people builds | Passed |
| ESLint, TypeScript, Prettier and Python Ruff | Passed |
| GraphQL SDL and generated operations | Schema parity and generation checks passed |
| Production npm audit | Zero known vulnerabilities |
| Gateway/people dependency lock audits | Zero known vulnerabilities in each |
| Visual review | Overview, profile and security layouts inspected; desktop/tablet/mobile captures retained privately |
| Scoped fixture cleanup | Identities, profiles, roles, sessions/transactions and operator grants verified |
| Final services | Seven new services healthy; legacy service IDs/health unchanged in acceptance runs |
| Git index and product document | Unchanged; all changes unstaged |

Machine-readable backend evidence is in ignored test-results/reports/s2/backend.xml.
Combined browser reports remain in test-results/reports/s1/{desktop,tablet,mobile}-lifecycle.json;
the runner now requires all seven cases with zero skips. The focused admin report
is desktop-admin.json. A focused run is not substituted for the full journeys.
Credential-free captures live under .local/admin/screens/<run UUID>/<viewport>.
No capture includes provider credential forms.

## Failures diagnosed during implementation

Early source checks caught fixture discovery, schema snapshot and TypeScript
control-flow issues; these were corrected before passing verification.
The first live S3 focus run reached the admin interface and completed its first
required password change, then failed because its helper read textContent from
Keycloak's read-only remembered-username input. The helper now checks the exact
input value, retaining identity verification. Cleanup passed even on that failure;
sanitized checkpoints and errors are retained privately under .local/auth/failures.

Visual inspection also found an early profile capture still showed Overview:
the navigation assertion matched the Overview card's h3. The test now requires
the exact level-one page heading and completed /admin/profile URL before capture.
All three full journeys were rerun successfully with the stronger assertions.
Final mobile visual review found that implicit grid rows stretched the sidebar
on shorter pages. Explicit auto/remaining-space rows corrected the layout; the
web-only image was rebuilt and the full mobile journey passed again, 7/7 with
zero skips. Final cleanup left exactly the intended active administrator account,
profile and ADMIN role; all 33 services were healthy and legacy IDs were unchanged.
No authorization/cleanup assertion was relaxed, no skip was counted as a pass and
no timeout or retry allowance was increased.

## Remaining limits and manual handoff

Remote S3 CI and production/TLS deployment are not yet claimed. Existing recovery
coverage remains in CI; no local intentional outage was authorized or run in S3.
The unchanged legacy suites were not rerun locally, and all their CI gates remain
mandatory. The full development dependency graph retains the previously recorded
10 findings; production app and new-service audits are clean. The pinned FastAPI
source test transport emits an existing httpx deprecation warning.

CI retains all ten jobs. The runtime job now additionally requires fresh initial
administrator creation and repeated safety verification before recovery. The
source minimum is 57 cases and the browser minimum is seven; omitted bootstrap
acceptance fails the structure guard. Merge only after the owner reviews the
change set and all required remote checks pass.

The authoritative Taskspace_Portal_Development_Plan.docx remains unchanged:
SHA-256 08af1dd1024824bbc91d7f0433e2e35e45db8b3e7084c9650edb99314199d6fd.
This record supplements it without editing it. S4 account/role-management screens,
company-wide business operations and future portals are not included.

Proposed commit: add S3 administrator portal and safe initial provisioning.
The owner performs staging, commit, push and PR actions manually.

## Manual first sign-in

Open http://127.0.0.1:3020 and use the dedicated ADMIN account. Retrieve only its
initial credential locally from the repository root:

```powershell
$initialAdministrator = Get-Content ".local/admin/initial-admin.json" | ConvertFrom-Json
$initialAdministrator.username
$initialAdministrator.temporaryPassword
```

Complete the required password change before entering the portal. If a previous
review account is still signed in, sign it out first. The private file retains
the initial password only; it does not track your replacement password.
