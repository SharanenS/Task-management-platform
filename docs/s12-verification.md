# S12 task scheduling verification

Status at local handoff: **local functional acceptance passed; environment health, owner review and remote CI were open**.

Post-merge update — 28 November 2026: the owner reported a successful merge.
Main commit 3589a6380d2118e4f344019b7bf7cc13467b13cd passed
[post-merge CI 46119194721](https://github.com/SharanenS/Task-management-platform/actions/runs/46119194721).
The earlier local results and separate Kafka health exception below remain historical evidence; no Kafka fix is claimed.
Dates: 27–28 November 2026. Branch: s12-task-scheduling. Baseline: 0763746.
The initial worktree and index were clean. The original development plan is unchanged.

## Resulting behavior

See [the scheduling contract](s12-scheduling-contract.md). Current project leaders
preview and confirm private working-day schedules and dependencies. Independent
work may overlap, with explicit warnings rather than capacity guarantees. Missing
or overdue incomplete inputs produce unknown forecasts. Original commitments,
revisions, approved project deadlines and forecasts remain separate. Scheduling
does not start, complete or approve work. Owner/ADMIN access remains read-only;
contributors receive only their own schedule details.

Four additive tables follow migration 0006: task_schedules, task_dependencies,
task_schedule_previews and task_schedule_changes. PostgreSQL independently reported
head 0007_task_scheduling. Existing rows remain unscheduled until explicitly planned.

## Source evidence

| Check | Actual result |
| --- | --- |
| Focused S12 source contracts | 37 passed, zero skips |
| Backend regression | 345 passed, zero skips |
| Web authentication and timezone units | 25 passed, zero skips |
| Repository structure suite | 31 passed, zero skips |
| CI-configured Ruff lint and formatting | Passed; 145 files formatted |
| Frontend lint and typecheck | Passed, including final owner-test synchronization |
| Frontend formatting | Passed; final owner/helper formatting and focused lint passed |
| Production Next.js build | Passed, including protected scheduling routes |
| Executable GraphQL schema and export | Match; backend regression covers parity |
| Repeated frontend code generation | Byte-identical |
| Workflow lane and mandatory cleanup contracts | Passed |

Source XML evidence is under ignored test-results/reports/s12. A deprecated
Starlette/httpx test-client integration emits one warning; assertions pass.
Restricted local HTTP transport and a build CSS-worker connection initially failed;
both checks passed with local execution access. No framework dependency, timeout,
retry setting or authorization assertion changed. The repository's explicit CI
E/F/I and 100-column Ruff settings passed; unrelated stricter inherited rules were
not applied as fixes to existing code.

## Approved runtime and passing acceptance

The owner approved four scheduling tables and updates only to project-work,
gateway and web. All three images built successfully. A later web-only update
corrected project-zone preview formatting, and a project-work-only update applied
two reviewed cutoff/readiness fixes. No other service was recreated. No real email,
intentional outage, new service, volume cleanup or legacy change was performed.

Five PostgreSQL probe wrappers passed: scheduling, task planning, owner decisions,
membership and calendar. They include schema parity, one-winner competing commits,
actor-bound replay, dependency handoff, cycle rejection, history, original deadline
preservation, publication/project commitment races and exact synthetic-issuer cleanup.

| Credentialed desktop/tablet/mobile scope | Final actual result |
| --- | --- |
| S12 desktop scheduling | 4/4 passed, zero skips; repeated on final backend image |
| S12 tablet scheduling | 4/4 passed, zero skips |
| S12 mobile scheduling | 4/4 passed, zero skips |
| Retained S11 desktop task planning | 4/4 passed, zero skips |
| Retained S10 desktop owner decisions | 5/5 passed, zero skips |
| Retained S8 desktop membership | 3/3 passed, zero skips |
| Retained S6 desktop calendar | 2/2 passed, zero skips; scoped cleanup verified |

S12 proves confirmed UI planning, dependency/parallel warnings, cycle rejection,
private projection, owner read-only access, cross-origin rejection and immediate
removed-leader read/write denial. The leader browser uses America/Los_Angeles while
preview display is asserted in the actual project's pinned timezone. Successful
runs have cleaned receipts and explicit session, schedule, peer identity/account,
bootstrap and grant proofs. The wrapper requires four executed scheduling cases,
zero skips and exactly one owned receipt. Discovery and failed/skipped attempts
are excluded from acceptance. Successful summaries are under test-results/reports/s1.

## Failures, corrections and recovery

- Initial desktop operator token bootstrap exceeded its existing five-second
  boundary before identity creation: 0/4 passed, three skipped. Its blocked receipt
  remains blocked. Independent preservation proved no application/identity resources
  remained. A diagnostic returned HTTP 200 in 4,498 ms under the same limit and
  revoked its grant with HTTP 204. A fixed diagnostic now identifies that boundary.
- First tablet run passed three functional cases, then its combined cleanup hook
  exceeded 45 seconds. Exact ownership recovery found two identities absent and one
  remaining; it removed only the marked remaining identity, original operator session
  and owned rows/sessions, and revoked the recovery grant. The receipt retains its
  original failed outcome. Cleanup now has named session/domain/peer/account/identity/
  operator phases and a mandatory final receipt. Each retains the original limit;
  every proof is required even after another phase fails. Responsive reruns passed.
- Preview display used viewer-local formatting despite its project-zone label.
  A shared pinned-zone formatter, three unit tests and cross-zone UI proof corrected it.
- Review found two backend edge cases. Overdue otherwise-ready work must remain
  startable without moving original dates; an assessment must not survive its exact
  finish cutoff. Both fixes passed source regressions and were deployed only to
  project-work before the final scheduling desktop confirmation.
- Two retained task attempts failed at operator bootstrap before creating identities
  (0/4, three skipped each). A direct diagnostic later returned HTTP 200 in 2,594 ms
  under the unchanged limit and revoked its grant with HTTP 204. Another attempt
  created its third disposable identity but lost the response; cleanup missed its
  unrecorded ID. Independent identity-digest comparison detected the mismatch.
  Exact username/email/run-attribute/creation-window recovery removed only that
  identity and verified all three absent. The helper now journals uncertain creation,
  resolves only ownership-verified matches, and requires exact-name absence before
  accepting cleanup. Ambiguous ownership or unavailable lookup blocks the receipt.
  Two source regressions cover peer absence when setup fails before the primary
  account. A live probe deliberately discarded the third successful creation response
  and passed exact recovery, account/identity cleanup and grant-preservation checks.
- A subsequent retained task attempt timed out in its original fixture sign-in/
  calendar setup hook before task assertions (0/4, three skipped). Phased cleanup
  passed. The final healthy-state rerun passed all four unchanged task cases.
- Retained owner acceptance first passed one case, then missed the Inactive fallback
  heading after revocation (1/5, three skipped); combined cleanup also stopped early.
  Scoped recovery found one identity already absent, removed the other, verified zero
  owned work/account/profile/grant/session rows and revoked the exact original operator
  session and recovery grant. Another run timed out in setup (0/5, four skipped), with
  phased cleanup verified. Response instrumentation then proved revocation HTTP 200
  but incorrectly tried to read a body already discarded during navigation. The test
  now checks the exact-origin revocation response and waits for the expected reload
  before the unchanged Inactive fallback assertion. All five owner cases and phased
  cleanup passed on the corrected test. No owner authorization behavior was changed.
- The first retained calendar run failed both cases (0/2, zero skips). Its first
  boundary was preview/publication: Review calendar changes was absent within the
  existing five-second assertion. The second reached authorization/origin checks,
  then its response was disposed. Those records do not establish the API result;
  no calendar product change is claimed. Calendar/account rows were cleaned; scoped
  recovery verified the identity and application sessions absent, no original operator
  sessions left in that run window, and recovery-grant revocation. The final rerun
  passed both unchanged calendar cases with verified cleanup.

All sanitized boundary, bootstrap, failed-run, scoped recovery and fault-injection
records remain under ignored test-results/reports/s12 and the original S6/S10/S11
report directories. No credentials or raw OIDC links are included. Earlier failed
runs are not converted into passes.

## Preservation and remaining gates

The fresh pre-migration baseline captured 3 accounts/profiles/role grants, 5 realm
identities, existing company/work records and 45 Compose resources. A full comparison
after owned recovery and membership acceptance passed: original data, realm identity/
credential/SMTP digests, enabled primary ADMIN, mounts, unaffected IDs and Git index
were preserved. All originally healthy services were healthy and previously stopped
services unchanged; new scheduling tables and all owned test data were empty.

Intermediate checks caught temporary web health failures and later unhealthy Kafka
in the separate deploy project. Both recovered without a restart or configuration
change by this work. Resource inspection showed substantial unrelated CPU use;
that is context, not proof of a particular test failure's cause. The final calendar
run was followed by another full comparison. Every successful wrapper independently
verified ten healthy portal services and unchanged legacy IDs/health.

CI retains four independent desktop/tablet/mobile/recovery lanes and mandatory
aggregate/final gates. Full lifecycle requires 32 cases per viewport, seven owned
receipts, six project-domain cleanup proofs and two extra employee cleanup proofs.
Recovery still requires both outage cases and the restored lifecycle. No outage or
real-email journey ran locally during S12; broader CI remains for the owner's manual
push. S11 PR and post-merge CI previously passed.

All 26 distinct selected browser cases now have passing runs with zero skips:
12 responsive scheduling cases and 14 retained desktop task/owner/membership/calendar
cases. Repeated desktop confirmations are not double-counted. Every successful
scope verified cleanup, ten healthy portal services and unchanged legacy IDs/health.

The final fail-closed preservation report, preservation-final.json, verifies all
original people/work rows, realm identities/credentials/SMTP, enabled primary ADMIN,
mounts, all unaffected container IDs, Git index and owned-test-data absence across
45 resources. Its sole health exception is deploy:kafka. The unrelated container
remains running but its last five health checks each exceeded its existing five-second
limit. Earlier a full comparison passed when it recovered; the latest result is
failed rather than reported as universally healthy. It was never stopped, rebuilt,
restarted or reconfigured by this work. All ten portal services remain healthy.

No local functional-test gap remains. Separate Kafka health, owner website review
and remote S12 CI remain open; S12 is not marked complete.
All source changes remain unstaged; no Git mutation was performed. S13 has not started.
