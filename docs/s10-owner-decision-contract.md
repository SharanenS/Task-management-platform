# S10 owner decisions and oversight contract

## Confirmed owner choices — 23 November 2026

The current project owner or ADMIN may record a leader absence with a reason,
explicit start/end instants and scope: reviews, within-deadline extension
assessment, or both. Fallback recipients are only the current project owner and
ADMIN; no substitute employee or global role is granted. Signing out does not
create an absence. A leadership vacancy also requires an explicit bounded record;
appointing a leader invalidates the old vacancy record. A recorded leader's
replacement/removal invalidates that leader's absence record.

An extension request remains pending until assessment and decision are finished,
not until task completion. S10 stores the owner escalation/decision contract;
actual extension request/task persistence is introduced by its later stage and
must use the same transaction. Recording a decision never implies a task has
completed or that its normal progress reporting should stop.

These choices are recorded here; the original development document is unchanged.

## Ownership and transport

Project-work owns the six new tables: delivery state, immutable assessments,
owner escalations, deadline-decision previews, immutable decisions and scoped
review fallbacks. It uses the existing private database. People remains the
account/profile/company-role authority. Gateway exposes typed GraphQL operations;
private project-work endpoints independently check the service credential, bearer
identity and current people authority. Current MANAGER ownership or ADMIN is
required. Being a project contributor or team leader does not grant owner access.
Unrelated manager, HR, inactive and cross-issuer access stays denied.

No new service, queue, email delivery, public port or external integration is added.

## Original commitment, current approval and forecast

The existing Project.approved_deadline/deadline_date/deadline_local and calendar
reference retain the original commitment for compatibility. They are not rewritten
by S10. The latest REVISE_DEADLINE decision determines current approval. The new
ownerOversight API labels the original commitment, current approval, current
forecast and actual delivery separately. Existing project list/detail labels now
explicitly describe the original commitment.

Forecasts come only from the future planning producer contract. Missing input is
UNASSESSED with a null forecast, never zero impact or a copied deadline. Outdated
schedule/project versions or expired assessment validity make the current forecast
unavailable and clearly stale. An older escalation forecast is labelled as a last
assessment, not presented as current. Actual delivery remains unavailable until
its real producing workflow exists; S10 never labels a forecast as delivered late.

## Trusted producer boundary

There is no public assessment or escalation creation operation. delivery_inputs
provides transaction-scoped contracts for the future planning/extension domain.
It advances a monotonic schedule version, records a matching immutable assessment
and opens or refreshes a source-request-bound escalation. These contracts require
an explicit transaction and reject unflushed pending state instead of discarding
another business mutation. Future callers must acquire the shared domain fence
before applying task changes and keep the full operation in one transaction.

Assessment validity is ten minutes and also requires exact project/schedule
versions. Escalation refresh increments its version. Invalid/unknown impact cannot
authorize an approval. S10 acceptance fixtures seed only marked owned projects;
production never fabricates task inputs merely to populate the inbox.

## Owner decisions

The three outcomes are REVISE_DEADLINE, ACCEPT_FORECAST_LATE and REQUEST_REPLAN.
All require explicit confirmation, a reason and recorded affected-team context.
Team context is an explicit recorded statement, not automatic blame attribution
or an invented team-membership model.

Revision and late-forecast acceptance require a fresh assessed forecast beyond the
current approved project deadline. A request for a revised plan is also possible
when assessment is unknown/stale; that does not approve unknown impact. Revision
requires an actor-bound preview showing original/current/forecast/proposed dates
and the calendar version. The date must be a working day at or after the forecast,
using the pinned timezone rules. The preview's validity cannot exceed assessment
validity. A changed calendar, actor, request or project invalidates it. A calendar
edit does not silently rewrite task schedules.

Company transaction locks, post-lock ownership reload, expected versions, unique
request identifiers and payload hashes reject stale/conflicting approvals and
make exact replay idempotent. A future extension producer can use
OwnerDecisionService.decide_in_transaction before its own mutation so task and
owner decision commit together. The current actor is recorded, never impersonated.
The owner escalation becomes DECIDED once the decision is recorded; later task
completion is separate.

History retains actor identity/name/role, outcome, reason, team context, forecast
snapshot/state, previous/revised approvals and whether the previous commitment
was already overdue. Original overdue history remains visible after a revision.
No decision marks a task/project actually delivered.

## Absence and fallback

Absence records retain their creator, exact leader (or explicit vacancy), scope,
reason and UTC start/end. They may be revoked with a separate reason, actor, time
and replay-safe identifier. Revocation does not delete the original record.
A future review/extension handler must call require_in_transaction and retain its
returned record/actor/scope proof in the business audit. Both role and ownership
are rechecked at use. Within-deadline extension fallback additionally needs a fresh
assessment whose forecast does not exceed current approval; unknown/late impact
requires the owner deadline-decision path instead. These contracts do not authorize
progress impersonation, independent-review claims or leader self-approval shortcuts.
Those future handlers retain their own assignee, review and self-approval checks.

## Presentation and bounds

Owner/admin project pages link to Delivery oversight. Empty production inbox and
forecast states are intentional until real task planning produces inputs. No fake
task, deadline assessment, review completion or sample escalation is shown.
Histories/inbox use pages of 25 records, with a common next/previous page control.
Reasons/summaries are bounded to 2,000 characters and team context to 300. Absence
windows are explicit and finite; no automatic logout/absence/reminder inference
is made. Automatic reminder thresholds and S11 task features are not introduced.
