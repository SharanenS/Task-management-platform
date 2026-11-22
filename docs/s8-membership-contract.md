# S8 project membership contract

Owner decision: 21 November 2026. This supplements the unchanged original product
plan. Appointments are limited to accounts with the EMPLOYEE company role and an
active linked employee record. HR accounts cannot receive appointments. Managers
remain project creators/owners, not normal contributor assignees.

## Authority and context

Only the current project owner (ADMIN or MANAGER) or a current ADMIN can appoint,
change or remove members. Project creation remains ADMIN/MANAGER only. A member,
including a team leader, cannot grant membership, enumerate candidate employees
or change company authorization roles. Historical creation grants no permanent
management authority after ownership changes. Ownership transfer is not added here.

Appointments are project-specific CONTRIBUTOR or LEADER responsibilities, never
a global TEAM_LEADER role or second account. One active leader is supported per
project. Removing or demoting the current leader precedes appointment of another.
The same EMPLOYEE account may lead one project and contribute to another.

Current account/profile/role authority is rechecked through people. Membership is
read from project-work on each permission-sensitive request, without an access
cache. Revocation removes subsequent project access; an EMPLOYEE with another
appointment keeps only that other project's scope. An inactive account/profile
or a change to an ineligible company role cannot exercise an old appointment.
Already-running reads can complete at their transaction snapshot; this is not a
distributed atomic transaction across people and project-work.

## Data and privacy

Project-work owns project_members and project_membership_changes. Accounts and
employee records remain solely in people; project rows hold account references
and an appointment-time display-name snapshot. The minimal internal candidate
contract contains account reference, display name, role and eligibility, with no
email address, credentials or unrelated HR fields. Public candidate lookup first
checks management authority for the exact project.

Authorized members see their project's roster and appointment titles. Detailed
responsibilities are visible only to the appointed person and project management;
peers receive null for those details and account references. Change history is
management-only. There is no task, progress, scheduling-detail or HR disclosure
introduced by this stage. ADMIN oversight is distinguished from actual ownership.

Member records are deactivated, not deleted, by normal application commands.
Changes retain actor, target, before/after state, timestamp and project version.
The UI shows the latest 50 changes; earlier records remain stored. The initial
bounded roster supports 100 distinct appointment records per project, including
removed appointments; an explicit error is returned at the limit. Candidate search
is paginated and restricted to currently eligible employees.

## Writes and history

Every command requires confirmation, a request UUID and the expected project
version. Shared company transaction locking serializes changes with project and
calendar operations. Version conflicts reject stale edits. A database partial
unique index independently permits only one active leader. Request fingerprints
allow safe replay without duplicate history and reject conflicting reuse.
Authority and target eligibility are rechecked within the write path.

Migration 0003_project_membership extends 0002_manager_projects. It adds two tables
and constraints without rewriting existing projects, deadlines, calendars or people
data. Downgrade refuses to discard appointments or their history. Original creator,
current owner and the original agreed deadline remain intact.

## Interface and stage boundary

ADMIN and owners open Project membership from project details. EMPLOYEE accounts
receive an Open assigned projects link after sign-in and use a shared contextual
workspace at /projects. Switching projects changes the displayed responsibility
without changing login or company role. This is not the later employee dashboard
or full leader task-planning workspace. Tasks, ownership transfer, coordination,
review workflows and S9 development are not included.
