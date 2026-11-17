# S4 user accounts and application roles

Date: 17 November 2026.
Status: IN PROGRESS — local application acceptance passed and Gmail is configured.
Real recipient receipt/activation/reset verification, owner review and remote CI
remain. S5 has not started. No stage completion beyond the evidenced local scope is claimed.

## Delivered scope

The administrator portal now includes /admin/accounts with account creation,
activation/deactivation, one company-role selection (ADMIN, MANAGER, EMPLOYEE or
HR), password-reset email initiation, explicit provisioning recovery and recent
change history. Company roles confer no project membership or team leadership.
The current administrator cannot demote or deactivate their own account.

The existing people service owns account lifecycle and authoritative profile/role
associations. The gateway exposes typed GraphQL commands and independently checks
identity. People rechecks current administrator authority under the lifecycle
lock. Web mutations use server-held tokens, exact Origin checks, fixed commands
and optimistic versions. Missing/inactive profiles and non-administrators remain
denied, including forged actor headers. No public registration or delete-account
feature is added. Deactivation preserves the employee profile and history.

## Email and credential decision

The owner chose email activation/reset links, not administrator-visible temporary
passwords. Keycloak creates the new identity without a password and sends actions
to verify its email and choose a password. Links have a 900-second lifetime, the
exact configured provider origin and a fixed permitted sign-in return URL.
Passwords, action links and tokens are absent from API results and audit records.
A successful send reports mail-server acceptance, not proven human receipt.

Initial acceptance used an approved private local inbox while the owner created
the dedicated sender. The owner has now supplied dailygotasks@gmail.com and asked
to connect it during S4; private credential entry is pending. Mailpit is pinned by version/digest, its UI binds only
127.0.0.1:8025 and SMTP remains private inside Compose. No relay or real external
email delivery is configured. The provider's realm-scoped service client has only
manage-users, query-users and view-users in realm-management, with matching scope
mappings and a short-lived service token. Its generated secret exists only in
ignored local configuration and the people service environment. Runtime services
receive no master administrator credential. Existing SMTP/client-secret drift
requires review rather than overwrite.

The previous pre-S22 deferral has been superseded by the current Gmail request.
The [delivery checklist](pre-final-stage-checklist.md) records the supplied sender
and remaining credential/delivery checks. Passwords and app passwords must not be
posted in chat.
The preserved initial ADMIN identity uses its original bootstrap email marker;
real reset delivery for that account additionally requires confirming its intended
recipient address. No primary administrator email or password was changed.

## Durability, safety and recovery

Migration 0003_account_management adds account versions, durable provisioning and
account audit tables. The actual PostgreSQL schema matches the models. A shared
session-level advisory lock serializes lifecycle commands with initial provisioning
across recovery commits and external provider calls. Last-administrator and
self-access checks run under that lock. Real concurrent cross-demotions proved
one change commits and the newly demoted actor is denied before its queued change.

Activation and its completed audit outcome are committed atomically. An injected
outcome-commit interruption proves the account remains inactive and its operation
recoverable; explicit recovery completes without creating another identity.

Creation records its UUID ownership before contacting Keycloak, checks username
and email conflicts and verifies the exact provider provisioning marker. Interrupted
responses resume only an owned identity. Unrelated identities are not adopted,
promoted, reset or deleted. Application access stays off until provisioning/email
acceptance completes. Duplicate request IDs are read-only or rejected if their
meaning changes; explicit recovery may resend a setup link but does not install a
password. Failures and outcomes remain inspectable in retained change history.

Deactivation commits denied application access before provider disable/logout, so
provider failure cannot leave business access enabled. Activation requires an
active profile, completed provisioning and enabled-provider readback. Changed role
permissions are resolved again for existing sessions. Reset initiation sends
provider email actions without retrieving or resetting the existing credential.

## Approved runtime and persistent data

The approved run built/recreated only web, gateway and people, applied the additive
migration, started local Mailpit and configured only the new realm's fixed web
return URL, administrator-editable provisioning marker, SMTP capture and owned
service client. Identity, Redis and database containers were not recreated.
No intentional outage, volume removal, broad cleanup or legacy source/data change.

A pre-runtime private account/profile/role baseline was compared independently
following acceptance: the exact original primary association remained, with one
active account, one profile and one ADMIN grant. Disposable provisioning and audit
rows were absent. Repeated initial-administrator verification preserved its exact
identity/account without password or role writes. Each browser run independently
verified the bootstrap administrator and revoked its temporary operator grants.
All eight new and 26 retained legacy services were healthy; legacy IDs and health
matched the baseline. Unrelated stopped containers were excluded from this scoped
health result and left untouched.

## Executed verification

| Check | Actual outcome |
| --- | --- |
| Backend authorization/provisioning/provider/schema/migration suite | 82 passed, zero skips |
| Authentication unit/protocol suite | 22 passed, zero skips |
| Repository/CI boundary suite | 15 passed, zero skips |
| Full desktop S1–S4 lifecycle | 8/8 passed, zero skips |
| Full tablet S1–S4 lifecycle | 8/8 passed, zero skips |
| Full mobile S1–S4 lifecycle | 8/8 passed, zero skips |
| Focused desktop S4 email journey | Passed after the diagnosed corrections below |
| Real email activation | Exact recipient message, provider confirmation, email verified and password chosen before normal application use |
| Employee administrator boundary | Administrator pages denied; forged authority denied by independent API tests |
| Deactivation | Exact disposable identity disabled; same bearer denied GraphQL access; inactive account entry shown |
| Reactivation and single-role change | Provider enabled readback, current account version and HR company role verified |
| Real email reset | Recipient followed reset link, chose a new password; old credential explicitly rejected with no app session; new credential accepted |
| Recovery failures | Source tests cover SMTP/provider failure, lost create response, unrelated identity refusal, read-only replay and recovery |
| Live PostgreSQL | Migration/model and constraint parity; concurrent cross-demotion and UUID-owned probe cleanup passed |
| Frontend quality and production build | Lint, typecheck, formatting and Next.js 16.4.6 production build passed |
| Python quality | Ruff E/F/I and formatting checks passed |
| Production npm audit | Zero known vulnerabilities |
| Scoped fixture cleanup | Exact owned identities, accounts, profiles, role grants, operations, audit rows and recipient messages removed |
| Browser authentication cleanup | Owned successful sessions and failed-login transaction keys removed and absence checked before cookies/context were discarded |
| Visual inspection | Desktop and mobile account forms/history inspected; tablet covered by viewport journey and private captures |
| Preservation | Primary administrator association preserved; no existing password writes; legacy IDs/health unchanged |
| Repeated realm/client/mail setup | Idempotent on the existing realm; no application identities or credentials changed |
| Direct gateway/people pinned dependency audits | No known vulnerabilities in either lockfile |
| Git and immutable plan | Index unchanged; all edits unstaged; plan SHA-256 unchanged |

Browser evidence is in ignored test-results/reports/s1/{desktop,tablet,mobile}-lifecycle.json.
Each final report selects and passes eight cases with zero skips. Backend evidence
is test-results/reports/s2/backend.xml; structure evidence is
test-results/reports/structure.json. Private captures are under
.local/admin/screens/<run UUID>/<viewport>; no credential forms were captured.
Diagnostics are sanitized and stored privately under .local/auth/failures.

## Diagnosed failures and corrections

Initial source tests caught audit foreign-key insertion order, replay-scope
comparison and an authentication exception incorrectly mapped to availability.
These were fixed without relaxing the authorization or state assertions.
The current operation generator already emits input types; removing duplicate
schema-type generation fixed duplicate declarations while keeping generated typed
documents reproducible. No generated output was hand-patched.

The first live boundary failed before the password form: Keycloak requires an
explicit proceed link. The helper now checks the exact provider origin and follows
that action. The provider v2 theme exposes an accessible Submit button, so its
existing role-based locator is used. Sanitized recipient metadata then exposed a
real provisioning issue: missing provider names triggered Update Account
Information. Provisioning now maps the supplied full name into provider name fields,
with a source regression; only people was rebuilt for that verified code change.

Further helper corrections scoped account form locators correctly and asserted the
existing inactive-account entry message alongside provider disabled readback and
direct same-bearer GraphQL denial. Final review also made activation and completed audit outcomes atomic; the injected
commit-failure regression passed before rebuilding only people and rerunning the
full browser journeys. No denial assertion was replaced by merely
seeing a login form. A duplicate local variable caused one discovery failure;
that 0/0 run was rejected and never counted as a pass.

The initial cleanup used a nonexistent Mailpit deletion path. SQL/provider cleanup
had finished, but the owned message and parent fixture remained. Ownership metadata
was preserved privately; only the exact recipient message ID and verified parent
fixture were removed, and the operator grant was revoked. The API now always gets
a nonempty explicit ID list; it never receives a delete-all request. Later cleanup
passed, and recipient cookies/transactions were explicitly checked before cookie
replacement. All three full journeys were rerun successfully after that stronger
cleanup. Original failures remain failures in their private diagnostics; no timeout
or retry allowance was increased and no skip/discovery counts as success.

## Manual review and remaining limits

Open http://127.0.0.1:3020/admin/accounts with the existing ADMIN login. Review the
create form, role/status confirmations, self-deactivation protection, activation
email, reset email and visible history. Emails currently appear only in the local
capture inbox at http://127.0.0.1:8025. Use only deliberate disposable review data;
normal application deactivation retains history and does not delete accounts.

Gmail SMTP delivery is pending owner account setup and separate private
configuration. Local acceptance does not prove delivery to a real external inbox.
Production/TLS deployment and remote S4 CI are not claimed. Existing recovery CI
remains mandatory; no intentional local outage was authorized or run for S4.
The unchanged development dependency graph retains its earlier 10 findings;
production npm audit is clean. The existing httpx test transport deprecation warning
remains. S5 has not started.

The original Taskspace_Portal_Development_Plan.docx remains unchanged, SHA-256:
08af1dd1024824bbc91d7f0433e2e35e45db8b3e7084c9650edb99314199d6fd.
This separate verification record supplements the plan without modifying it.

Proposed commit: add S4 account management and email activation.
The owner performs all staging, commit, push and PR actions after review. CI still
has ten required jobs; its new runtime path starts the eight-service environment,
requires all eight lifecycle cases and cannot omit initial-administrator acceptance.

Integration references: [Keycloak user action-email API](https://www.keycloak.org/docs-api/latest/rest-api/index.html)
and [Mailpit API](https://mailpit.axllent.org/docs/api-v1/). The actual pinned-version
provider page and Mailpit Swagger contracts were inspected during diagnosis.

The final atomic-outcome image passed all three complete 8/8 journeys again, with
zero skips and scoped cleanup. No local recovery outage was run or claimed; existing
recovery and retained legacy CI gates remain mandatory. Existing development-only
dependency findings and the source transport deprecation warning are unchanged.

Proposed commit: add S4 account management and email activation.
All changes remain unstaged. The owner performs review, staging, commit and push.

Independent final evidence is retained privately in
.local/accounts/final-verification.json: exact primary account/profile/role baseline
preserved; one account/profile/grant remains; zero disposable provisioning or audit
fixtures; zero capture messages; all 34 scoped services healthy and legacy IDs and
health unchanged. Unrelated stopped containers were excluded from scoped health
checks and left untouched.

The product document SHA-256 remains
08af1dd1024824bbc91d7f0433e2e35e45db8b3e7084c9650edb99314199d6fd.
The read-only index manifest hash remains fa2d8ce40ea797878ee8169e6567862c3fe7a4e3;
git diff --cached is empty. Actual local secret values were scanned against the
complete tracked/untracked change set: zero matches and no generated/private
artifacts among the candidate files.

## Gmail sender update — 17 November 2026

The owner replaced the earlier deferral and confirmed dailygotasks@gmail.com as
the sender. The original product document remains unchanged. The new explicit
operator command is `python scripts/configure-email.py gmail`; it prompts for a
Google app password with echo disabled and aborts instead of falling back to
visible input. No normal Google password, command-line secret or .env change is
used. SMTP credentials are not written to a local file or committed source.

The command authenticates to smtp.gmail.com:587 using certificate-verified STARTTLS
before changing the current realm settings. It accepts only the existing local
capture configuration or this exact approved Gmail sender. It updates only SMTP,
checks the readback and revokes its temporary operator grant. A private receipt
contains only sender/mode and verification booleans. No email is sent by setup.
Gmail authentication or setup failure is sanitized; failed authentication preserves
the currently working delivery. The primary administrator email, password, company
role and profile are not modified. No service rebuild or restart is required.

Normal S4 startup preserves an already configured approved Gmail sender and its
stored credential rather than reverting it to capture or writing a masked secret
back. Automated email journeys inspect the live realm SMTP configuration and fail
closed before fixture creation unless delivery is local capture. This protects
real addresses from test messages. A structure regression prevents removing that
guard; tests do not automatically switch a live Gmail realm back to capture.

Gmail is not yet connected: the address alone is insufficient for SMTP login. The
owner must enable Google 2-Step Verification, create an app password and enter it
locally. Actual recipient receipt, activation and reset through Gmail must then be
verified; prior Mailpit passes do not count as real Gmail delivery evidence.

[Google app-password guidance](https://support.google.com/accounts/answer/185833)
and [Gmail SMTP settings](https://developers.google.com/workspace/gmail/imap/imap-smtp)
were checked for the authentication and STARTTLS configuration.

Gmail-update verification: backend suite 98 passed, zero skips; structure suite
16 passed, zero skips; Ruff check and format passed. The focused desktop S4 journey
passed 1/1 with the new live capture-delivery guard, followed by scoped cleanup and
healthy-service/legacy-preservation verification. These are local-capture results,
not Gmail delivery evidence. `configure-email.py status` reports local-capture; no
SMTP setting has been changed or real email sent during this update. No service
rebuild or restart was needed. The Git index and product-document hash are unchanged.

## Gmail configured by owner — 17 November 2026

The owner ran the hidden-entry Gmail setup command. Its output reported Gmail
authentication and realm configuration verified, with no email sent. Independent
read-only status confirmed delivery mode gmail and sender dailygotasks@gmail.com.
All 34 scoped services were healthy and the Git index manifest remained unchanged.
No SMTP credential was viewed, printed or written to committed source. No service
restart or primary-administrator change was performed.

This verifies authentication/configuration only. Actual inbox receipt and the real
Gmail activation/reset journeys still require owner-controlled recipient evidence.
The local capture tests must not be rerun against this live Gmail configuration.
The initial administrator recipient email remains its preserved bootstrap marker
until the owner explicitly confirms any intended change.

## Owner-reported Gmail review — 17 November 2026

After the manual checklist to create an EMPLOYEE account using an owned recipient,
receive its setup email, follow the link, choose a password and sign in, the owner
reported that all was good. This records owner-reported activation/first-login
acceptance, not an independently automated Gmail run. Separate real-Gmail reset
and used/expired-link evidence is not claimed. Remote CI remains pending manual
commit/push; S5 has not started. The owner has requested manual staging preparation.
