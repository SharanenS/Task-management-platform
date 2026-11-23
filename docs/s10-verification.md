# S10 owner decisions verification

Status: **in progress — local acceptance passed; owner website review and remote CI pending**.
Branch: s10-owner-decisions. Baseline: merged S9 commit 6fd4403.
Date: 23 November 2026.

The branch and index were clean before editing. All changes remain unstaged.
The owner confirmed owner/ADMIN scoped absence recording and pending-until-decision
semantics. These are recorded in s10-owner-decision-contract.md; the original plan
is unchanged. S11 has not started.

## Source change set

- Six additive project-work tables and guarded migration 0005_owner_decisions.
- Original commitment retained; separate current approval, assessment and decision
  history. No public assessment/escalation input writer or fake production inputs.
- Current-owner/ADMIN decision access; actor-bound calendar preview; fresh forecast,
  version, transaction and idempotency fences; explicit within-deadline fallback.
- Typed gateway API and protected oversight/decision/absence portal screens.
- Source tests, guarded owned fixture input/cleanup and five-case browser suite,
  PostgreSQL concurrency probe and three-service runtime script.

## Actual source checks

| Check | Actual result |
| --- | --- |
| Focused S10 source/API/migration/cleanup contracts | 39 passed; zero skips after final preview-validity refinement |
| Combined backend regression | 257 passed; zero failures, errors or skips (includes the 39 S10 cases) |
| Migration from S9 with existing project/calendar/coordination data | Passed; schema matched metadata and downgrade refused retained history |
| Frontend typecheck including browser test | Passed |
| Frontend lint and formatting | Passed on final source |
| Authentication unit tests | 22 passed; zero skips |
| Repository structure tests | 24 passed; zero skips, including S10 omission guards |
| GraphQL schema and operation generation | Executable schema parity passed in backend suite; repeated operation generation was byte-identical |
| Backend lint/format | Passed on final source using repository E/F/I selection and 100-column formatting |
| Production container build | project-work, gateway and web built successfully; Next production build passed |
| Live migration / PostgreSQL probe | Six additive tables applied; schema parity, competing decisions, replay, baseline preservation, fallback and owned cleanup passed |
| Credentialed desktop/tablet/mobile | Desktop 5/5, tablet 5/5 and mobile 5/5 passed; zero skips; scoped cleanup verified for each |
| CI integration | S10 source/runtime/PostgreSQL/browser scope added to retained gates; CI YAML parsed; remote run pending manual push |
| Frontend production dependency audit | 0 vulnerabilities |

The initial restricted authentication unit run passed 16/22: six OIDC cases could
not reach their temporary loopback mock server (EACCES). Repeating with local
loopback access passed all 22 without source or assertion changes. An exploratory
Ruff invocation inherited broader parent-directory rules; the repository
E/F/I selection and final 100-column format check passed across all 101 selected
backend, source-test and operation/structure files.

The initial read-only review covered 36 changed/untracked source files; the
final review also includes the authorized CI/runner/structure additions. The embedded-secret
pattern scan found no candidates; no environment file changed. Git whitespace
checks passed and the index has zero changed entries. Original plan SHA256 remains
08af1dd1024824bbc91d7f0433e2e35e45db8b3e7084c9650edb99314199d6fd.

No skip or discovery is claimed as a pass. Responsive acceptance evidence comes
from three separate credentialed runs. The approved three-service S10 update is applied. Existing real data is
protected by the fresh preservation baseline. No .env, SMTP, account, legacy service or volume change was made.

## Approved runtime scope

Capture a fresh preservation baseline, including any real S9 coordination rows
created since the prior stage. Do not reuse S9's older empty-coordination baseline.
Apply only the new project-work migration and rebuild/recreate project-work,
gateway and web. Keep people/identity/database services, ADMIN credentials,
Gmail configuration, legacy stacks and other local projects unchanged.

Run the owner PostgreSQL probe and the five-case desktop/tablet/mobile journey,
one worker, zero retries, unchanged 45-second case limit, then relevant retained
checks. The private fixture writes only receipt-owned marked projects; it is not
a production endpoint. It exercises forecast fixtures, revision history, late
acceptance, unknown/stale rejection, pending decisions, explicit scoped absence,
revocation, access isolation and responsive layout.

Verify exact owned cleanup and independently compare actual data, identities,
credentials, SMTP, service IDs/mounts and Git index. Foreign references must stop
cleanup. Preserve unique sanitized failure diagnostics before remediation. No
credential, raw OIDC address or query parameter belongs in diagnostic output.

S10 is included in retained isolated CI. The wrapper requires five executed
S10 passes and a cleaned receipt in focused mode; the full lifecycle requires
24 passes and five receipts, including four project-domain cleanup proofs.
Existing quality gates remain required.
Remote CI and owner website acceptance remain later gates. Do not mark S10 complete
or begin S11 without the required evidence.

## Approved runtime evidence — 23 November 2026

The owner approved S10 runtime, scoped tests and CI integration. A fresh baseline
captured 45 Compose containers, existing calendar/project data and coordination
rows, 3 accounts/profiles/grants, 5 realm users, initial ADMIN provisioning,
account/organization audit history and credential/SMTP checksums. No old S9
baseline was reused. Only project-work, gateway and web were rebuilt/recreated.
The owner PostgreSQL probe passed and verified its synthetic-issuer cleanup.

Desktop attempts retained before the successful run:

- The first attempt timed out at the initial Keycloak fixture-authorization call,
  before creating an identity. A direct probe of that exact operation returned
  HTTP 200 in 1,045 ms and its temporary grant was revoked (HTTP 204). Independent
  preservation comparison verified that no owned data remained. Its incomplete
  receipt is retained as blocked, never counted as cleaned or a pass.
- The next attempt exceeded the combined identity/browser/project preparation
  hook. Preparation was separated into independently bounded identity and browser
  setup hooks, each keeping the existing 45-second limit and all assertions.
- The absence case then exposed an exact-label locator mismatch. Isolated
  accessibility inspection and live sanitized control metadata proved the label
  included option text while the combobox name was exactly “Fallback scope”.
  Scope and decision selects now use their exact accessible role/name.
- An error call log included a disposable bearer header. The saved owned diagnostic
  was redacted, authorization/cookie/JWT sanitization was strengthened, and cleanup
  removed the disposable sessions/identities. No credential is included here.

These attempts are not acceptance passes. Original sanitized failure reports and
boundary records are retained under test-results/reports/s10. Subsequent desktop
and tablet journeys each executed all five cases with zero skips and verified
owned cleanup, bootstrap preservation and healthy services. Independent comparison
after desktop matched original people/work data, realm identities/credentials/SMTP,
primary ADMIN, mounts, unaffected container IDs and Git index. Mobile also completed 5/5 with zero skips and verified cleanup. All final retained checks listed below also passed.

## Retained database regression

The retained PostgreSQL wrappers passed against the S10 runtime: coordination
follow-up races/replay/history; membership leader races/replay/history; calendar
publication races and project commitment/publication races; account constraints,
last-administrator protection and reporting-cycle concurrency. Each reported its
scoped rollback or verified owned cleanup. These probes used their synthetic
owned scopes and did not change real calendar/project commitments or roles.

## Manual website review

Open http://127.0.0.1:3020, sign in with the preserved ADMIN account and open
Projects → an existing project → Delivery oversight. Review original/current
commitments, the honest “Not assessed” forecast, no invented actual delivery,
escalation empty state and absence history. A current MANAGER owner may use the
same project-specific entry; unrelated managers and employee leaders cannot.
If reviewing absence recording, use an explicitly intended reason, scope and time
window, then revoke with a reason and confirm the retained history. This creates
real audit data, so no automatic cleanup of owner-created review records occurs.

The decision/forecast journey uses private owned acceptance fixtures because real
task-planning producers belong to later stages. No demonstration inputs are left
in production pages. Remote CI and owner website acceptance remain completion
gates. S11 has not started. Git staging, commit and push remain owner actions.

## Final local acceptance and preservation

| Final check | Result |
| --- | --- |
| S10 desktop / tablet / mobile, separate credentialed runs | 5/5 each; 15 total; zero skips |
| Retained desktop coordination | 4/4 passed; zero skips |
| Retained desktop membership | 3/3 passed; zero skips |
| Retained desktop manager projects | 1/1 passed; zero skips |
| Retained desktop working calendar | 2/2 passed; zero skips |
| Retained desktop administrator workspace | 1/1 passed; zero skips |
| Retained desktop current account / direct GraphQL | 1/1 passed; zero skips |
| Final frontend lint / formatting / typecheck | Passed after selector and sanitizer corrections |
| Final authentication unit tests | 22/22 passed; zero skips |
| Final backend/operation lint and formatting | Passed across 101 files |
| Repository structure guards | 24/24 passed; zero skips |
| Project-work migration head | 0005_owner_decisions |
| Independent final preservation comparison | Passed |

The 27 final browser passes exclude all failed/skipped attempts described above.
Every successful wrapper verified its owned receipt and cleanup, bootstrap
preservation and ten healthy portal services. The full isolated CI lifecycle now
requires 24 executed cases; it was not run locally against configured Gmail.
Email lifecycle/recovery remains a fresh isolated remote CI gate; no SMTP change
or unapproved outage was used to obtain local evidence. Backend dependency locks
are unchanged; their remote lockfile audits remain required and are not claimed
as rerun locally. Frontend production audit passed with zero vulnerabilities.

The independent final comparison found exactly the original people/account/audit
rows and realm identities/credentials/SMTP checksums, including preserved primary
ADMIN. Original calendar/project/preview and coordination data matched the fresh
baseline. All six new tables were empty after scoped test cleanup. All 45 Compose
containers remained accounted for: 39 originally running containers healthy,
6 previously stopped containers unchanged. Only the three approved application
containers were replaced; unaffected container IDs and mounts were preserved.
No volumes were removed, no legacy service was replaced and no email was sent.
The original plan and Git index are unchanged; no Git mutation was performed.

Local engineering verification is ready for manual review. S10 completion still
requires the owner's website acceptance and passing remote CI after the owner's
manual commit/push. Do not start S11. Proposed commit message:
`add S10 owner oversight and audited deadline decisions`.
