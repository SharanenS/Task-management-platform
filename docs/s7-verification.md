# S7 manager portal and project creation

Date: 19 November 2026. Branch: s7-manager-projects. Baseline: fd3d36f.
Status: **LOCAL ACCEPTANCE PASSED, including calendar-form refinement; owner review and remote CI pending.**

## Scope and ownership

The immutable product plan defines manager layout, authorized project lists,
creation, creator/current-owner distinction, objectives and approved deadlines.
See s7-project-contract.md for explicit decisions. No S8 membership, leader
appointments, ownership-transfer API, tasks, forecast or progress widgets are added.
The existing project-work service/database owns projects. People remains the only
account/employee/role authority. GraphQL remains the public business API.

Managers enter /manager after sign-in and see only currently owned projects.
Administrators use /admin/projects and may oversee same-company projects. Both
roles can create and become initial owner. EMPLOYEE and HR gain no project
access from their company role. A historical creator does not retain access
when a different current owner is set by a later authorized workflow.

Shared project views/forms live under apps/web/src/project-workspace; manager
layout/navigation are separate from the administrator shell. No old interface
is imported or rendered. Published calendar data is reused, not copied into a
second calendar/identity authority.

## Initial project commitment

An actor-bound server preview holds the name, objectives and explicit agreed
working-date deadline. It resolves configured closing time and pins calendar,
timezone/rule release and UTC/local boundary. Non-working dates are rejected,
not silently shifted. A past deadline is warned about. Creation requires explicit
confirmation, an unexpired preview and the unchanged latest calendar version.

Calendar publication and project commitment share the per-company PostgreSQL
transaction lock. Role/active-account authority is read from people independently
of the gateway and rechecked after waiting. Request and preview uniqueness prevent
duplicate creation. Original deadline snapshots and creator identity are retained;
no later calendar edit rewrites them. Migration rollback refuses to discard
project commitments. The approved local migration reached 0002_manager_projects.

## Actual source verification

| Check | Actual result |
| --- | --- |
| Combined account/calendar/project tests | 163 passed, zero skips |
| S7 project source suite | 12 passed, zero skips |
| Structure regressions | 18 passed, zero skips; S7 browser coverage cannot be removed from full lifecycle |
| Source/execution boundary validator | Passed |
| Frontend lint, formatting and types | Passed |
| Production web build | Passed; manager and administrator project routes generated |
| Python lint and formatting | Passed |
| Authentication protocol tests | 22 passed, zero skips |
| Web production dependency audit | Zero vulnerabilities; dependency manifests/locks are unchanged |
| Real PostgreSQL commitment/calendar races | Passed: schema parity, one commitment per preview, replay, publication race and owned cleanup |
| Desktop S7 browser journey | 1/1 passed, zero skips, one worker, zero retries |
| Tablet S7 browser journey | 1/1 passed, zero skips, one worker, zero retries |
| Mobile S7 browser journey | 1/1 passed, zero skips, one worker, zero retries |
| Updated S3 desktop regression | 1/1 passed, zero skips; administrator workspace, password change and revoked-role denial |
| Retained people PostgreSQL probes | Passed: schema, account concurrency, last-admin protection, reporting-cycle concurrency and owned cleanup |
| Final preservation and health | Passed: all 36 services healthy; existing rows, identities, credentials, SMTP, mounts and unaffected container IDs unchanged |
| Remote CI | Not run for these unstaged changes |

Source tests exercise admin/manager creation, owner-scoped list/search/detail,
non-author rejection, cross-issuer denial, creator-versus-current-owner behavior,
calendar-required and working-date validation, deadline immutability, confirmation,
actor-bound preview expiry/staleness and idempotency. Public/private API checks
verify current role rejection, forged actor-header rejection and identical missing/
unrelated-project responses. The migration test preserves a published calendar
and refuses downgrade after a project commitment.

## Approved runtime and actual cleanup

The owner approved the S7 migration, updates to project-work/gateway/web and
scoped email-free acceptance. Docker became available, with 26 legacy services
healthy and all ten portal containers stopped. Seven existing portal dependencies
were started in place; their container IDs and mounts were preserved. Only the
three approved application services were rebuilt/recreated. No intentional outage,
volume deletion, SMTP change, environment-file edit or unrelated rebuild occurred.

A preservation baseline was captured before rollout. It covered all rows in nine
people tables, realm users/credential digests/SMTP, existing calendar data, service
IDs/mounts and the Git index. Both pre-test and final comparisons passed.
The original company calendar had zero publications and previews. Each S7 browser
run therefore used its marked temporary calendar and removed it after its owned
projects, restoring the original unconfigured calendar state. No company defaults
were left behind. Final project and project-preview counts were zero.

The retained baseline contained two accounts/profiles/role grants, one initial-admin
record, one account-provisioning record, four account-audit records, one department,
one job title, three organization-audit records and four realm identities. All were
preserved exactly, including the enabled primary ADMIN and its credentials.
Gmail status remained configured for dailygotasks@gmail.com; no email was sent.
All 36 services were healthy at completion: ten portal and 26 legacy services.

Executed focused checks from the repository root:

```powershell
python scripts/calendar-development.py up --apply-migration
python scripts/verify-account-entry-postgres.py
python scripts/verify-calendar-postgres.py
python scripts/run-s1-acceptance.py --project desktop --projects-only
python scripts/run-s1-acceptance.py --project tablet --projects-only
python scripts/run-s1-acceptance.py --project mobile --projects-only
python scripts/run-s1-acceptance.py --project desktop --admin-only
```

The PostgreSQL probe uses only a synthetic issuer/actor. It verifies exact schema
parity, competing requests against one preview, safe replay, and a real calendar-
publication/commitment race. Cleanup verifies its ownership before deleting any
probe row. Previously committed calendars/projects remain untouched.

The separate S7 browser journey verifies two marked manager identities, manager
entry and confirmed creation, unrelated list/search/detail denial, administrator
oversight and creation, non-author denial, request-origin checks and responsive
width. It reuses the actual company calendar when configured. If none exists, an
owned temporary fixture calendar is published and removed after owned projects.
No company defaults are permanently installed and no email endpoint is called.

Receipt-bound cleanup verifies exact identity markers/timestamps, account/profile
associations, project creator/current-owner references, preview ownership and
non-owned foreign references before deleting any test row. App sessions and
operator grants are revoked, identities must return 404, and all expected services
must remain healthy with unchanged legacy IDs. Sanitized first-boundary diagnostics
are preserved before cleanup. The primary administrator is never promoted,
deactivated, reset or deleted. Gmail is never switched to capture for these tests.

Full fresh CI now requires 11 lifecycle cases over the original and project specs,
with two independently cleaned run receipts, on each viewport, plus retained
recovery and source/quality gates. Focused local project acceptance requires one
executed pass, zero skips, one worker and zero retries. The 45-second timeout is
unchanged. Full email lifecycle acceptance remains guarded against live Gmail.

## Failures diagnosed and corrected

The first two image builds failed on incomplete package downloads (cffi, then
cryptography), before any migration or service replacement. A subsequent attempt
encountered a truncated package-index response. Gateway and project-work builds
now use pip's bounded --resume-retries 3 option; the final canonical builds passed.
No dependency version, test timeout or test retry count changed.

The first desktop S7 browser attempt timed out before signing in because its new
helper used the label "Sign in". The existing interface correctly exposes
"Continue to sign in". The helper now targets that exact accessible name.
The sanitized boundary diagnostic was retained before cleanup; that failed run's
receipt also verified complete scoped cleanup. The corrected desktop journey,
then tablet/mobile journeys and the S3 desktop regression all passed separately.
No failed or skipped attempt is counted as a pass.

Sanitized reports are under test-results/reports/s1/{desktop,tablet,mobile}-projects.json
and desktop-admin.json. First-boundary diagnostics are under test-results/reports/s7;
private ownership receipts remain under .local/auth/runs. These ignored runtime
artifacts are excluded from the change set. Reports contain no passwords, tokens,
raw OIDC addresses or query parameters.

## Owner review and remaining gates

Open http://127.0.0.1:3020/admin/projects as ADMIN. Publish the real company calendar
at /admin/calendar before creating an actual project; disposable test calendars
were removed. A real MANAGER account enters /manager and sees its owned projects.
Check project objectives, working-date validation, preview/confirmation, creator
and current-owner labels, and the retained original deadline on project details.
No permanent manager account was created by acceptance.

Source and approved local acceptance gates passed. Owner website/source review
and remote CI after manual Git steps remain pending; no remote green result or
merge is claimed. Full email lifecycle and recovery suites were not run locally
against live Gmail. Their retained isolated CI gates remain required; the full
lifecycle now includes the new S7 case. S8 has not started.

The original plan remains unchanged. All edits remain unstaged, and read-only Git
checks confirm the index is unchanged. No repository-history or branch operation
was performed.

## Subsequent calendar-form refinement — 19 November 2026

The owner requested calendar creation without a timezone field. See
calendar-local-time.md for the separate amendment and exact verification results.
The source detects the first calendar's local setting and retains the stored
setting on later edits. Calendar history, UTC boundaries and authorization remain
in place. The owner approved the web-only update and scoped tests; only web was
rebuilt/recreated. No new migration, backend recreation or SMTP change occurred.

The canonical container production build passed. Calendar journeys passed on
desktop, tablet and mobile separately (each 1/1, zero skips), including automatic
detection, exact offset-aware deadlines and preservation when device settings
change. Desktop project acceptance passed again (1/1, zero skips). Every run used
one worker, zero retries and verified owned cleanup. The earlier Windows-native
build failure at CSS worker startup remains documented; it was not counted as a pass.

A new pre-update baseline and independent final comparison confirmed exact
preservation of existing people/calendar/project rows, realm identities,
credentials, Gmail configuration, mounts and all 35 non-web container IDs.
All 36 scoped services were healthy. Original calendar/project tables were empty
and are empty again after removal of test resources. No permanent sample calendar
was installed. ADMIN was preserved. Source calendar tests (36, zero skips),
frontend formatting/lint/typecheck and Python fixture checks passed.

The original plan and Git index are unchanged. All changes remain unstaged.
Owner website/source review and remote CI remain pending; S8 has not started.
