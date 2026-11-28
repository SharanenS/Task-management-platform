# S12 working-day task scheduling and dependencies

This supplements the unchanged original development plan. Scheduling remains in
project-work; the gateway orchestrates verified identity calls and the web BFF
keeps tokens in server-side sessions. No new service or database is introduced.

## Approved rules and scope

The S6 whole-working-day rules remain authoritative: a working start counts as day
one, non-working requested starts roll forward, holidays/exceptions override the
weekly pattern, and dependency handoffs occur at the next working day's opening.
The project's immutable calendar version and timezone rules remain pinned. No
calendar or timezone is silently substituted. Original task commitments and the
original project deadline remain distinct from revisions and current forecasts.

The owner approved overlapping independent work on 27 November 2026. Scheduling
follows dependencies, not a resource-capacity solver. Overlapping windows assigned
to the same employee produce explicit project-scoped workload warnings. Other
projects' private schedules are not exposed through these warnings. Up to 100
overlap pairs are shown per network snapshot. Duration is a
window of working days, not an hourly effort estimate or a delivery guarantee.

## Authority and privacy

Only the current active EMPLOYEE appointed as this project's leader may preview
or save schedules. Owner and ADMIN can inspect private schedules and history but
do not acquire leader planning authority. Nonmembers and unrelated managers are
denied; current assignee and membership eligibility are rechecked. Contributors
receive only their own task schedules. Colleagues' dates, durations, readiness,
forecast, overlap pairs and schedule revision history are not projected to peers.
Reassignment immediately removes the former assignee's private schedule access.

The gateway and owning service independently verify the authenticated identity,
current people status and trusted service credential. The session BFF requires the
exact configured application origin for POSTs and never accepts an actor from the
browser. Invalid requests, missing credentials and unavailable private services
fail closed. Scheduling does not change company roles or appointment rules.

## Analysis, readiness and uncertainty

A bounded dependency DAG supports up to 250 project tasks, 250 prerequisite inputs
per task, and durations of 1–3660 whole working days. Duplicate, self, foreign
and cyclic dependencies are rejected. Each path calculates independently; a join
uses the latest prerequisite handoff, never the sum of unrelated extensions.
Missing schedule data, ineligible assignments, cancelled prerequisites or an
unfinished task past its scheduled finish keep the project forecast explicitly
unassessed/null. Historical dates are retained instead of being moved to now.
Unsupported calendar windows and ambiguous/nonexistent local boundaries are errors.
No duration is invented for existing tasks.

Readiness requires a known eligible plan, the effective start to have arrived,
and all prerequisites to be COMPLETED; AWAITING_REVIEW does not satisfy a gate.
The in-transaction start guard also rechecks current assignee/role, current
membership and task lifecycle. It is a contract for the later execution handler;
S12 introduces no Start, completion, approval or self-approval action. Date gates
and dependency readiness are separate from lifecycle states and blockers. An overdue
otherwise-ready pending task remains startable without shifting its original dates;
its incomplete overdue forecast remains unknown.

## Preview, revisions and concurrency

The leader edits one pending task's requested start, duration and prerequisites,
with a reason. An actor-bound ten-minute preview shows effects on all dependency
paths, unknown forecasts, deadline exceedance, calendar version and workload
warnings. Confirmation consumes the exact preview; it cannot approve a project
deadline change. Started/reviewed/completed tasks cannot be rescheduled indirectly
through an upstream pending task.

Company transaction fencing, post-lock authority reload and expected task/project
versions serialize changes. A preview binds the complete current task graph,
assignee eligibility, pinned calendar/configuration, schedule generation and
current approved project deadline. Stale authority, inputs, time cutoffs, expired
previews and already-used previews require a new preview. Exact request replay
is actor/payload bound; it creates no duplicate revision. Different concurrent
commits based on the same project version have one winner.

The four additive tables are task_schedules, task_dependencies,
task_schedule_previews and task_schedule_changes. The first confirmed task plan
stores an immutable original snapshot. Subsequent revisions retain before/after
network snapshots, reason, actor and schedule/project versions. Current dependent
windows update transactionally; no original commitment is overwritten. S10
assessment generation advances in the same transaction and its validity is capped
at the next unfinished task cutoff, including equality at that cutoff. Schedule writes do not automatically approve
an extension, open an escalation, or mark actual delivery.

## Interface and operations

Project details links to Task schedule in the leader/member workspace and
owner/admin portals. The timeline combines real date-window bars with textual
accessible dates, durations, uncertainty and readiness. The editor previews first
and requires explicit confirmation. Supervisors can inspect the latest 25 revision
records; older records remain in the owning database.

Migration 0007_task_scheduling follows 0006_task_breakdown. Existing task/account
rows are untouched and remain unscheduled until deliberately planned. A downgrade
refuses to remove any schedule, dependency, preview or revision evidence. Live
application requires separate approval; only project-work, gateway and web need
rebuilding. Scoped tests verify ownership before deleting disposable records,
including cross-project dependency references, and leave ordinary records intact.
