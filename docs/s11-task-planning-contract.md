# S11 contextual leader workspace and task breakdown

The original development document is unchanged. This stage implements its leader
workspace and task breakdown; scheduling/dependencies, execution, review and
extension workflows remain in their later stages.

## Authority and privacy

A current active EMPLOYEE with the active LEADER appointment in the exact project
may create, edit and reassign pending tasks. Leadership is contextual, never a
second company role or another login. The current owner and ADMIN may oversee
private task detail and retained planning history, but their roles alone do not
make them task planners or allow employee impersonation. S10 absence/fallback does
not grant task-planning rights. Contributors cannot enumerate assignment choices.

Only active EMPLOYEE accounts with active employee profiles and current project
membership are eligible assignees. The leader may assign themselves. Manager/HR
accounts, inactive identities, directory-only records and nonmembers are excluded.
Project-work authorizes the exact project before asking people for a bounded batch
of exact account references. People returns only identifier, display name, active
eligibility and company role; there is no public employee-directory endpoint.

A project member may see task reference, title, assignee display name and general
status. Private instructions, acceptance criteria, assignment times and detailed
planning history are not projected to peers. The current assignee receives their
task details, but no other person's assignment history. Authorized supervisors
receive retained change history. Former assignees immediately revert to the peer
projection after reassignment; removed members lose project access. No private
filter/search/date/count operation is exposed.

## Task and assignment persistence

Project-work owns three additive tables: work_tasks, task_assignments and
task_changes, in its existing private database. Every new task requires a title,
instructions, acceptance criteria and one eligible assignee. Initial status is
PENDING; S11 offers no progress, completion, approval or scheduling controls.
Cancellation is representable in the status constraint, but no cancellation or
reopening action is introduced without the later authorized workflow.

A partial unique index enforces at most one active assignment per task in both
PostgreSQL and SQLite. Reassignment closes the previous assignment and appends
its replacement. It never deletes the previous owner. Every change requires a
reason, explicit confirmation and actor-bound idempotency key; snapshots retain
before/after instructions and assignment references. The most recent 50 changes
are displayed; older history remains stored. Task lists and member choices have
bounded pagination and no private-field filters.

S11 edit/reassignment is limited to PENDING tasks. Changing work after execution
starts needs the later lifecycle/handover contract and is rejected here; completed
or cancelled work cannot be silently reopened. A later account deactivation or
membership removal does not erase a historical assignment. It denies that
identity access; an authorized current leader can reassign pending work to an
eligible member. Employment offboarding/handover is completed in its later stage.

## Transactions and stale requests

All task writes use the existing company transaction fence, reread current people
and project leadership, and verify both project and task versions. Member changes
share that fence. Eligibility is checked with current people data inside the
write boundary; no browser company-role/assignee claim is trusted. Reusing the
same request and payload returns its original receipt without a duplicate effect;
a changed payload is rejected. Revocation is checked before replay.

Planning writes advance the delivery schedule version and project version, making
previous assessments stale. They do not fabricate a new forecast, rewrite the
original project commitment, revise an approved deadline, or claim that work was
delivered. Future scheduling uses the existing delivery producer contracts.

## Routes and verification scope

The shared project task view is available at /projects/{id}/tasks, with owner/admin
oversight at /manager/projects/{id}/tasks and /admin/projects/{id}/tasks. The web
POST bridge enforces exact origin and server-side session checks. Gateway exposes
typed GraphQL; private project-work and people endpoints independently validate
service and identity credentials and current authority. Browser code receives no
bearer token or service key.

Source tests cover contextual planning, peer privacy, reassignment, stale/repeat
requests, eligibility, database uniqueness, preserved S10 migration data and guarded
cleanup. Approved runtime checks will additionally exercise PostgreSQL races and
four browser cases on desktop/tablet/mobile, one worker, zero retries, retaining
the existing timeout. They use marked disposable projects/accounts and preserve
the primary administrator, real data, Gmail settings and legacy services.
