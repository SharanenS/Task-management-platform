# S8 project membership and team leadership verification

Date: 21 November 2026. Branch: s8-project-membership. Baseline: 2f9d910.
Status: **LOCAL ACCEPTANCE PASSED — ready for owner review; remote CI and merge pending.**

The owner explicitly approved S8 source, migrations and source checks, and chose
EMPLOYEE-only appointments. The original plan is unchanged. See
s8-membership-contract.md for authority, privacy, concurrency and scope decisions.

## Implemented source

- Project-work membership/current-role checks, confirmed appointments/removal,
  retained history, replay protection, expected-version conflicts and one-leader
  database uniqueness. Migration 0003 preserves S7 projects and calendar references.
- A minimal people-owned eligible-employee lookup, with no duplicated employee
  authority in project-work. Inactive, unlinked, cross-company, HR and MANAGER
  targets are rejected. Private and public APIs independently enforce authority.
- Typed public GraphQL contracts and generated frontend operations. ADMIN/owner
  membership screens, contextual EMPLOYEE project access and per-project leader
  versus contributor responsibility. No global leader role is introduced.
- Scoped source fixtures, a three-case browser journey and a synthetic-company
  PostgreSQL race probe. Runtime commands were executed after explicit approval.

## Actual checks

| Check | Result |
| --- | --- |
| Combined account/calendar/project source suites | 191 passed, zero skips |
| Focused S8 membership/directory/migration source suite | 28 passed, zero skips |
| Structure regressions | 20 passed, zero skips, including S8 runtime and full-lifecycle omission guards |
| Repository boundary validator | Passed |
| Backend/source-script lint and formatting | Passed |
| GraphQL schema and generated operation reproducibility | Passed |
| Frontend formatting, lint and types | Passed |
| Authentication unit tests | 22 passed, zero skips |
| Windows-native production build | Failed before page generation at CSS worker startup; the same boundary recorded during S7 |
| Production container build | Passed, including all new routes and TypeScript |
| Live migration | Applied 0003_project_membership to the existing project-work database |
| Account/calendar/project PostgreSQL regressions | Passed, including scoped rollback/cleanup and last-admin preservation |
| S8 PostgreSQL membership probe | Passed: schema parity, competing leaders, replay, retained history, revocation and owned cleanup |
| Desktop S8 journey | 3/3 passed, zero skips; cleaned receipt verified |
| Tablet S8 journey | 3/3 passed, zero skips; cleaned receipt verified |
| Mobile S8 journey | 3/3 passed, zero skips; cleaned receipt verified |
| Retained desktop S7 project journey | 1/1 passed, zero skips; cleaned receipt verified |
| Retained desktop S6 calendar journey | 1/1 passed, zero skips; cleaned receipt verified |
| Final preservation/health/cleanup | Passed: all original rows, credentials, SMTP and mounts unchanged; all 36 services healthy; all five cleanup receipts verified |
| New CI runtime/full-lifecycle integration | Integrated after approval; source/structure guards passed, remote execution pending |
| Remote CI | Supplied S8 run: 13/14 desktop cases passed; obsolete protected-entry expectation failed. Corrected focused check passed locally; new CI run pending |

The source tests exercise one account leading/contributing in different projects,
unrelated/cross-company denial, stale role rejection, inactive target rejection,
private peer-field redaction, immediate subsequent-request revocation, creator and
deadline preservation, leader uniqueness, safe replay and conflicting requests.
The migration check upgrades an S7 project/calendar snapshot, compares schema to
models and refuses downgrade after membership history exists. Existing S2-S7
source regressions remain in the combined run.

Initial source-test failures were diagnosed as a detached test-fixture reference
and an assertion expecting a GraphQL error when the correct inactive-account
response is HTTP 403. Both fixtures/assertions were corrected, retaining the denial
requirement. Frontend type/lint findings were corrected without changing access
checks. No failed or discovery-only run is counted as acceptance.

## Approved runtime work

The owner approved local runtime, scoped tests and CI integration. Migration 0003
was applied only to the private project-work database. Only people, project-work,
gateway and web were rebuilt/recreated. The final web build also corrected the
employee sign-in copy to direct users to assigned projects, and added a contextual
skip link and long-text wrapping. Both canonical container builds passed; the
Windows-native CSS-worker failure is separate and remains documented above.
There were no new services, databases, public ports, dependencies or intentional
outages, and no .env or SMTP edit.

A fresh pre-update baseline captured current rows/credentials/SMTP and container
IDs/mounts. It includes three accounts, five realm identities, one existing project,
one project preview, and one calendar publication/preview. Older empty-calendar
baselines were not reused. The update changed only the four approved service IDs.
The initial post-update comparison passed with all 36 scoped services healthy. The
scoped browser journeys create two marked disposable identities and owned projects
with appointments/history, then remove only verified test resources. They reuse
the actual calendar, or temporarily publish a marked fixture only if none exists.
No real email was sent; Gmail remained configured as dailygotasks@gmail.com.

Executed commands:

```powershell
python scripts/membership-development.py up --apply-migration
python scripts/verify-account-entry-postgres.py
python scripts/verify-calendar-postgres.py
python scripts/verify-membership-postgres.py
python scripts/run-s1-acceptance.py --project desktop --membership-only
python scripts/run-s1-acceptance.py --project tablet --membership-only
python scripts/run-s1-acceptance.py --project mobile --membership-only
python scripts/run-s1-acceptance.py --project desktop --projects-only
python scripts/run-s1-acceptance.py --project desktop --calendar-only
```

The three-case membership journey checks confirmed UI appointment; the same login
leading one project and contributing to another; unrelated scope and member-grant
denial; active-account/role changes; administrator removal/history; and request
origin checks. It uses one worker, zero retries and the existing 45-second timeout.
Cleanup verifies exact identity markers, timestamps, account/profile associations,
project ownership and appointment/history references before deleting test rows.
Foreign references cause cleanup to stop, rather than delete user data. Each
failure gets a separate sanitized report before cleanup. No raw OIDC addresses,
query parameters, passwords or tokens belong in diagnostics.

After explicit approval, the S8 source runner, membership runtime and PostgreSQL
checks were integrated into CI. The full lifecycle now requires 14 executed cases,
zero skips and three independently cleaned receipts on each viewport. The opt-in
membership focus requires three executed passes and one cleaned receipt. The
existing real-email guard and recovery gates remain in place. The full email
lifecycle/recovery suite is not run locally against the configured Gmail sender;
remote isolated CI remains required after manual Git steps.

## Final preservation evidence

Independent comparison to the fresh baseline passed after all five browser runs.
All nine existing people tables matched exactly: three accounts/profiles/grants,
one initial-admin record, two provisioning records, ten account-audit records,
one department, one job title and three organization-audit records. All five
pre-existing realm identities and credential/SMTP fingerprints were preserved;
the dedicated ADMIN remained enabled with unchanged credentials.

The existing calendar publication/preview and project/project-preview rows were
preserved exactly according to normalized row digests, including creator, owner,
original deadline and version. The new membership/history tables were empty after
cleanup. S8 and S7 journeys reused the real calendar. The S6 regression published
only marked temporary versions and removed those, restoring the original version.

All 36 scoped services were healthy. Only the four approved application container
IDs changed; all 32 other IDs and every mount stayed unchanged, including all 26
legacy services and persistent database volumes. No broad cleanup occurred.
All five run receipts verified identity/account removal, membership/project/calendar
and organization cleanup, bootstrap preservation and operator-grant revocation.
Owned application session records were removed before test contexts closed.

Passing browser reports are under test-results/reports/s1/{desktop,tablet,mobile}-membership.json,
desktop-projects.json and desktop-calendar.json. The sanitized real PostgreSQL
report is test-results/reports/s8/postgres.json, with source reports beside it.
Runtime reports, ownership receipts and preservation fingerprints remain ignored
local artifacts. No skip or discovery run is counted as acceptance.

## Owner review and remaining gates

Open http://127.0.0.1:3020/admin/projects as ADMIN, open a project, then choose
Project membership. Search for an eligible EMPLOYEE account, select Contributor
or Team leader, enter responsibilities, confirm and save. Select an existing
appointment to change or remove it. Demote/remove the current leader before
appointing another. The initial bounded roster supports 100 distinct appointments,
including removed records, as documented in the contract.

Sign in as an appointed EMPLOYEE and use Open assigned projects. Each project
shows its own current responsibility; leadership in one does not change authority
in another. Members cannot manage appointments, read management history or see
peers' detailed responsibilities. No permanent acceptance accounts were left behind.

The S8 implementation and approved local acceptance are verified. Owner website/
source review and remote CI after manual Git steps remain pending; no remote green
result or merge is claimed. No S9 work has started. The original plan is unchanged;
all edits remain unstaged and read-only Git checks confirm the index is unchanged.

## Protected-entry CI correction — 23 November 2026

The supplied PR #32 log records 13/14 desktop cases passed, zero skipped. The
failure at authentication.spec.ts:599 was the old expectation that /projects was
an unavailable route. S8 intentionally introduced this protected contextual route;
an unauthenticated request now redirects to /sign-in. All three S8 cases and the
remaining authentication/project/calendar cases passed in the supplied run. The
quality gate correctly failed because the authentication job did not fully pass;
tablet/mobile CI steps were not reached.

The existing test now checks exact sign-in redirects and the sign-in heading for
/projects and a nested project-membership route, and verifies that neither creates
an application session cookie. Existing no-old-interface, canonical-origin,
responsive-width and expired-entry assertions are retained. No product code,
authorization rule, cleanup rule, timeout, retry count or CI gate was weakened.

Focused lint, formatting and type checks passed. The exact corrected test body was run in a credential-free,
ignored temporary harness using the existing desktop/tablet/mobile settings,
one worker, zero retries and the unchanged timeout: 3/3 executed passes, zero
skips. The passing sanitized report is
test-results/reports/s8/protected-entry-correction.json.
No credentials were loaded, no identities/accounts were created, and no service,
SMTP, database, existing data or environment file was modified by this check.
The complete credentialed 14-case suite was not rerun locally against live Gmail;
remote CI must run on the new correction commit before merge.

The original plan is unchanged. The two correction files remain unstaged for
owner review; Git history and index were not changed.
