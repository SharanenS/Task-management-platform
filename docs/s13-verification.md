# S13 completion review verification

Status: **in progress — local checks passed; owner website review and remote S13 CI pending**.
Date: 28 November 2026. Branch: s13-completion-review.
Baseline: 3589a6380d2118e4f344019b7bf7cc13467b13cd. Initial worktree/index were clean.

S12 post-merge CI [46119194721](https://github.com/SharanenS/Task-management-platform/actions/runs/46119194721)
completed successfully on the exact baseline. The unchanged original development
plan's S13 scope and existing S10/S11/S12 contracts were inspected before edits.

## Implementation

See [the completion contract](s13-completion-contract.md). Added current-assignee
execution, separately versioned completion submissions, review return/approval,
explicit audited leader self-approval and current review-scoped owner/ADMIN fallback.
Three additive tables and migration 0008 follow the existing project-work chain.
Original commitments and planning history remain intact; actual start, submission
and approval time stay separate. Private progress, blockers, work updates and
submission snapshots are projected only to the current assignee or supervisors.
Late approval makes the forecast unassessed without moving dates or assigning fault.

Includes private service endpoints, typed GraphQL, generated operations, the session
BFF, contextual leader/owner/admin screens, scoped cleanup, PostgreSQL probe and
five browser cases per viewport. Employee shell/employee execution UI, extensions,
notifications, cancellation/reopening and S14 have not started.

## Actual verification results

| Check | Actual result |
| --- | --- |
| Focused review/domain/API/migration/cleanup suite | 30 passed, zero skips |
| Full backend regression | 375 passed, zero skips |
| Structure regression | 33 passed, zero skips |
| CI-configured Ruff lint/format | Passed; 156 files formatted |
| Frontend lint/types | Passed, including final history/display edits |
| Web unit tests | 25 passed, zero skips |
| Frontend formatting and production build | Passed, including all review routes and BFF |
| Schema export and frontend code generation | Passed; repeat generation was byte-identical |
| Credentialed desktop/tablet/mobile | 5/5 passed separately on each viewport; zero skips; cleanup and wrapper health verified |
| Live PostgreSQL schema/concurrency probe | Passed; one race winner, exact replay, separate submission, original deadline and scoped cleanup verified |
| Retained desktop task planning | 4/4 passed, zero skips; cleanup and health verified |
| Retained desktop scheduling | Rerun 4/4 passed, zero skips; cleanup and health verified; initial failed preview retained below |

Source reports are under ignored test-results/reports/s13. A first focused invocation
found a missing test-fixture import; it was corrected. Formatting findings were
corrected without changing assertions. FastAPI's test client emits the existing
Starlette/httpx deprecation warning. Source API checks use local in-memory test
transports, not real services or accounts. No skip/discovery is counted as a pass.

Fourteen inline browser GraphQL operations also validated against the exported schema.
Workflow YAML, four independent lanes, unchanged job limits and desktop-only probe
scope passed semantic validation. All ten portal containers were healthy before the approved update. The live
migration is now at 0008_completion_reviews, and running project-work/gateway
Python source hashes match the workspace. Only the three approved services were
recreated; their production web build passed.

The source tests cover separate submission/approval, return/resubmit feedback,
self-confirmation, exact replay/conflicts, current authority fencing, inactive
assignees, peer privacy, both service credentials, fallback scope/expiry/revocation/
changed leadership, dependency gating, original-date preservation and retained-data
rollback refusal. The cleanup tests reject foreign actors without deleting tasks. Review approval
preserves the last assignee-reported percentage rather than reporting progress as
the reviewer. Approved completed prerequisites remain completed after the former
assignee is deactivated; current child-task eligibility and readiness are still
required. Both lifecycle edge cases have explicit regression assertions.

## Prepared runtime and CI scope

The following scope was approved by the owner and executed locally. Commands run
from repository root:

```powershell
python scripts/review-development.py up --apply-migration
python scripts/verify-reviews-postgres.py
python scripts/run-s1-acceptance.py --project desktop --reviews-only
python scripts/run-s1-acceptance.py --project tablet --reviews-only
python scripts/run-s1-acceptance.py --project mobile --reviews-only
```

The browser wrapper requires five executed cases, zero skips and exactly one owned
receipt per focused run. All task/schedule/review/session/peer-account/identity and
bootstrap/grant cleanup proofs are required. Five prepared journeys cover leader-own
UI execution and explicit self-approval, contributor return/resubmission, dependency
blocking until approval, explicit owner fallback/revocation and privacy/origin/
removed-leader boundaries. Contributor execution uses the shared authenticated API;
no future employee portal is represented as implemented. The PostgreSQL probe uses
a synthetic issuer and validates schema parity, one-winner competing review decisions,
exact replay, separate submission/approval, retained actual outcomes and owned cleanup.
The PostgreSQL probe has now executed successfully against the live S13 image;
browser outcomes are recorded below as they complete.

CI retains all existing lanes/gates and adds S13 source/runtime/desktop PostgreSQL
coverage. Full lifecycle now requires 37 cases per viewport, eight owned receipts,
seven project-domain cleanup proofs and three third-employee cleanup proofs; review
cleanup has its own seven-receipt proof. Recovery still requires both outage cases
and the full restored lifecycle. No timeout/retry increase or removed assertion.

Before any approved live migration, capture a fresh preservation baseline; do not
reuse or overwrite S12's baseline. Preserve real work/reviews, calendars, accounts,
ADMIN credentials, Gmail settings, mounts, unrelated containers and the Git index.
Only project-work/gateway/web were updated. No email, intentional outage,
new service, volume cleanup or broad deletion is included. Remove only verified
run-owned resources and independently verify preservation after every failed cleanup.

Owner website review and remote S13 CI remain outstanding. Live PostgreSQL/browser
outcomes are recorded below. The original plan is unchanged. All edits remain unstaged and
no Git/GitHub mutation was performed.


## Source handoff

The source implementation and applicable source checks are complete. Review of all
tracked/new paths found no unrelated edits, private credential files, generated
runtime artifacts or credential-pattern findings. The original plan SHA-256 remains
08af1dd1024824bbc91d7f0433e2e35e45db8b3e7084c9650edb99314199d6fd.
The Git index remains unchanged and empty. Live acceptance outcomes are recorded below; no skip or discovery run is treated
as a pass.


## Approved live runtime — 28 November 2026

The owner approved the three-table migration, only project-work/gateway/web updates,
PostgreSQL checks and scoped desktop/tablet/mobile journeys. A fresh S13 baseline
was captured before any service update: 3 accounts/profiles/role grants, 5 realm
identities and 45 Compose resources. It also captured current company/work records,
including changes since S12; S12's older baseline was not reused. All ten portal
services were healthy. Original image IDs for the three approved targets were
recorded privately for recovery. No credentials were printed and no .env changed.

The approved image builds and migration completed. PostgreSQL schema/concurrency
acceptance and its owned cleanup passed. The first desktop attempt failed before
review execution: the fixture operator token request did not complete within the
unchanged five-second limit (0/5 passed, four serial skips). Its sanitized report
was retained. Independent preservation checks proved no disposable identity or
application rows were created and original data, credentials, SMTP, ADMIN, mounts
and unaffected service IDs were preserved. A direct authentication check then
returned successfully in 435 ms. No assertion, timeout or service was changed
before rerunning. An unrelated deploy:kafka health exception was observed and
left untouched; it is not treated as proof of the authentication failure cause.


The desktop rerun passed 5/5, zero skips, with all scoped cleanup proofs and
wrapper health checks verified. Tablet passed 5/5, zero skips, with the same
cleanup/health proofs. The independent post-desktop comparison found all 45
resources preserved and no health exceptions. Final source review removed a
misleading inspection-only message that claimed owners saw only their own
submissions; server permissions and projections were unchanged. Mobile also passed 5/5, zero skips, with all scoped cleanup and wrapper health
proofs. The final wording-only web rebuild passed production compilation/types
and became healthy. Lint, typecheck and formatting passed for the final wording.
Retained desktop task planning passed 4/4, zero skips, with cleanup and wrapper
health verified. Scheduling rerun passed 4/4, zero skips; scoped cleanup and wrapper health also passed.

Successful S13 receipts (desktop/tablet/mobile respectively):
`dd6683dd-5a3b-4b7c-ba17-78a574366dbb`,
`59030ecf-67e5-4663-b4d6-64c93852b249`,
`7ef9491d-05f5-4692-9bd9-90b70253f48e`. All are `cleaned` and include true
project/membership/owner/task/schedule/review/calendar/session cleanup, identity/
account/peer removal, bootstrap preservation and grant-revocation proofs.
Sanitized acceptance reports are retained under ignored
`test-results/reports/s1/{desktop,tablet,mobile}-completion-reviews.json`; the live
PostgreSQL report is under ignored `test-results/reports/s13/postgres-*.json`.


## Retained desktop scheduling boundary

The first retained S12 scheduling run failed at the initial UI schedule-preview
response before saving a schedule (0/4 passed; three serial skips). Its existing
assertion recorded only response.ok=false, so no HTTP status or root cause is
claimed from that artifact. Sanitized boundary diagnostics were preserved before
cleanup. The wrapper verified owned cleanup and ten healthy portal services; an
independent baseline comparison proved original rows, identities/credentials/SMTP,
ADMIN, mounts and unaffected IDs preserved and owned test rows absent. The
unrelated deploy:kafka health exception reappeared and was left untouched.
The retained test now includes HTTP status and allowlisted fixed error text in
its unchanged successful-preview assertion; no credential, OIDC URL, query string,
request body, assertion or timeout relaxation was introduced. The diagnostic rerun
passed 4/4, zero skips, on the same service images, including preview/save,
dependency/overlap behavior, cycle rejection/privacy and immediate leader
revocation. The first failed response did not recur; its root cause remains
unproven. No production scheduling change was made. The diagnostic test edit
passed focused lint, typecheck and formatting.


## Final local handoff

Final independent preservation comparison passed after all runtime journeys and
their cleanup: all original people/work rows, five realm identities, credential/SMTP
digests, primary ADMIN, mounts and unaffected container IDs were preserved. All
owned test data was absent. All 45 resources matched required running/stopped
states, with no final health exceptions; all ten portal services were healthy.
The earlier unrelated Kafka health exception cleared without intervention.
No service outside project-work/gateway/web was rebuilt or recreated. No real
email, intentional outage, volume deletion or broad cleanup was performed.

Read-only Git checks confirm branch s13-completion-review, an unchanged empty
index and clean diff whitespace. All 42 changed/new deliverable files remain
unstaged. No credentials/private runtime artifacts were found in the change set.
The original plan hash is unchanged. S14 has not started.

Local implementation and scoped acceptance are ready for owner review. S13 stays
in progress until owner website review and required remote S13 CI succeed. The
initial operator-request and scheduling-preview failures are retained above;
neither is represented as fixed by a timeout increase, unrelated service restart
or a proven infrastructure cause. The scheduling diagnostic improvement permits
a future recurrence to identify its exact HTTP/error category safely.

Proposed commit message after owner review:
`add S13 completion reviews and audited leader-owned execution`
