# S5 company structure and employee foundations

Status: **LOCAL ACCEPTANCE VERIFIED — owner website review reported; source review and remote CI pending.**
Date: 17 November 2026. Branch: s5-company-structure. Baseline: 72a3ed2.

## Scope and decisions

The immutable product plan defines departments, job titles, reporting relationships
and employee/account associations under initial administrator management. The owner
approved employee records before login accounts. One company role per account
continues unchanged; reporting managers and job titles grant no company or project
permissions. S6 has not started.

The shared people service owns these records. The gateway exposes typed GraphQL
contracts and the new administrator screens use the existing server-side session
boundary. Future HR views can reuse the same domain records and validation.

## Implementation

- `/admin/organization`: create, rename, archive and reactivate departments/titles.
  Names are normalized and unique per issuer and type. Active employee references
  prevent archival; existing history is retained.
- `/admin/employees`: paginated/searchable directory, employee creation without a
  login, employment edits, reporting manager selection and verified account linking.
- Account creation may attach an existing active, unlinked employee instead of
  creating a duplicate profile. Existing provisioning recovery remains explicit.
- Linking requires an active same-issuer account, exactly one valid role, no existing
  profile, no pending provisioning, and the exact enabled provider identity.
  Linking sends no email and never retrieves or resets a password.
- Commands reauthorize the current administrator under the existing shared PostgreSQL
  lock. Reporting changes walk the full chain, reject self/indirect cycles, and
  serialize concurrent graph updates. Versions reject stale changes; request IDs
  bind retries to their original intent; audits commit with successful changes.
- Migration 0004 backfills each existing employee issuer from its existing account,
  keeps all existing IDs/content, and makes login association optional. Downgrade
  refuses to discard unlinked employees. Migration 0004 is applied locally.

## Verified source evidence

| Check | Actual result |
| --- | --- |
| Backend regression suite | 115 passed, zero skips, including S5 domain/private API/GraphQL authorization and migration preservation tests |
| Authentication unit tests | 22 passed, zero skips after rerun with local loopback access |
| Repository structure regression suite | 16 passed, zero skips |
| Repository boundary validator | Passed |
| Python lint and formatting | Passed for scripts, services, shared security and source/structure tests |
| Frontend lint and types | Passed after lifting a form component out of render and declaring the generated query type |
| Production web build | Passed; organization and employee routes generated |
| Full frontend formatting | Passed after reformatting the browser spec |
| Production dependency audit | Zero vulnerabilities |
| PostgreSQL runtime parity and reporting concurrency | Passed: model/schema parity, required constraints, scoped rollback, last-admin race and reporting-cycle race; exact probe cleanup verified |
| Desktop S5 browser journey | Final expanded journey: 1/1 passed, zero skips, one worker, zero retries |
| Tablet S5 browser journey | 1/1 passed, zero skips, one worker, zero retries |
| Mobile S5 browser journey | 1/1 passed, zero skips, one worker, zero retries |
| Existing desktop account-entry regression | 1/1 passed, zero skips, one worker, zero retries; scoped cleanup verified |
| Remote CI | Not run for these unstaged changes |

An initial restricted unit-test invocation could not connect to its temporary
loopback server (EACCES); all 22 tests passed when rerun with local connection
access. A restricted backend invocation was interrupted and is not counted; the
complete 115-test run passed. A provisioning session warning exposed by the new
attachment test was corrected by adding the account to the session before binding
its employee. The remaining Starlette/httpx deprecation warning is upstream and
does not indicate a skipped or failing test.

## Runtime and cleanup procedure

The owner approved S5 runtime and scoped tests on 17 November 2026. Only the new
web/gateway/people images and containers were updated, and migration 0004 targeted
only the new people database. The web service was updated once more for the selector
label correction below. No identity/session/database/mailbox service was recreated.
No .env change, intentional outage, real email or broad cleanup occurred.

`python scripts/verify-account-entry-postgres.py` checks schema parity and rollback
probes, existing last-admin concurrency, and the S5 concurrent reporting-cycle probe.
All committed probes use synthetic issuers/UUID-owned resources and verify exact
cleanup. The S5 probe must allow exactly one of two conflicting updates, reject the
other as reporting_cycle, preserve roles and delete only verified owned rows.

Executed email-free browser focus from the repository root:

```powershell
python scripts/run-s1-acceptance.py --project desktop --organization-only
python scripts/run-s1-acceptance.py --project tablet --organization-only
python scripts/run-s1-acceptance.py --project mobile --organization-only
```

The wrapper runs Playwright from apps/web, one worker, zero retries. The journey
creates scoped structures, two unlinked employees and one marked disposable
identity/account, proves indirect-cycle rejection, rejects the exact disabled
provider identity before linking, confirms no association was created, verifies it
is enabled again, checks existing-employee selection without submitting an email
request, links the verified identity,
checks role preservation and direct EMPLOYEE/MANAGER/HR denial, then verifies owned
cleanup. Sanitized stage diagnostics are written before cleanup on failure. Cleanup
refuses resources changed by another actor or referenced by a non-owned employee.
The wrapper requires one executed pass, no skips, cleaned identity/account receipts,
all eight new services healthy and unchanged legacy service health/IDs.

Fresh isolated CI uses capture email and executes all nine lifecycle cases on each
viewport; the existing CI entrypoints include the added S5 case automatically.
Do not run full/email acceptance against the local Gmail realm or switch its mode.
Gmail activation/first-login success is owner reported; real Gmail reset and
used/expired-link evidence remains on the pre-final checklist.

## Runtime findings and corrections

The first desktop run timed out at directory creation. A diagnostic rerun with a
shorter five-second action wait isolated the exact Department selector: its nested
label included its option text, so the exact label lookup did not match. Explicit
accessible names were added to the new selectors. The test retains exact matching;
the overall 45-second timeout, one worker, zero retries and authorization assertions
are unchanged. Both early runs cleaned their owned resources successfully.

The next run reached account association and failed because the form locator's
relative filter repeated its parent row scope. The filter now resolves its button
inside the form. Its cleanup then exposed a separate fixture ORM assertion: after
loading the disposable account's role, deleting that account through the ORM tried
to clear a role primary key. The cleanup transaction rolled back. Cleanup now uses
the same explicit account-ID deletion pattern as the existing fixture commands.

Before another acceptance run, the blocked receipt, exact identity IDs, usernames,
email markers, run attributes, timestamps, audited resource names and associations
were checked. Only that run's structures, employees, audits, accounts, role grants
and two marked identities were removed; identity absence was verified. An independent
comparison then confirmed the original data and credentials unchanged. Sanitized
failure-stage diagnostics remain under test-results/reports/s5; private fixture
receipts remain under .local/auth/runs. Neither directory is part of the Git changes.

The corrected desktop journey passed. The final expanded journey, including live
disabled-identity rejection and the existing-employee account-form selection, then
passed separately on desktop, tablet and mobile. Machine-readable zero-skip reports:

- test-results/reports/s1/desktop-organization.json
- test-results/reports/s1/tablet-organization.json
- test-results/reports/s1/mobile-organization.json
- test-results/reports/s1/desktop-account-entry.json

The extra account-entry regression was initially blocked by automatic approval
review over possible Gmail email impact. Source inspection proved that its selected
test and hooks create an already-verified disposable identity and call no activation
or reset endpoint; the exact focused command was then approved and passed. No email
safety guard was changed to resolve that review.

## Preservation and service health

The pre-migration baseline contained 2 accounts, 2 employee profiles, 2 company-role
grants, 1 initial-administrator provisioning record, 1 account-provisioning record
and 4 account-audit records. After migration, failures, scoped recovery and successful
acceptance, every original column/value and record count matches that baseline.
The three new organization tables contain zero residual test rows.

All 4 existing realm identities, their credential fingerprints and the full SMTP
configuration fingerprint match the baseline. The exact primary ADMIN remains
enabled and its credentials are unchanged. Gmail remains the active sender at
dailygotasks@gmail.com. No real messages were sent by S5 tests.

All 8 portal and 26 legacy services are healthy. Persistent mount identities and
unaffected container IDs are unchanged, including all 26 legacy containers. Only
the approved web/gateway/people containers changed. No service restoration was
needed because no intentional outages were performed.

The plan SHA256 remains
08af1dd1024824bbc91d7f0433e2e35e45db8b3e7084c9650edb99314199d6fd.
Read-only index checks and the preservation baseline confirm an unchanged, empty
Git index. All changes remain unstaged; no branch or repository-history operation
was performed. Legacy source and dependency files are unchanged; no generated
runtime artifact or environment file appears in the change set.

## Remaining gates

Local required S5 acceptance evidence is present. On 17 November 2026, the owner
reported “I think all good” after the website review. This records owner-reported
UI acceptance; it does not claim a completed source review. The remaining steps
are owner source/staged-diff review, manual commit/push and remote CI evidence
before S5 is closed. No remote CI pass is claimed for these unstaged changes.

The full nine-case email lifecycle suite was not run against the Gmail realm.
Fresh isolated CI still requires all nine cases per viewport plus recovery checks.
Selected-employee email activation was source-tested with recovery; S5 live checks
covered form selection and verified linking without sending mail. Existing real
Gmail reset/used-expired-link evidence remains a separate pre-final email gate.
S6 has not started, and the authoritative plan has not been edited.


## CI administrator navigation correction — 17 November 2026

The owner supplied the PR #29 CI failure after commit 5308166. Its desktop
lifecycle run executed all nine cases: eight passed, including S4 and S5; S3
failed at the obsolete assertion that no Employees link exists. The final quality
gate correctly failed because this required job failed. Tablet/mobile steps in
that CI job were not executed; no full remote pass is claimed.

S5 intentionally adds the administrator Employees and Company structure links.
The S3 journey now explicitly requires both exact navigation labels and their
new-portal hrefs (/admin/employees and /admin/organization), while retaining the
absence checks for unimplemented Projects, Workflows, Reports and Design system.
Password, session, authorization and revoked-role assertions remain unchanged.
No production code, timeout, service, SMTP setting or dependency was changed.

Executed the exact affected S3 journey using the credential-safe repository-root
wrapper with --admin-only, separately on desktop, tablet and mobile. Each run
passed 1/1 with zero skips, one worker and zero retries. This focus creates an
already-verified disposable identity and changes only its password; no activation
or reset email endpoint is called. The existing ADMIN repeat-provisioning and
password-preservation assertions passed. Reports are under
 test-results/reports/s1/desktop-admin.json,
 test-results/reports/s1/tablet-admin.json and
 test-results/reports/s1/mobile-admin.json.

Frontend lint, full formatting, typecheck and git diff --check passed. Every run
verified scoped fixture/session/grant cleanup. An independent current-baseline
comparison verified all existing people rows, realm identities and credential
fingerprints, full Gmail SMTP fingerprint, data mounts and container IDs unchanged.
All 34 scoped services remain healthy. The original plan and Git index are
unchanged; these two correction files remain unstaged for owner review.

The full nine-case lifecycle suite is not rerun against live Gmail. The owner must
review/commit/push this correction and obtain a green remote CI run before merging.
S5 is not closed and S6 has not started.
