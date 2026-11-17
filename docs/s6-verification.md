# S6 company working calendar verification

Date: 17 November 2026. Branch: s6-company-calendar. Baseline: 5aa9af8.
Status: **LOCAL ACCEPTANCE VERIFIED — owner website confirmation recorded; source review and remote CI pending.**

## Authority and scope

The immutable product plan and the existing architecture assign the calendar to
project-work. The owner approved whole-working-day counting on 17 November 2026.
See s6-calendar-rules.md for the approved decisions and explicit implementation
boundaries. The original document remains unchanged. S7 has not started.

S6 introduces one functional project-work service and its private database. People
remains the only authority for accounts/employee associations/company roles; no
identity tables are replicated. GraphQL remains the public business boundary.
No project/task/capacity claims or empty future services are added.

## Source implementation

- Administrator Working calendar screen: explicit timezone, seven weekday settings,
  holidays and dated working/non-working overrides. No company values are seeded.
- Actor-bound, server-issued previews show working hours and special dates, expire
  after ten minutes and require confirmation. Editing draft values invalidates the
  visible preview. Publication requests retain their idempotency identifier.
- Immutable calendar publications retain configuration, actor reference, time,
  number and pinned timezone-rule release. Historical versions are not overwritten.
- Publication rechecks current authority after acquiring a per-issuer PostgreSQL
  transaction lock. Competing previews must match the current base version.
  Request replay is bound to the original actor/issuer/preview.
- Independent service-key/JWT authentication and live people-service administrator
  authorization reject forged actor headers and current role revocation. Authority
  outages fail closed. Browser POSTs check exact origin; diagnostics omit secrets
  and protocol addresses/parameters.
- Calculations expose requested/effective starts, counted dates, local/UTC deadline,
  next-working-day handoff, calendar version and timezone-rule release. Durations
  are whole calendar working days, not hourly effort or delivery guarantees.
- Packaged pinned tzdata is loaded explicitly rather than using the host timezone
  database. Missing historical rules fail explicitly instead of silently changing
  a previous calculation. Local DST gaps/ambiguities are rejected.
- Initial work-domain migration matches the models in an isolated SQLite check.
  Downgrade refuses to discard published history. Migration 0001_company_calendar
  is applied only to the new project-work database.

## Actual source evidence

| Check | Result |
| --- | --- |
| Combined backend account/calendar suite | 151 passed, zero skips (115 retained account tests + 36 calendar tests) |
| Calendar calculation/version/API suite | 36 passed, zero skips, including complete typed GraphQL preview/publication/history/calculation, pinned timezone history and hostile timezone-key rejection |
| Structure regressions | 17 passed, zero skips; required S6 CI startup cannot be omitted |
| Repository boundary checks | Passed |
| Frontend lint and typecheck | Passed |
| Frontend formatting | Passed |
| Production web build | Passed with /admin/calendar and its command route |
| Authentication unit suite | 22 passed, zero skips |
| New project-work dependency lock audit | No known vulnerabilities found |
| Web production dependency audit | Zero vulnerabilities |
| Python lint and formatting | Passed |
| PostgreSQL schema/concurrent publication probe | Passed: exact schema parity, competing publication/stale rejection, replay and owned cleanup |
| Retained people PostgreSQL probes | Passed: constraints/rollback, last-admin race and reporting-cycle race; owned cleanup verified |
| Desktop S6 acceptance | 1/1 passed, zero skips; one worker, zero retries |
| Tablet S6 acceptance | 1/1 passed, zero skips; one worker, zero retries |
| Mobile S6 acceptance | 1/1 passed, zero skips; one worker, zero retries |
| Updated desktop administrator regression | 1/1 passed, zero skips; password and revoked-role checks retained |
| Remote CI | Not run for these unstaged changes |

Source verification caught and corrected a test-package name that shadowed the
standard Python calendar module, a circular metadata-sort warning (the named base
version constraint is explicitly applied after table creation), and JSX placement
inside a try/catch. The remaining Starlette/httpx deprecation warning is upstream;
it does not represent a skipped or failing test.

## Runtime proposal and scoped verification

The owner separately approved S6 runtime and scoped tests on 17 November 2026.
The wrapper added project-work and project-work-db, created their fresh named volume,
applied only migration 0001_company_calendar there, and rebuilt/recreated gateway
and web. Existing people, identity, sessions, mailbox and legacy containers/data
remain intact. No .env edits, real email, intentional outages or broad cleanup
occurred. The new database volume was verified absent before creation.

Executed from the repository root after capturing a preservation baseline:

```powershell
python scripts/calendar-development.py up --apply-migration
python scripts/verify-calendar-postgres.py
python scripts/run-s1-acceptance.py --project desktop --calendar-only
python scripts/run-s1-acceptance.py --project tablet --calendar-only
python scripts/run-s1-acceptance.py --project mobile --calendar-only
```

The PostgreSQL probe uses a synthetic issuer and actor UUID, checks real schema
parity, races competing publications, expects one stale-preview rejection, verifies
safe replay and removes only its owned previews/versions.

The browser focus creates a verified disposable administrator fixture, publishes
run-marked temporary calendar versions, checks the approved Friday-to-Tuesday
calculation, confirms a later holiday changes only the new version, recalculates
the old version unchanged, checks origin and non-admin boundaries, and verifies
receipt-bound cleanup. Removing these test-only publications restores the prior
calendar state; no real company values are silently installed. Cleanup refuses
non-owned references and leaves earlier calendar versions intact.

The wrapper requires one executed pass per focused run, zero skips, one worker,
zero retries, cleaned identity/session/grant/calendar receipts, healthy expected
services and unchanged legacy IDs/health. Failure diagnostics are captured before
cleanup with fixed stages and sanitized messages. The normal 45-second test timeout
is unchanged. The new service/database pair is explicitly inventoried; unknown
extra services remain an error.

Fresh CI starts the S6 service, runs its PostgreSQL probe and requires all ten
lifecycle cases on each viewport, plus existing recovery and quality gates. Full
email lifecycle acceptance remains blocked against local live Gmail; calendar-only
acceptance sends no email and never changes SMTP settings.

## Actual runtime and preservation evidence

All three S6 browser journeys passed on their first live executions. They verified
confirmed publication, the approved three-day example, a new holiday's impact only
on the new version, unchanged historical calculation, responsive width, origin
rejection, current non-admin denial and receipt-bound cleanup. The updated S3
navigation/password/revoked-role regression also passed on desktop. No skip or
discovery run is counted. Reports:

- test-results/reports/s1/desktop-calendar.json
- test-results/reports/s1/tablet-calendar.json
- test-results/reports/s1/mobile-calendar.json
- test-results/reports/s1/desktop-admin.json

Independent final comparison, run after the test sequence finished, matches the
pre-runtime baseline for all original columns and values in 2 accounts, 2 employee
profiles, 2 company-role grants, 1 initial-administrator provisioning record,
1 account-provisioning record and 4 account-audit records. Existing organization
records are unchanged. Both new calendar tables have zero residual test rows;
the company calendar remains unconfigured until the owner enters actual values.

All 4 existing realm identities, their credential fingerprints and the full SMTP
fingerprint match the baseline. The exact primary ADMIN remains enabled, its
password is unchanged, and Gmail remains configured as dailygotasks@gmail.com.
No real email was sent. All test identities, app sessions, role grants and calendar
resources were cleaned under the existing receipts and ownership checks.

All 10 portal services and 26 legacy services are healthy. Original mounts and
unaffected container IDs are unchanged; only gateway/web were replaced and the two
approved calendar containers were added. No existing service was stopped for a
recovery scenario and no restoration was necessary. An intermediate read-only
preservation check was issued while tablet acceptance was active and observed its
expected temporary rows; no cleanup was triggered from that comparison. The final
post-suite comparison passed after all test-owned rows were removed.

## Remaining evidence and manual gates

Required local S6 evidence is present. On 17 November 2026, the owner reported
that the working calendar is working. This is owner-reported website confirmation,
not a claim that each flow or source file was manually reviewed. Source/staged-diff
review, manual Git steps and remote CI remain. The full ten-case email lifecycle suite was not run
against live Gmail; fresh isolated CI must supply the complete lifecycle/recovery
results. Do not claim a remote pass or close S6 before those gates are satisfied.
The original plan is unchanged and S7 has not started.
The Git index remains unchanged and empty. No repository-history or branch
operation has been performed. The authoritative plan's SHA256 remains
08af1dd1024824bbc91d7f0433e2e35e45db8b3e7084c9650edb99314199d6fd.
