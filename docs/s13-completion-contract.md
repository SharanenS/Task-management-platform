# S13 completion review and leader-owned work

This supplements the unchanged original development plan and reuses the existing
people, project-work, gateway and web boundaries. No new service or dependency is
introduced. Execution/review truth stays in project-work's PostgreSQL database.

## Scope and transitions

The current assignee alone starts eligible work, reports progress/blockers and
submits completion evidence. The shared domain/API contract supports assignees;
S13 exposes execution controls for the contextual leader's own work. The employee
shell and employee execution interface remain later S15/S16 stages. Contributors'
submissions in S13 acceptance use the shared authenticated API, not a fake employee
portal. Managers and ADMIN do not become task assignees through their company role.

Start requires the S12 known schedule, reached start date and COMPLETED prerequisites.
Awaiting review does not satisfy a dependency. An approved completed prerequisite
remains completed when its former assignee becomes inactive; the new assignee
still needs current eligibility and the date/readiness gates. Starting writes a separate actual
start; it never shifts the planned start, duration, original/current schedule or
project deadline. Overdue work remains open and otherwise-ready late starts remain
allowed without moving commitments.

Transitions are PENDING -> IN_PROGRESS -> AWAITING_REVIEW -> COMPLETED. Return for
changes moves AWAITING_REVIEW -> IN_PROGRESS, retaining submission and feedback.
Reporting 100 percent does not approve or complete work. Approval does not rewrite
the last assignee-reported percentage; accepted completion is a separate outcome. Submission is a completion
claim with evidence and confirmation; approval establishes accepted completion.
Blockers remain separately reported information, not a fifth lifecycle state; they
do not implicitly prohibit reporting progress. Clearing a blocker is an explicit
progress update. Earlier notes and blocker values remain in work-update history.
No cancellation, administrative reassignment of started work, reopening, extension
approval, notification delivery or project-delivery policy is introduced here.

## Review authority and separation

Current active EMPLOYEE project leaders review submitted work. Their own submissions
appear in the same queue. Own approval requires a separate explicit self-confirmation;
it is recorded as self-approval, never presented as independent review. Submission
and approval are separate commands and transactions. Returning one's own submission
does not falsely create a self-approval flag.

Owner/ADMIN can inspect submissions, but can decide only with an active explicit
S10 absence record scoped REVIEWS or BOTH, bound to the current leader/vacancy and
inside its time window. EXTENSIONS-only records grant no completion-review right.
Logout never creates absence. Each fallback decision retains the exact record ID;
revocation, expiry and changed leadership take effect at the next command. An
unrelated manager, HR role, ordinary contributor or removed leader gains no review
permission from a client-supplied role/header or hidden menu.

## History, privacy and time

Three additive tables follow migration 0007: task_executions, task_submissions and
task_review_decisions. Existing tasks and planning history are not rewritten.
Executions retain current reported progress/blocker, actual start and approved
completion time. Submissions retain the exact assignment, submitter, task version,
summary, submitted time, instructions/criteria and work/schedule snapshot. Closing
sets closure metadata once; it does not rewrite the submitted content. Decisions
retain actor, outcome, feedback, self-approval, fallback record, decision time and
task/project versions. TaskChange retains immutable work-update audit and request
identity alongside the existing planning audit.

Submission time and approval time remain separate. completed_at is the approved
lifecycle completion time, not a claim that all work finished at that moment.
If that approval follows the planned finish, the schedule forecast stays explicitly
unassessed rather than presenting a past planned date as a certain delivery outcome.
Dates are not silently moved and no team fault or project delivered-late outcome is
inferred. Actual-aware extension/delivery assessment remains subsequent work.

Only current assignees and authorized supervisors receive private execution,
submission, feedback and snapshot details. Peers retain the existing general task
summaries; their review response cannot reveal another assignee's private rows.
Former assignees lose access after reassignment. Contributor histories are filtered
to their own submissions/updates; supervisor history remains scoped to the project.
Planning/reassignment history excludes execution events so it does not mislabel an
execution snapshot as a missing task. The review screen separately shows work
updates and submissions/decisions. Latest 25 tasks per page and latest 25 updates/
submissions per task are bounded; older history remains stored. Eligibility and
history lookups are batched. Display times use the project's pinned timezone.

## Concurrency and operational boundaries

Mutations require current active authority after company transaction fencing,
current membership/assignment eligibility, expected task/project versions and an
explicit confirmation. A review binds an exact open submission and its original
assignment/version. Each submission has at most one decision and each task at most
one open submission. Exact actor/payload-bound request replay produces no duplicate
update, submission or decision; changed payloads conflict. Current authorization
is still rechecked before a replay receipt is returned. Late/stale commands cannot
reopen completed work or overwrite another review. Execution/decision changes
advance the delivery generation so old S10 assessments cannot silently remain fresh.

Private endpoints independently require verified JWT identity and trusted service
credentials. GraphQL is the public business API. The web BFF uses the configured
exact application origin, server-side sessions and controlled error messages.
Tokens and credentials are not returned to browser JavaScript or diagnostics.

Migration 0008_completion_reviews is additive and refuses downgrade when any of its
three tables contains evidence. Runtime application requires separate owner approval.
Only project-work, gateway and web need rebuilding; no new service/database/volume,
real email or intentional outage is required. Tests journal disposable identity
ownership, verify project/actor/assignment/request/fallback references before
removal, reject foreign references, remove decisions before their parents, verify
zero owned review rows and preserve real company records and the primary ADMIN.
