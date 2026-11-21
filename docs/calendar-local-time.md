# Company calendar local-time entry

Owner-requested refinement, 19 November 2026. The original product plan is unchanged.
This replaces the manual timezone-entry requirement in the S6 implementation.

The calendar form has no timezone field. The first publication detects the
administrator device's named local time setting automatically. The preview shows
that local-time reference before confirmation. Days, hours and holidays still
require actual company values. If detection fails, publication is blocked with
an actionable message rather than inventing a default.

Later edits retain the published company setting, including when the administrator
uses a device in another region. The service continues validating named time rules
and retaining calendar/deadline versions and UTC boundaries. Earlier commitments
are never reinterpreted using the current browser or server time setting.

The browser acceptance checks first-publication detection, no timezone input,
confirmed publication, exact local deadlines with the appropriate offset,
preservation across a different device setting, and historical calculations.
Source verification: 36 calendar tests passed, zero skips; Python fixture lint
and formatting passed; frontend formatting, lint and type checks passed.
The Windows production build failed at the Turbopack CSS child-process boundary
(exit before connection), both with restricted and normal local process access.
No application assertion or timeout was changed to bypass that failure.
The owner approved the web-only rollout and scoped tests. The canonical web
container production build passed, including TypeScript. Only the web container
was recreated; no backend service or migration was changed.

## Actual runtime verification

| Check | Result |
| --- | --- |
| Desktop calendar publication/history/authorization | 1/1 passed, zero skips |
| Tablet calendar publication/history/authorization | 1/1 passed, zero skips |
| Mobile calendar publication/history/authorization | 1/1 passed, zero skips |
| Desktop manager project creation and role isolation | 1/1 passed, zero skips |
| Scoped cleanup and operator-grant revocation | Verified after every journey |
| Independent final preservation check | Passed; all 36 services healthy |

Every browser run used the credential-safe root wrapper, one worker, zero retries
and the unchanged 45-second timeout. The calendar journeys verified automatic
first-publication detection, no timezone field, preview and explicit confirmation,
exact local deadline/offset calculations, unchanged saved settings after a
different device setting, historical calculation and non-administrator denial.
The project journey verified confirmed creation, current-owner isolation,
administrator oversight and rejection of non-author roles.

A fresh baseline covered current people rows, realm users/credential digests/SMTP,
calendar/project rows, mounts, all 36 scoped service IDs and the Git index. The
final comparison matched every original row and mount. All 35 backend/legacy
container IDs stayed unchanged. ADMIN remained enabled with unchanged credentials;
Gmail remained configured as dailygotasks@gmail.com. No real email was sent.

The original calendar/project tables were empty. Marked temporary publications,
projects, previews, accounts, identities and application sessions were removed;
no sample calendar or company defaults were left behind. Configure the actual
working days and hours at http://127.0.0.1:3020/admin/calendar, preview, confirm
and publish. The running page now needs no manually entered timezone.

Sanitized passing reports are in test-results/reports/s1/desktop-calendar.json,
tablet-calendar.json, mobile-calendar.json and desktop-projects.json. Private
cleanup receipts and preservation digests remain ignored local artifacts.
The earlier Windows-native CSS-worker build failure remains recorded above;
the successful canonical container build and live acceptance are separate evidence.
Remote CI and owner review remain pending. The original plan and Git index are
unchanged; all source changes remain unstaged. S8 has not started.
