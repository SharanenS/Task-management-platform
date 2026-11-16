# S1 authentication verification and handoff

Date: 15 November 2026.

Status: READY FOR MANUAL COMMIT. Local S1 implementation and acceptance are
verified. Owner review, manual Git actions and remote CI remain. S2 has not started.

## Delivered behavior

The replacement application at http://127.0.0.1:3020/sign-in now owns the sign-in
journey. It has new sign-in, interrupted-sign-in, expired-session, unavailable,
signed-out, error and not-found views, plus a branded Keycloak credential page.
Desktop, tablet and mobile layouts were exercised and visually inspected.
No route, error, navigation item or authentication fallback imports the old shell.

The protected /auth/ready page confirms authentication and truthfully states that
the workspace is not available yet. It exposes no business operations or future
portal links. Active employee/profile association, company-role authorization and
GraphQL business contracts belong to S2. No empty Python business service was
created merely to fill the directory structure.

The authoritative Taskspace_Portal_Development_Plan.docx v1.1 remains unchanged.
SHA-256: 08af1dd1024824bbc91d7f0433e2e35e45db8b3e7084c9650edb99314199d6fd.
The retained Next.js/Python/FastAPI/Keycloak stack follows the agreed portal design.

## Security and session decisions

- Authorization Code with S256 PKCE, independent state and nonce, and one-time
  Redis GETDEL transactions. Invalid, expired and replayed transactions fail closed.
- OIDC signature, issuer, audience, nonce and expiry validation through pinned
  openid-client. Signature checking is explicitly enabled with non-repudiation
  checks, including local HTTP mode; it is not assumed from library defaults.
- The exact external issuer is http://127.0.0.1:8180/realms/taskspace-portals.
  Container token/JWKS traffic uses only the explicitly permitted identity:8080
  issuer with the same realm path. Identity claims must match the external issuer.
  URL classification compares full origins, including scheme, host and port.
- HTTPS is required except explicit loopback development mode and the fixed private
  identity service. HTTPS cookie configuration uses Secure and the __Host- prefix.
  Local browser acceptance uses HTTP; HTTPS behavior is unit-tested, not claimed
  as a deployed end-to-end TLS test.
- Login and logout are POST-only with exact Origin validation. Return destinations
  are restricted to the sole implemented protected page. Application credentials
  are entered only at Keycloak; application password grants and self-registration
  are disabled. Keycloak brute-force protection is enabled.
- Opaque 32-byte HttpOnly SameSite=Lax session and transaction cookies. Names differ
  from legacy cookies. Redis keys hash the browser identifier and use a new namespace.
  No access, refresh or ID token is placed in browser storage or exposed in page data.
- Session lifetime is bounded by access-token expiry, ID-token expiry and a 30-minute
  maximum. Transactions last five minutes. S1 discards refresh tokens and requests
  no offline access; expiry requires sign-in again. Unverified legacy refresh-race
  behavior was not carried forward. Any future refresh mechanism requires its own
  concurrency and failure tests.
- Expired/corrupt records are removed and stale cookies are cleared. The expiry route
  cannot log out a valid session. Logout revokes local state before provider logout.
  Failed local revocation is not presented as successful logout; provider-only
  unavailability is distinguished from an ended application session.
- Redis failure never creates authenticated fallback state. Closed cached connections
  are discarded; the first request after restoration opens a fresh connection.
  Failed commands are not automatically replayed, avoiding ambiguous repeated writes.
- Authentication responses are not cacheable. Headers constrain framing, resources,
  forms and referrers. Incoming request logging is disabled so callback query values
  are not printed. Application diagnostics use fixed categories; browser reporting
  emits boundaries and locations rather than raw errors or OIDC URLs.

The preserved mechanisms were assessed before reuse. The new app imports none of
the old authentication implementation. It retains sound protocol concepts, not the
old shell, profile assumptions or incomplete concurrent refresh behavior.

## Runtime and data isolation

The owner explicitly approved starting the S1 stack and the two sequential recovery
outages. Project: taskspace-portals-development. Services: web, identity, identity-db
and auth-sessions. Published loopback ports: 3020, 8180 and 6381. The identity database
has no host port. Its portal_identity_data volume is scoped to the new project.
No worker, consumer, publisher, queue or legacy database connection was introduced.

The root Compose file remains web-only; compose.auth.yaml is an explicit override.
The wrapper uses an explicit empty Compose environment file, never the legacy .env.
Generated credentials are kept only in ignored .local/auth/development.json and are
not reset when the wrapper is rerun. Database/session images and the identity build
base use inspected digests. Keycloak is prepared during image build and started
with --optimized. Builds run sequentially, with a 512 MiB identity Java heap,
1024 MiB web-build Node heap and two framework build workers.

The liveness endpoint /health/live checks the web process. The database, identity
and session store retain separate health checks; real authentication is verified by
browser acceptance. Startup remains limited to 180 seconds, provider readiness to
40 seconds and individual browser tests to 45 seconds. No limit was lengthened to
make a failure pass. Restoration verification uses the cleanup hook's independent
budget so an outage probe cannot consume its readiness deadline.

The new realm import contains client configuration only, with no embedded users or
passwords. Its master-realm bootstrap administrator is operational setup, not the
S3 initial company administrator. No permanent application users were created.
Legacy account APIs were never called. No legacy service, realm, database, user,
volume, queue, password, migration or source file was reset or deleted.

## Acceptance results

| Check | Actual outcome |
| --- | --- |
| Authentication unit/protocol suite | 21 passed; zero skips or failures |
| Structure regression suite | 12 passed; zero skips or failures |
| Desktop lifecycle on final recovery build | 5/5 passed; zero skips |
| Tablet lifecycle on final recovery build | 5/5 passed; zero skips |
| Mobile lifecycle on final recovery build | 5/5 passed; zero skips |
| Sequential identity and session-store recovery | 2/2 passed; zero skips |
| Full credentialed desktop lifecycle after restoration | 5/5 passed; zero skips |
| Formatting, ESLint and TypeScript | Passed |
| Python Ruff lint and formatting | Passed |
| Production container build | Passed on final application source |
| New-app production npm audit | Zero known vulnerabilities |
| Docker definition check | Passed; no warnings |
| Runtime artifact/privacy inspection | No test outputs or private environment files in web image |
| CI YAML and mandatory job discovery | Eight required gates retained and parsed |
| Visual review | Desktop, tablet, mobile, provider and signed-in page inspected |
| Final service health | 26 legacy and four new services running and healthy |
| Scoped cleanup | Zero new-realm users, app authentication records or residual administrator sessions |
| Bootstrap preservation | Exact ID/active-state checks in every fixture; final independent check passed |
| Source/environment preservation | Original inventory verified; private .env unchanged |
| Git branch, HEAD and index | Preserved; all changes unstaged |
| Immutable product document | Hash unchanged |

The post-restoration desktop run is the final desktop report, not a separate set
of new unique tests. Machine-readable reports are in ignored
test-results/reports/s1/{desktop,tablet,mobile}-lifecycle.json and
test-results/reports/s1/desktop-recovery.json. Each lifecycle run requires all five
cases and zero skips. Recovery requires both cases, independent health verification,
and then a complete credentialed desktop rerun. Discovery or a skip cannot pass.

The five lifecycle cases cover protected entry and no old UI, real rejected
credential submission, valid sign-in/cookie privacy/server expiry/logout, callback
and Origin tampering, and nonce mismatch against a valid provider response.
Invalid login requires an actual submission on the exact provider origin, explicit
rejection, no authenticated application cookie and no provider user session. A visible
login form alone is insufficient. Expiry modifies only the exact disposable session
after checking its subject. Unit protocol tests use generated RSA keys and a loopback
mock issuer, proving JWKS use and rejection of signature/claim failures.

## Cleanup and restoration evidence

Fixtures use unique UUID usernames and matching example.invalid email addresses.
Creation receipts are recorded privately before ownership checks. Deletion requires
matching receipt/run/realm, exact returned user ID, username/email, expected names
and bounded creation timestamp. No unmanaged-attribute permission was enabled.
Each run verifies removal by a subsequent 404 and preserves the bootstrap by exact
ID. Every administrator grant created by a fixture is revoked individually.
Browser-owned Redis records are checked before scoped deletion. All receipts must
be clean for the runner to pass.

Recovery checks exact project/service labels and healthy state before stopping a
target. Both test finally blocks start only their target. Cleanup verifies readiness
and functional recovery; cleanup failures fail the case. The outer wrapper separately
restores a stopped target, checks all four services and compares legacy IDs/health.
After the successful recovery run, all five credentialed desktop cases passed again.
Final independent API/Redis checks found zero disposable users, authentication records
and residual administrator sessions. The final diagnostic grant was also revoked.

Credential-free captures are retained locally under .local/auth: sign-in-desktop.png,
sign-in-tablet.png, sign-in-mobile.png, identity-sign-in.png and ready-desktop.png.
The signed-in capture contains only a disposable display name. Trace/video and automatic
screenshots are disabled. An explicit review flag captures the ready page only after
successful sign-in; no credential-entry screenshot is taken. The visual-review
transaction was independently ownership-checked and removed.

## Failures diagnosed before the final passes

- Initial Keycloak startup exceeded readiness while doing 122057 ms of augmentation
  followed by first database initialization. Sanitized startup evidence is in
  .local/auth/startup-diagnostic.txt. Preparation moved to the image build; the new
  data was retained. No stale-container explanation or timeout increase was used.
- A parallel image build was stopped after observing 441–501 MiB free of 15998 MiB.
  Only the verified new build client and new identity service were paused. Bounded,
  sequential builds recovered free memory and completed. All services were restored.
- The first browser fixture's custom ownership marker was dropped by Keycloak's
  default profile policy. Cleanup correctly blocked. The sole uniquely marked failed
  identity and its exact administrator session were independently verified and removed.
  Creation-receipt ownership checks replaced the unsupported marker without relaxing
  deletion requirements or realm permissions.
- The next run exposed the provider's read-only reauthentication identity field and
  an unrelated empty Next screen-reader alert. The helper now verifies the same identity;
  notices are scoped to main. Assertions and timeouts were retained. Subsequent complete
  desktop/tablet/mobile runs passed and receipts prove the reauthentication branch ran.
- The first recovery run failed readiness-budget composition and the first request
  after Redis restoration. Sanitized results are in .local/auth/recovery-first-failure.json.
  Keycloak itself restarted in 27.343 seconds. Cleanup now retains its independent
  40-second readiness assertion. The real closed-connection cache bug was fixed in the
  app, and the first post-restoration request plus full credentialed rerun passed.
- Source checks caught UTF-8 text, CSP syntax, Redis generic typing and fixture typing
  issues; all were corrected. Generated Playwright outputs are excluded from formatter
  and Docker input scope. Failed attempts are not counted as acceptance passes.

Git normalized CRLF in three preserved historical Markdown files during the owner's
checkout. Original byte hashes remain in recovery metadata. Current inventory hashes
explicitly normalize CRLF to LF; no historical document's bytes were edited here.
The CI inventory hash includes the added S1 unit/browser gates.

## Remaining limits and manual handoff

Remote CI, production deployment and a fresh CI database first boot are not claimed.
The new runtime reused its preserved identity volume after the first startup attempt.
The full new-app dependency graph retains the eight known S0 development findings
(seven moderate, one high); the production npm audit is clean. Business PostgreSQL
integration and unchanged legacy browser suites were not rerun locally for this
frontend/authentication change. Their six historical CI gates remain mandatory.

Review the source and this record before staging. Use the exact development origin
http://127.0.0.1:3020; credentials are not embedded in source. Test logins have been
deleted. Initial company-account provisioning remains S3. S2 requires subsequent
explicit authorization after S1 review and merge.

Proposed commit: feat: add secure S1 authentication experience.
The owner stages, commits, pushes and opens the PR manually. Merge only after all
eight required CI jobs succeed. No Git mutation, push or PR action was performed.

## Initial-entry correction — 16 November 2026

A fresh visit to the root previously passed through the protected confirmation
page and incorrectly displayed the session-ended view. The root now sends a
visitor without a session cookie directly to the configured sign-in origin;
`localhost:3020` resolves to the configured `127.0.0.1:3020` application origin.
A valid session still reaches `/auth/ready`. Missing cookies on protected entry
or the expiry route lead to sign-in; a present expired or invalid session still
passes through the expiry route, which clears the stale cookie. The expiry
message no longer describes a first visit as an ended session. No artificial
loading delay was introduced. Origin checks and session validation remain intact.

Verification on the updated web image:

- Lint, typecheck, formatting and all 21 authentication unit tests passed.
- The web production image built successfully; only the approved new web service
  was recreated, and its health check passed.
- Desktop authentication acceptance: 5/5 passed, zero skipped, one worker and
  zero retries. This includes first entry through `localhost`, unauthenticated
  expiry/protected entry, a signed-in return to the root, real credential
  rejection, forced server-side expiry, reauthentication, logout, callback
  tampering, cross-origin rejection and nonce mismatch.
- Scoped disposable identity cleanup, bootstrap preservation and grant cleanup
  passed. All four new services were healthy afterward; legacy service IDs and
  health were unchanged. The separately provisioned manual-review account is
  retained and is not an acceptance fixture; its credentials remain local.
- Tablet/mobile lifecycle and service recovery evidence above remains from the
  prior verified runs. Those runs were not repeated for this routing correction.
- The first restricted-process unit attempt could not complete its loopback
  protocol checks; the normal-process run passed all 21 without source or timeout
  changes. No restricted-process result is counted as a pass.

The authoritative plan remains unchanged, S2 has not started, and all changes
remain unstaged for owner review. Remote CI and the previously stated limits
remain outstanding.

## Retained CI dashboard locator correction — 16 November 2026

The supplied main-branch merge-run log reports 9/10 domain cases passed. The
retained dashboard case failed after keyboard navigation to Projects because a
substring heading locator matched both the page h1 "Projects" and the empty-state
h3 "No projects found". The aggregate quality gate then failed because that
required browser job failed; it was not a second independent application failure.

The assertion in legacy/frontend/tests/e2e/dashboard-acceptance.spec.ts now targets
level 1 with the exact accessible name "Projects". Visibility, keyboard navigation,
filter handoff, cursor reset, authorization and cleanup assertions remain required.
No runtime source, timeout, service, account or product-plan change was made.

Focused ESLint, legacy TypeScript checking and formatting passed. A credential-free
Chromium reproduction of the reported two-heading DOM confirmed the old locator
matches two nodes and the corrected locator identifies the visible page h1.
Repository structure verification and all 12 structure tests passed. This isolated
locator reproduction is not a full dashboard acceptance pass. The credentialed
dashboard journey and aggregate quality gate require a new remote CI run on the
follow-up commit. Rerunning the old commit alone does not apply this source fix.
