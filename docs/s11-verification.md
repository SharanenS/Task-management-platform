# S11 leader workspace verification

Status: **in progress — local acceptance passed; owner website review and remote CI pending**.
Branch: s11-leader-workspace. Baseline: merged S10 commit 07cc161.
Date: 24 November 2026. Initial worktree and index were clean.

## Resulting behavior

The current EMPLOYEE leader plans tasks only in the appointed project. Tasks
require instructions, acceptance criteria and one eligible active employee
assignee; leaders may assign themselves. Pending edits and reassignment require
a reason, confirmation, current authority and version checks. Reassignment retains
the previous assignment and before/after history, with readable historical names.

Owner/ADMIN oversight is read-only for task planning. Contributors see colleagues'
titles, assignee names and general status; private details belong to the current
assignee and authorized supervisors. Former assignees lose private access on
reassignment, and removed leaders lose project access immediately. No scheduling,
progress, completion, cancellation or approval actions were added from later stages.
See [task planning contract](s11-task-planning-contract.md).

Three additive project-work tables are applied at migration head
0006_task_breakdown. A partial unique index enforces one active assignment.
Source and PostgreSQL probes verified schema parity, retained S10 commitments/
decisions, stale/repeat request safety and competing reassignment behavior.

## Final actual evidence

| Check | Result |
| --- | --- |
| Focused S11 source/API/migration/cleanup contracts | 49 passed; zero skips |
| Complete backend regression | 306 passed; zero skips on final production/fixture source |
| Authentication unit tests | 22 passed; zero skips |
| Repository structure/CI omission guards | 26 passed; zero skips |
| Backend and operation lint/format | Passed across 111 selected files; E/F/I and 100-column rules |
| Frontend lint, formatting and typecheck | Passed, including final prospective and retained browser specs |
| GraphQL schema and generation | Executable schema parity passed; repeat operation generation byte-identical |
| Production builds | people, project-work, gateway and web built; Next production build passed |
| S11 PostgreSQL probe | Assignment race, single winner, replay, private projection, history and exact owned cleanup passed |
| S11 desktop / tablet / mobile, separate credentialed runs | 4/4 each; 12 passes; zero skips |
| Retained desktop owner decisions | 5/5 passed; zero skips |
| Retained desktop coordination | 4/4 passed; zero skips |
| Retained desktop membership | 3/3 passed after bounded setup correction; zero skips |
| Retained desktop projects | 1/1 passed; zero skips |
| Retained desktop calendar | 2/2 passed; zero skips |
| Retained desktop administrator workspace | 1/1 passed; zero skips |
| Retained desktop account entry/direct GraphQL | 1/1 passed; zero skips |
| Frontend production dependency audit | 0 vulnerabilities |
| Final independent data/service/index comparison | Passed |

The 29 final browser passes exclude failed/skipped attempts below. Playwright ran
from apps/web through the repository-root wrapper, one worker, zero retries,
unchanged 45-second case/hook limit. Each successful wrapper verified its scoped
receipt, account/identity/session/resource cleanup and healthy portal services.

All retained PostgreSQL wrappers also passed: owner deadline decisions,
coordination follow-up races/history, membership leader races/history, calendar
publication and project commitment races/replay, account constraints/concurrency/
last-administrator protection, and reporting-cycle safety. Each verified scoped
rollback or owned cleanup. No skip or discovery run is counted as a pass.

## Approved runtime and preservation

The owner approved the migration, four-service update, scoped runtime checks and
CI integration. A fresh S11 baseline captured 45 Compose containers, 3 accounts/
profiles/role grants, 5 realm users, primary ADMIN, provisioning and account/
organization audit rows, credential/SMTP checksums, and existing work data.
There was one original calendar/preview and one project/preview; membership,
coordination and S10 oversight tables were empty. The task tables did not exist.
No previous-stage baseline was reused.

Only people, project-work, gateway and web were rebuilt/recreated. The final
independent comparison matched every original people/work row checksum, realm
identity/credential/SMTP checksum, primary ADMIN, mounts, unaffected container ID
and Git index. The three new task tables were empty after scoped cleanup. All
45 Compose containers remained accounted for: 39 originally running containers
healthy, 6 previously stopped containers unchanged. Portal health was independently
verified by each wrapper. No volume was removed, no legacy service replaced, no
real email sent and no recovery outage simulation performed. Root .env was not edited.

S11 acceptance uses three distinct receipt-owned identities: manager/owner,
employee/leader and employee/contributor. The third employee has exact run,
subject, profile, role and creation-time ownership proofs. Its account and realm
identity absence are mandatory cleanup flags. Existing two-identity journeys keep
their original scope; the extra actor is allowed only with the verified peer
subject. Foreign/mismatched fixture data stops cleanup rather than being deleted.

## Failed attempts and justified corrections

- The first desktop attempt timed out at the initial Keycloak fixture authorization
  before identities were created. Later setup hooks lacked their prerequisite.
  A follow-up probe of the exact operation returned HTTP 200 in 722 ms and its
  grant was revoked with HTTP 204. Independent baseline comparison passed. The
  initial incomplete receipt remains blocked, never relabelled as cleaned/passed.
- Fixture drafts exposed an unsupported secondary-admin state and the existing
  rule rejecting a project owner as a normal contributor. These remained denied.
  The final journey uses distinct owner, leader and contributor identities; no
  application permission or existing fixture role restriction was relaxed. Five
  source regressions verify third-employee cleanup and preservation of mismatched
  subject/profile/role data and existing identities.
- A prefilled edit textarea included its value in exact label text. Isolated
  accessibility inspection confirmed the textbox name “Instructions”; the test
  now uses its exact role/name. The next display assertion matched both paragraph
  and textarea, so it now requires the exact display paragraph. The edit itself
  succeeded. All authorization, history, replay and cleanup assertions remain.
- Retained S8 membership preparation exceeded the combined setup hook while
  preparing identities, projects and sign-ins. Cleanup passed. Identity preparation
  is now a separate bounded hook, with specific project-preview/creation/sign-in
  diagnostics. All three membership cases passed on the rerun. No timeout was
  increased, assertion removed or scenario skipped to obtain a pass.

Sanitized failure reports and unique boundary diagnostics were saved before
cleanup; no credential, bearer token, raw OIDC URL or query parameter is required
in these records. The final diagnostic token-pattern scan found no candidates.
No additional service rebuild was needed for fixture/locator-only corrections.
During source development, fixture-name and HTTP-denial envelope expectations
were corrected, and lint removed an unintended task-dispatch block from account
administration before any runtime update. Final backend regression passed.

## CI and remaining gates

Existing CI jobs and the quality gate remain required. S11 source, runtime and
PostgreSQL checks are added to the retained pipeline. The full browser lifecycle
now requires 28 executed cases and six cleaned receipts, including five project-
domain owner/task cleanup proofs and one verified third-employee cleanup. Focused
S11 requires four passes and its verified receipt. Gmail-safe guards, retries and
timeouts remain unchanged; CI YAML and omission guards passed locally.

The complete email lifecycle and recovery suite was not run locally against
configured Gmail. Fresh isolated remote CI must run these retained gates after
the owner's manual push. Backend dependency locks are unchanged; remote lockfile
audits remain required and are not claimed as rerun locally. Local engineering
verification is ready for owner review; S11 completion awaits website acceptance
and passing remote CI. S12 has not started.

## Manual website review

Open http://127.0.0.1:3020. As ADMIN or the current manager owner, open Projects →
a project → Work breakdown for read-only oversight. Appoint an eligible EMPLOYEE
as its leader through Project membership, then sign in as that employee and open
Assigned projects → Work breakdown. Create a task with instructions, criteria,
assignee and reason; edit/reassign pending work and inspect readable history.
Contributors may see their own details and colleagues' summaries. Original test
records were removed, so an empty task list is expected before real work is entered.
Owner-created review data is real audit data and is not automatically deleted.

The original plan SHA256 remains
08af1dd1024824bbc91d7f0433e2e35e45db8b3e7084c9650edb99314199d6fd.
All resulting edits remain unstaged; no Git mutation was performed. Proposed commit:
`add S11 contextual leader task planning and reassignment history`.
