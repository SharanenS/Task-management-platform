# Stage R1 Specification: Role-Based Portals & Platform Refinement

**Document Status:** Working Specification & Architecture Baseline (Stage R1 Revision)  
**Target Baseline:** Branch `portal-r1-baseline` (commit `fc8fc6f`, `main` Phase 14 accepted)  
**Workflow & Staging Note:** Per approved process, the Stage R1 specification remains unstaged on `portal-r1-baseline` and will be bundled together with the first verified Stage R2 implementation in a single combined PR. Stages R3 through R15 retain individual stage verification and manual user Git gates.  
**Coexistence Principle:** Legacy interface retained until replacement acceptance; unified backend source of truth; zero authorization bypasses.

---

## 1. Executive Summary & Architecture Strategy

This specification defines the architecture, permission matrix, data contracts, and implementation roadmap for transitioning Taskspace from a single monolithic dashboard into five role-focused portals:

1. **Admin Portal:** Identity, account provisioning, application role assignments, company working calendar, project ownership administration, audit oversight, and approval fallback.
2. **Manager Portal:** Project creation, ownership, team leader appointments, delivery risk tracking, structured update requests, internal meeting coordination, and deadline escalation decisions.
3. **Team Leader Experience:** Project task breakdown, member assignment, dependency mapping, review queue, and extension evaluation within approved project buffers.
4. **Employee Portal:** Personal assigned tasks, progress updates, blocker reporting, review submissions, extension requests, and meeting/update responses.
5. **HR Portal:** Employee profile lifecycle, onboarding workflows, departmental transfers, reporting hierarchy maintenance, and offboarding coordination with Admin.

### Core Architecture Principles

* **Dual-Interface Coexistence:** Legacy routes (`/projects`, `/tasks`, `/employees`, `/workflows`, `/jobs`, `/reports`, `/operations`, `/system`) remain operational while portal routes (`/portals/...`) are constructed. Both interfaces share the same backend services, authentication mechanisms, and databases.
* **Unified Source of Truth:** Business rules, authorization policies, and state transitions reside strictly in backend domain services (`services/work`, `services/employee`, `services/workflow`, `services/job`, `services/notification`) and the GraphQL Gateway (`gateway`). Portals and legacy views never duplicate or compete for business logic.
* **Symmetric Authorization Enforcement:** All new permission checks, task privacy filters, and workflow constraints implemented on the backend apply universally to both new portal queries and legacy GraphQL entry points. Keeping the legacy interface accessible will never preserve an authorization bypass.
* **Non-Destructive Transition:** No legacy code, database columns, or endpoints will be deleted until all portals achieve verified acceptance, pass regression testing, and have an approved rollback strategy (Stage R15).

---

## 2. Verified Current System Audit & Requirements Matrix

This audit evaluates the codebase at commit `fc8fc6f`. Every claim is categorized with explicit audit evidence:

* **Observed in source/configuration:** Verified through direct static inspection of code, configuration, or migration files.
* **Relevant automated tests located:** Existing automated test suites covering the capability have been identified in the repository.
* **Tests executed during R1:** Explicitly recorded as none (R1 is an audit-only stage; no test suites were executed).
* **Runtime behaviour unverified in R1:** Runtime execution, live network flows, and Docker daemon interactions were not exercised during R1.
* **Not found within identified search scope:** Verified absent from the relevant codebase after structured searches.

| Platform Capability / Domain | Current Implementation & Evidence | Audit Status | Required Target State |
| :--- | :--- | :--- | :--- |
| **Authentication & OIDC** | • Gateway token validation: `gateway/app/auth.py` (lines 19–53).<br>• Frontend session & PKCE handling: `frontend/src/auth/session.ts` (lines 18–96).<br>• Keycloak realm configuration: `infrastructure/keycloak/taskspace-realm.json` (lines 1–60).<br>• Automated tests located: `frontend/tests/e2e/authentication.spec.ts`, `frontend/tests/auth.test.ts`, `gateway/tests/test_auth.py`. | **Observed in source/config; automated tests located; runtime unverified in R1** | Reuse existing infrastructure as-is. Public registration remains disabled (`registrationAllowed: false`). Password reset flow enabled. Session cookies and token refresh retained. |
| **Admin Provisioning & Passwords** | • Temporary password creation: `services/employee/app/keycloak_admin.py` (lines 83–120, sets `"temporary": True`).<br>• Runtime startup: `services/employee/app/bootstrap.py` (lines 1–33, syncs metadata to PostgreSQL, does not overwrite Keycloak passwords).<br>• Dev bootstrap script: `scripts/bootstrap-development.ps1` (lines 151–162, runs `kcadm.sh set-password`, overwriting credentials on invocation). | **Observed in source/config; runtime unverified in R1** | Clarify password behavior: ordinary application startup does not alter existing passwords, whereas explicit development bootstrap resets them. Maintain requirement that application startup must never reset or overwrite existing credentials. |
| **Company Roles** | • `ApplicationRole`: `ADMIN`, `MANAGER`, `MEMBER` in `services/employee/app/models.py` (lines 11–14), `gateway/app/schema.py` (lines 153–156), and `infrastructure/keycloak/taskspace-realm.json` (line 13).<br>• Role `HR` is absent from all schemas and realm roles. | **Observed in source/config; automated tests located (`employee-administration.spec.ts`)** | Add company role `HR`. For `MEMBER`, analyze compatibility: evaluate whether to rename to `EMPLOYEE` across Keycloak/DB/API or preserve the internal enum value `MEMBER` with an "Employee" user-facing label to avoid breaking existing contracts. |
| **Project Roles & Responsibilities** | • `ProjectRole`: `PROJECT_MANAGER`, `CONTRIBUTOR` in `services/work/app/models.py` (lines 27–29) and `gateway/app/schema.py` (lines 173–176).<br>• `TEAM_LEADER` role is absent.<br>• Project ownership is tracked only via immutable `creator_employee_id` in `services/work/app/models.py` (line 65). | **Observed in source/config; automated tests located (`project-management.spec.ts`)** | Add project role `TEAM_LEADER`. Add explicit mutable `owner_employee_id` on Project. Add `RESTRICTED_VIEWER` where required. Team leadership is project-scoped, not global. |
| **Project Creation Permissions** | • Public Gateway mutation `createProject` explicitly checks `if actor.role not in {"ADMIN", "MANAGER"}: raise GraphQLError(..., code="FORBIDDEN")` (`gateway/app/schema.py`, lines 2124–2127).<br>• Internal Work Service independently enforces `if actor.application_role not in {"ADMIN", "MANAGER"}: raise WorkError("FORBIDDEN", 403)` (`services/work/app/service.py`, lines 186–187).<br>• Unit test verified in `services/work/tests/test_work.py` (line 62, `test_member_cannot_create`). E2E coverage located in `frontend/tests/e2e/project-multi-role.spec.ts`. | **Implemented and Verified** | Retain existing defense-in-depth model as-is: both the public Gateway and the internal Work Service already strictly restrict project creation to `ADMIN` and `MANAGER`. Base employees (`MEMBER`) cannot create projects through the UI or API. |
| **Task Creation Permissions** | • Any project member (including `CONTRIBUTOR`) can create tasks in `services/work/app/service.py` (lines 450–454). | **Observed in source/config; automated tests located** | Restrict task creation to Project Owner, Team Leader, or Admin. Contributors cannot create project tasks. |
| **Task Lifecycle States** | • `TaskStatus`: `TODO`, `IN_PROGRESS`, `BLOCKED`, `DONE`, `CANCELLED` in `services/work/app/models.py` (lines 32–37).<br>• Direct jump from `IN_PROGRESS` to `DONE` allowed in `services/work/app/service.py` (line 588). | **Observed in source/config; automated tests located (`task-management.spec.ts`)** | Adopt primary lifecycle: `PENDING` &rarr; `IN_PROGRESS` &rarr; `AWAITING_REVIEW` &rarr; `COMPLETED`. Treat blocked as an interruption condition, overdue as a dynamic calculation, and dependency readiness as a separate entry gate. |
| **Task Review & Approvals** | • Review queue and review records are absent from `services/work/app/models.py`. | **Not found within identified search scope** | Implement completion review submission (`AWAITING_REVIEW`), Team Leader review queue, return-for-changes with feedback, and explicit self-approval audit logging for leaders. |
| **Colleague Task Privacy** | • `_task_value` returns description, due dates, comments, and activities to any project member in `gateway/app/schema.py` (lines 750–772) and `services/work/app/service.py` (lines 433–436). | **Observed in source/config; automated tests located** | Restrict colleague visibility: co-members see Title, Assignee Display Name, Reference, and General Status. Detailed progress, dates, durations, deadlines, extension reasons, and review notes are restricted to Assignee, Leader, Owner, and Admin. The HR role alone receives zero task detail. |
| **Task Durations & Dependencies** | • Tasks store only calendar `due_date: Date` in `services/work/app/models.py` (line 119).<br>• Working-day duration and task dependency tables are absent. | **Not found within identified search scope** | Add working-day duration (`duration_working_days: Integer | None`). Add task dependency graph table supporting DAG validation and prerequisite completion gating. |
| **Company Working Calendar** | • Calendar configuration, timezone, working hours, and holiday models are absent from all services and databases. | **Not found within identified search scope** | Implement company working calendar: working weekdays, configurable hours (including weekday variations), company timezone, and effective-dated calendar exceptions/holidays. |
| **Extension Request Workflow** | • Extension request entities and evaluation workflows are absent from `services/work`. Due dates are edited directly by managers. | **Not found within identified search scope** | Implement extension workflow: assignee requests additional working days + reason; original schedule remains valid; leader approves if within deadline; escalates to owner/admin if forecast exceeds deadline. Accommodate unassessed/unknown impact states. |
| **Manager Coordination & Meetings** | • Structured update forms and internal check-in meeting requests are absent from `services/work`. | **Not found within identified search scope** | Implement structured update requests and internal check-in meeting records with participant acknowledgement tracking. |
| **HR & Employee Profiles** | • `Employee` model in `services/employee/app/models.py` (lines 22–45) has only `username`, `email`, `display_name`, `role`, `active`.<br>• Reporting lines (`reports_to_employee_id`), department, and employment lifecycle states are absent. | **Observed in source/config; automated tests located (`employee-administration.spec.ts`)** | Extend profile model with department, job title, reporting hierarchy, and onboarding/offboarding workflow tracking. HR role manages employment records but cannot grant application authorization roles. |
| **Event & Notification Pipeline** | • RabbitMQ outbox & notification service handles `TASK_ASSIGNED`, `REPORT_SUCCEEDED`, `REPORT_FAILED` in `services/notification/app/models.py` (lines 11–15). | **Observed in source/config; automated tests located** | Add notification templates and events for task reviews, extension requests/decisions, update requests, and meeting check-ins. |
| **Frontend Portal Architecture** | • Monolithic layout with conditional navigation in `frontend/src/components/layout/app-shell.tsx` (lines 106–108). | **Observed in source/config; automated tests located (`dashboard-acceptance.spec.ts`)** | Construct dedicated portal views (`/portals/admin`, `/portals/manager`, `/portals/employee`, `/portals/hr`) sharing reusable UI primitives while preserving legacy routes. |
| **Shared Visual Foundation (Stage R2)** | • Tokens: `frontend/src/components/portal-ui/portal-tokens.ts`.<br>• Theming: `frontend/src/app/globals.css` (`.portal-theme`).<br>• Primitives: cards, buttons, badges, inputs, selects, tables, typography in `frontend/src/components/portal-ui/`.<br>• SVG Charts: `task-status-chart.tsx`, `completion-trend-chart.tsx`.<br>• Preview page: `/design-system` (`frontend/src/features/design-system/portal-preview.tsx`).<br>• Verification: 17 unit tests in `frontend/tests/portal-ui.test.tsx`, production build, typecheck, lint, Prettier all passed. | **Implemented & Verified (Stage R2)** | Reusable visual foundation ready for Stage R3 portal shell and subsequent portal pages without altering legacy styles or violating existing assertions. |

---

## 3. Account Administration, Authorization, and HR Scope

### 3.1 Strict Separation of Authorization Roles and Employment Attributes

The platform maintains a strict boundary between **Application Authorization Roles** (which govern technical system permissions in Keycloak, Gateway, and services) and **Employment Attributes** (which represent corporate HR data).

```
+---------------------------------------------------------------------------------------+
| APPLICATION AUTHORIZATION ROLES (Managed strictly by ADMIN)                            |
| Controls access tokens, API permissions, and service boundary guards                  |
|                                                                                       |
|   +----------------+      +----------------+      +--------+      +---------------+   |
|   |     ADMIN      |      |    MANAGER     |      |   HR   |      |    MEMBER     |   |
|   |                |      |                |      |        |      |  (EMPLOYEE)   |   |
|   +----------------+      +----------------+      +--------+      +---------------+   |
+---------------------------------------------------------------------------------------+
                                           |
                                  Independent Layers
                                           v
+---------------------------------------------------------------------------------------+
| EMPLOYMENT & PROFILE DATA (Maintained by HR, overseen by Admin)                        |
| Corporate metadata, organizational structure, and lifecycle status                     |
|                                                                                       |
|   • Department (e.g., Engineering, Operations, Human Resources)                       |
|   • Job Title (e.g., Senior Systems Analyst, Lead Designer)                           |
|   • Reporting Relationship (reports_to_employee_id -> Manager or Director)             |
|   • Employment Lifecycle Status (ONBOARDING, ACTIVE, TRANSFERRED, OFFBOARDING)        |
+---------------------------------------------------------------------------------------+
```

#### Authority Boundaries:
1. **Admin Authority:**
   * Sole authority to create, activate, deactivate, and reconcile application user accounts in Keycloak and Employee Service.
   * Sole authority to assign or alter application authorization roles (`ADMIN`, `MANAGER`, `HR`, `MEMBER`).
   * HR cannot grant application privileges, change user roles, or promote users merely through its HR role.
2. **HR Authority:**
   * Manages authorized employee profiles, job titles, departments, work locations, and reporting relationships.
   * Manages onboarding workflows (gathering profile data, initiating provisioning requests to Admin).
   * Manages departmental transfers (updating department and reporting manager).
   * Manages offboarding workflows (initiating exit checklists, submitting deactivation requests to Admin).
3. **Role Composition (Existing Storage vs. Policy Choice):**
   * *Existing Storage Model:* The current database column `employees.role` is a single enum value (`ApplicationRole`). Each account currently holds exactly one application role.
   * *Company Role Composition Policy Decision (Unresolved):* Whether the production account model strictly permits only one company role per identity, or whether future multi-role composite grants (e.g., an identity holding both HR and Manager roles) should be supported, is recorded as an open architectural choice. The initial implementation preserves the existing single-role storage model.

---

## 4. Manager Assignment Policy and Project Responsibilities

### 4.1 Manager Role Scope

In accordance with the agreed baseline:
* **Managers are not normal task assignees.**
* The Manager role focuses on project creation, ownership, team leader appointment, delivery risk tracking, structured update requests, internal meeting coordination, and deadline escalation decisions.
* **No Contributor Exception:** The specification does not introduce an exception allowing managers to be selected as normal task assignees via contributor membership. Managers oversee and coordinate projects; tasks are assigned to team members and team leaders.

### 4.2 Project-Specific Responsibilities

Project responsibilities represent contextual assignments within a project (`services/work`), distinct from company roles:

1. **Project Owner:**
   * Initially assigned to the project creator (Admin or Manager).
   * Controls project settings, team appointments, membership, and approved deadlines.
   * Resolves escalated extension requests and deadline decisions.
   * Fallback reviewer when a team leader is unavailable.
2. **Team Leader:**
   * Appointed by the Project Owner or Admin for a specific project.
   * Breaks project work into tasks, sets planned durations, and maps dependencies.
   * Assigns tasks to team members (and to themselves).
   * Reviews task completion submissions.
   * Approves extension requests that remain within the approved project buffer.
   * *Dual Role on Projects:* A single user account can lead Project A (acting as Team Leader) while contributing as a regular assignee on Project B. Team leadership is strictly project-scoped.
3. **Contributor:**
   * Project member assigned to execute tasks.
   * Updates their own task status, reports blockers, requests extensions, and submits work for review.
4. **Restricted Viewer (Optional Project Scope):**
   * Member with read-only visibility into general task titles and statuses, without editing or assignment capabilities.

### 4.3 HR Project Access Policy

* **Baseline Rule:** The `HR` company role alone grants **zero** project or task authority. An HR user cannot view, create, edit, or administer projects or tasks merely by holding the HR role.
* **Broader Participation Policy (Unresolved):** Whether an individual who holds an HR company role may also be added as a contributor to an internal administrative project via standard project membership is recorded as an unresolved policy decision. The security boundary ensures that if such membership is ever permitted, access is granted strictly through explicit project membership records, never through the HR role itself.

---

## 5. Comprehensive Permission Matrix

| Capability / Action | Admin | Project Owner | Manager (Non-Owner) | Team Leader | Contributor | Employee (Non-Member) | HR Role Alone |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Manage Accounts & App Roles** | Yes | No | No | No | No | No | Coordinate Only |
| **Configure Company Calendar** | Yes | No | No | No | No | No | No |
| **Maintain Employment Profiles & Org Lines**| Yes | View Dept | No | No | No | No | Yes |
| **Create New Project** | Yes | Yes | Yes | No | No | No | No |
| **Appoint / Replace Team Leader** | Yes | Yes | No | No | No | No | No |
| **Manage Project Memberships** | Yes | Yes | No | No | No | No | No |
| **Break Down Tasks & Set Dependencies** | Yes | Yes | No | Yes | No | No | No |
| **Assign Tasks to Members** | Yes | Yes | No | Yes | No | No | No |
| **Update Own Task Status (Progress/Blocker)**| No* | No* | No | Yes (Self Only)| Yes (Self Only)| No | No |
| **Submit Own Task for Review** | Yes (Self) | Yes (Self) | No | Yes (Self) | Yes (Self) | No | No |
| **Review & Approve Task Completion** | Fallback | Fallback | No | Yes | No | No | No |
| **Explicit Leader Self-Approval** | Audit Flag | Audit Flag | No | Yes (Explicit) | No | No | No |
| **Request Task Extension** | N/A | N/A | N/A | Yes (Self) | Yes (Self) | No | No |
| **Approve Extension (Within Buffer)** | Fallback | Yes | No | Yes | No | No | No |
| **Decide Extension (Exceeds Deadline)**| Fallback | Yes | No | Escalate | No | No | No |
| **Issue Structured Update Request** | Yes | Yes | No | No | No | No | No |
| **Schedule Internal Check-in Meeting**| Yes | Yes | No | No | No | No | No |
| **View Colleague Task Title & Status** | Yes | Yes | No | Yes | Yes | No | No |
| **View Colleague Task Detail/Notes/Dates**| Yes | Yes | No | Yes | **NO (Privacy)**| No | **NO (Privacy)**|

*\*Note: Normal task progress and blocker reporting belong exclusively to the current assignee. Team leaders, owners, and admins cannot report progress on another employee's task. Review decisions are separate operations. Any exceptional administrative override or intervention requires an explicitly proposed policy and dedicated audit log.*

---

## 6. Task Lifecycle, State Transitions, and Privacy

### 6.1 Formal Task Lifecycle

The primary lifecycle consists strictly of four states:

$$\text{PENDING} \longrightarrow \text{IN\_PROGRESS} \longrightarrow \text{AWAITING\_REVIEW} \longrightarrow \text{COMPLETED}$$

```
                +----------------------------------------------------+
                |                                                    |
                v                                                    |
         +-------------+      Start Work      +---------------+      |
         |   PENDING   | -------------------> |  IN_PROGRESS  |      |
         +-------------+                      +---------------+      |
                                                |           ^        |
                                                | Submit    | Return |
                                                v           |        |
                                              +---------------+      |
                                              |   AWAITING    |------+
                                              |    REVIEW     |
                                              +---------------+
                                                |
                                                | Leader/Owner Approves
                                                v
                                              +---------------+
                                              |   COMPLETED   |
                                              +---------------+
```

#### Lifecycle Rules & Orthogonal Conditions:
1. **`PENDING`:** The task is scheduled and ready to begin once prerequisites are met.
2. **`IN_PROGRESS`:** The assignee has actively commenced work.
3. **`AWAITING_REVIEW`:** The assignee has finished work and submitted it for review. The task enters the Team Leader review queue.
4. **`COMPLETED`:** The reviewer has accepted the delivery. This is the normal terminal state.
5. **Return for Changes:** When a reviewer rejects a submission, the task transitions from `AWAITING_REVIEW` back to `IN_PROGRESS` with mandatory reviewer feedback notes.
6. **No Automatic Reopening:** Tasks do not automatically transition from `COMPLETED` back to `PENDING` or `IN_PROGRESS`. Any administrative reopening of a completed task is treated as an exceptional proposed action requiring explicit authorization and audit recording.
7. **Prerequisite Dependency Gating (Separate Gate):** Prerequisite dependencies must all be `COMPLETED` before a task can transition from `PENDING` to `IN_PROGRESS`. Planned dependency calculations determine schedule forecasts, while actual completion gating controls state transitions.
8. **Blocked Condition (Orthogonal Interruption):** Any task in `IN_PROGRESS` can set `is_blocked = True` along with a mandatory `blocker_reason`. Clearing the blocker restores `is_blocked = False` without modifying lifecycle state.
9. **Overdue Condition (Dynamic Scheduling Calculation):** A task is dynamically evaluated as overdue if `planned_end_date < current_working_date` while `status != COMPLETED`. Overdue is not a stored status; overdue tasks remain open until completed, and late completion history is preserved.

### 6.2 Data Migration and Legacy Contract Compatibility

Existing database records hold statuses: `TODO`, `IN_PROGRESS`, `BLOCKED`, `DONE`, `CANCELLED`. To preserve data integrity without data loss:

1. **Mapping Existing Statuses:**
   * Legacy `TODO` &rarr; Maps to `PENDING`.
   * Legacy `IN_PROGRESS` &rarr; Maps to `IN_PROGRESS` (`is_blocked = False`).
   * Legacy `BLOCKED` &rarr; Maps to `IN_PROGRESS` (`is_blocked = True`, preserving existing blocker text and activity history).
   * Legacy `DONE` &rarr; Maps to `COMPLETED` with an explicit migration marker (`is_legacy_completion = True`). Historical completed tasks will **not** fabricate review records or be forced through fresh approvals.
   * Legacy `CANCELLED` &rarr; Preserved as an administrative terminal status (`CANCELLED`) or substatus, retaining cancellation reasons and audit trails. Cancellation is not discarded.
2. **`MEMBER` Identifier Analysis:**
   * In the existing system, `MEMBER` is deeply embedded in PostgreSQL enum types, Keycloak realm role names, JWT token claims, and generated GraphQL client types.
   * *Proposed Compatibility Strategy:* Rather than forcing a high-risk schema and realm rename from `MEMBER` to `EMPLOYEE`, the system will preserve `MEMBER` as the internal technical identifier while presenting it as "Employee" in all user-facing copy, labels, and portal interfaces. If a full technical rename is later mandated, it will be executed under a dedicated migration with fallback aliasing.
3. **Duration Data on Legacy Records:**
   * Historical tasks lack working-day duration records. Legacy tasks will default to `duration_working_days = NULL` (unspecified duration) rather than fabricating an arbitrary one-day estimate.

### 6.3 Colleague Task Privacy Enforcement

To protect employee privacy, task fields are partitioned into colleague-visible vs. restricted tiers:

1. **Colleague-Visible Fields (Co-members on the same project):**
   * Task Reference (e.g., `PRJ-104`), Task Title, Assignee Display Name, General Status (`PENDING`, `IN_PROGRESS`, `AWAITING_REVIEW`, `COMPLETED`), and Blocked Flag (`is_blocked: bool`).
2. **Restricted Fields (Visible ONLY to Assignee, Project Team Leader, Project Owner, Admin):**
   * Detailed Description, Progress Notes, Comments, Planned Start/End Dates, Working-Day Duration, Blocker Detail Notes, Extension Requests, Justifications, Review Notes, and Audit History.
3. **Schema Compatibility & Defense-in-Depth:**
   * In `gateway/app/schema.py`, `Task.description` and `Task.due_date` are already nullable (`str | None`, `date | None`). For non-authorized co-members, these resolvers safely return `null`.
   * Non-null fields (such as `status` and `title`) remain populated with authorized general values.
   * Queries for task comments (`taskComments`) and activities (`taskActivities`) enforce permission checks at the resolver: returning empty connections or raising `FORBIDDEN` if invoked by non-authorized co-members.
   * Privacy boundaries are enforced across all access vectors: direct GraphQL queries, nested project relations (`Project.tasks`), search/filter operations, task counts/aggregates, background exports (`services/job`), reports, and notification messages.
   * Export jobs enforce the identical policy: CSV exports generated by regular members redact colleague-private detail columns.

---

## 7. Working Calendar, Scheduling, and Extension Engine

### 7.1 Company Working Calendar Model

The working calendar governs all schedule and duration calculations:

* **Configurable Working Days & Hours:** Standard working weekdays (e.g., Monday–Friday) with configurable working hours per weekday (supporting variations such as half-days on Fridays).
* **Company Timezone:** IANA timezone identifier (e.g., `America/New_York`, `UTC`) governing start/end of working day boundaries.
* **Holidays & Calendar Exceptions:** Explicit dates marked as non-working days or special working days.
* **Effective-Dated Calendar Versions:** Calendar modifications take effect on a specified `effective_from` date. Tasks preserve the calendar version ID or snapshot under which their schedule was committed. Changes never silently alter historical schedules.
* **Schedule Change Impact Preview:** Modifying the company calendar triggers an impact preview showing affected active projects. The administrator must explicitly confirm before revised working dates are applied to active schedules.
* **Duration vs. Effort:** Working-day duration represents an elapsed working schedule window, not an hourly effort estimate.

### 7.2 Proposed Scheduling Calculation Defaults

The following rules are established as baseline proposals:
1. **Inclusive Start Day (Proposal):** If a task starts on a working day during working hours, that day counts as day 1 of the duration.
2. **Sequential Handoff (Proposal):** A dependent task begins on the next working day following predecessor completion, unless same-day handoff is explicitly configured.
3. **Multiple Predecessors (Proposal):** When a task depends on multiple predecessors, its earliest allowable planned start date is:
   $$\text{Earliest Start} = \max_{p \in \text{Predecessors}}(\text{PlannedFinishDate}(p)) + 1\text{ working day}$$
4. **Whole-Day Scheduling (Proposal):** The initial engine schedules in whole working days. Partial-day task scheduling is deferred to future refinements.
5. **Dependency Cycle Prevention:** When a task dependency is created or updated, the engine validates the directed acyclic graph (DAG) and rejects any relationship that would introduce a cycle.

### 7.3 Extension Request Workflow & Unassessed Impact Representation

```
             +-----------------------------------------------------+
             | Assignee submits extension: requested working days  |
             | and justification.                                  |
             +-----------------------------------------------------+
                                       |
                                       v
             +-----------------------------------------------------+
             | Status: PENDING / IMPACT_ASSESSMENT_PENDING          |
             | • Original approved schedule remains effective.     |
             | • Assignee continues working & reporting progress.  |
             | • Forecast date is NULL until assessed.             |
             +-----------------------------------------------------+
                                       |
                                       v
             +-----------------------------------------------------+
             | Impact Assessment Engine Evaluates Schedule:        |
             | • Recalculates downstream dependency critical path. |
             | • Computes forecast project completion date.        |
             +-----------------------------------------------------+
                                       |
                     +-----------------+-----------------+
                     |                                   |
                     v                                   v
          [Forecast finishes within            [Forecast exceeds
           approved project buffer]             approved project deadline]
                     |                                   |
                     v                                   v
          +--------------------+               +--------------------+
          | Team Leader Review |               | Escalated to Owner |
          +--------------------+               +--------------------+
          | - Approve          |               | - Revise Deadline  |
          | - Reject           |               | - Accept Forecast  |
          +--------------------+               |   Late Delivery    |
                                               | - Reject & Re-plan |
                                               +--------------------+
```

#### Detailed Extension Principles:
1. **Representation of Unknown Impact:**
   * An extension request cannot require a mandatory forecast date or mandatory binary impact flag upon creation.
   * Model fields include an assessment status: `ASSESSMENT_PENDING`, `ASSESSED_WITHIN_DEADLINE`, `ASSESSED_EXCEEDS_DEADLINE`, or `ASSESSMENT_FAILED`.
   * While impact is unassessed, the request remains pending, follow-ups are routed to the Team Leader, and the original schedule remains legally effective.
2. **Work Continuity:** Assignees continue working and logging progress while an extension request is pending.
3. **Approval-Time Recalculation & Concurrency Protection:**
   * To prevent concurrent approvals from silently consuming the same project buffer, approvals employ optimistic locking (`version` on Project Schedule).
   * At the moment of approval, the engine recalculates the schedule against the latest committed state. If concurrent modifications altered the buffer, the transaction aborts with a version conflict, requiring the approver to review the refreshed forecast.
4. **Leader Self-Extension:** Team Leaders assigned to tasks can request extensions. Approval within buffer requires explicit self-approval confirmation and distinct audit recording.
5. **Owner Escalation Decisions:**
   * *Approve Revised Deadline:* Extends the approved project completion commitment.
   * *Accept Forecast Late Delivery:* Keeps the original deadline for contract tracking while authorizing delivery against the revised forecast.
   * *Reject with Replanning Request:* Declines the extension and requests that the leader adjust task scope or resources.
6. **"Delivered Late" Classification:** Work is labeled "delivered late" strictly after actual delivery occurs past the approved deadline—never prospectively while work is ongoing.
7. **"Pending until finished" Interpretation (Unresolved Ambiguity):**
   * *Status:* Genuine phrasing ambiguity in requirements.
   * *Recommended Default Interpretation:* **"Pending until impact calculation and approval decision are finished,"** not pending until the entire task reaches completion. The original schedule remains active during this pending window.
8. **Approver Absence & Delegation:**
   * Unavailability must be backed by an explicit, authorized delegation record with date boundaries (e.g., planned leave). A logged-out or offline session never implies absence.
   * When delegation is active, approval authority cascades to the designated delegate, Project Owner, or Admin fallback without misidentifying the actor in the audit record.

---

## 8. Manager Coordination & Internal Meetings

* **Structured Update Requests:** Project Owners/Managers can dispatch update requests to Team Leaders or Assignees. Specific forms capture progress summaries, blocker clarifications, and risk assessments. Tracked through states: `DISPATCHED`, `ACKNOWLEDGED`, `SUBMITTED`, `OVERDUE`.
* **Internal Check-In Requests:** Managers can request internal check-ins or cabin discussions with proposed working-day windows and participant lists. Participants acknowledge or propose alternatives. External telephony and external calendar integrations are excluded from scope.

---

## 9. Reuse, Adaptation, and Retirement Inventory

| Interface / Component Path | Current Purpose | Retained in Portals? | Strategy & Action Plan | Dependencies & Test Coverage |
| :--- | :--- | :--- | :--- | :--- |
| `frontend/src/components/layout/app-shell.tsx` | Monolithic shell with navigation sidebar | Yes (Legacy) | **Extract Shared Primitives; Retain for Legacy Routes.** Extract reusable header, user menu, and mobile nav into `@/components/layout/portal-shell`. Retain `app-shell.tsx` for legacy routes. | Tested in `foundation.spec.ts`. Must keep functional during coexistence. |
| `frontend/src/features/dashboard/workspace-dashboard.tsx` | Combined overview dashboard | Yes (Legacy) | **Replace in Portals; Retain for Legacy `/`.** Build role-specific portal dashboards (`/portals/admin`, etc.). Retain existing component for `/` legacy view. | Tested in `dashboard-acceptance.spec.ts`, `dashboard.test.tsx`. Tests will migrate to portals in R14. |
| `frontend/src/features/projects/project-directory.tsx` | Project directory and filters | Yes (Adapted) | **Adapt for Admin/Manager Portals.** Reuse project card and list primitives; scope queries to user's authorized projects. | Tested in `project-management.spec.ts`, `projects.test.tsx`. |
| `frontend/src/features/projects/create-project-form.tsx` | Project creation dialog | Yes (Reused) | **Reuse in Admin & Manager Portals.** Remove from regular employee navigation; enforce role check. | Tested in `project-management.spec.ts`. |
| `frontend/src/features/tasks/task-directory.tsx` | Global project task list | Yes (Adapted) | **Adapt for Employee ("My Tasks") & Team Leader.** Apply colleague privacy masking to task table. | Tested in `task-management.spec.ts`, `tasks.test.tsx`. |
| `frontend/src/features/tasks/task-detail.tsx` | Task detail, comments, history | Yes (Adapted) | **Adapt with Privacy Masking.** Hide private progress notes, dates, and discussions from unauthorized co-members. Add review & extension controls. | Tested in `task-management.spec.ts`. |
| `frontend/src/features/tasks/create-task-form.tsx` | Task creation form | Yes (Adapted) | **Adapt for Team Leaders & Owners.** Add working-day duration and dependency selectors. Restrict access to leaders/owners. | Tested in `task-management.spec.ts`. |
| `frontend/src/features/employees/employee-directory.tsx` | Admin employee management | Yes (Adapted) | **Adapt into HR Portal Directory.** Incorporate department, job title, reporting lines, and transfer actions. | Tested in `employee-administration.spec.ts`, `employees.test.tsx`. |
| `frontend/src/features/notifications/notification-center.tsx`| In-app notification center | Yes (Reused) | **Reuse as Shared Utility.** Connect to new review, extension, update, and meeting notification types. | Tested in `notification-report-lifecycle.spec.ts`. |
| `frontend/src/features/operations/operations-panel.tsx` | Metrics and alert monitoring | Yes (Admin) | **Reuse in Admin Portal.** Retain as operations tool for Admin. | Tested in `operations-acceptance.spec.ts`, `operations.test.tsx`. |
| `frontend/src/features/system/system-panel.tsx` | Gateway connectivity check | Yes (Legacy) | **Retain as Legacy Connectivity Utility.** Retain to preserve gateway heartbeat tests. | Tested in `foundation.spec.ts`, `system.test.tsx`. |
| `frontend/src/features/design-system/component-preview.tsx` | Component preview gallery | Yes (Test Anchor)| **Retain Route `/design-system` as Test Utility.** Do not expose in portal navigation, but preserve route to maintain test coverage. | Tested in `foundation.spec.ts`. |

---

## 10. Design-Level GraphQL & API Operation Inventory

This inventory outlines major GraphQL operations across domains at the design level (no implementation code is executed during R1).

| Domain / Capability | Owning Service | Operation Name & Type | Authorized Actors & Scope | Key Validation & State Rules | Audit & Event Output |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Account Role Assignment** | `services/employee` | `updateEmployeeRole` (Mutation) | `ADMIN` only | Cannot demote last remaining Admin; validates role enum. | Outbox event: `EMPLOYEE_ROLE_UPDATED` |
| **Employment Profile Update** | `services/employee` | `updateEmployeeProfile` (Mutation) | `ADMIN`, `HR` | Validates reporting hierarchy (prevents cyclical reporting relationships). | Outbox event: `EMPLOYEE_PROFILE_UPDATED` |
| **Company Calendar Update** | `services/work` | `updateCompanyCalendar` (Mutation) | `ADMIN` only | Effective-date validation; generates schedule impact preview. | Outbox event: `CALENDAR_CONFIG_UPDATED` |
| **Project Creation** | `services/work` | `createProject` (Mutation) | `ADMIN`, `MANAGER` | Creator becomes initial Owner; validates unique project key. | Outbox event: `PROJECT_CREATED` |
| **Team Leader Appointment** | `services/work` | `appointTeamLeader` (Mutation) | `ADMIN`, Project Owner | Target user must be an active project member. | Outbox event: `TEAM_LEADER_APPOINTED` |
| **Task Creation & Breakdown** | `services/work` | `createTask` (Mutation) | `ADMIN`, Owner, Team Leader | Project must be writable; validates working-day duration > 0. | Outbox event: `TASK_CREATED` |
| **Task Dependency Mapping** | `services/work` | `setTaskDependencies` (Mutation) | `ADMIN`, Owner, Team Leader | DAG cycle detection; validates all tasks belong to same project. | Outbox event: `TASK_DEPENDENCIES_UPDATED` |
| **Task Status Update** | `services/work` | `updateTaskStatus` (Mutation) | **Current Assignee only** | Normal progress updates (`PENDING` &rarr; `IN_PROGRESS`) and actual progress reporting belong exclusively to the assigned employee. Team Leaders, Owners, and Admins cannot report progress on another employee's task. Review decisions are handled separately via `reviewTaskCompletion`. Exceptional administrative overrides require an explicitly proposed administrative policy and dedicated audit trail. | Outbox event: `TASK_STATUS_CHANGED` |
| **Task Blocker Flagging** | `services/work` | `setTaskBlocked` (Mutation) | **Current Assignee only** | Blocker reporting reflects the assigned employee's operational reality. Mandatory `blocker_reason` when blocking; clears on unblock. Leaders and managers cannot report blockers on behalf of an employee without an explicit administrative override procedure. | Outbox event: `TASK_BLOCKER_CHANGED` |
| **Submit Task for Review** | `services/work` | `submitTaskForReview` (Mutation) | **Current Assignee only** | Task must be `IN_PROGRESS`; enters `AWAITING_REVIEW`. | Outbox event: `TASK_AWAITING_REVIEW` |
| **Review Task Completion** | `services/work` | `reviewTaskCompletion` (Mutation) | Team Leader, Owner, Admin Fallback | Approve &rarr; `COMPLETED`; Reject &rarr; `IN_PROGRESS` with feedback. Explicit self-approval flag recorded when leader reviews own task. | Outbox event: `TASK_REVIEW_DECIDED` |
| **Request Task Extension** | `services/work` | `requestTaskExtension` (Mutation) | **Current Assignee only** | Validates `additional_working_days > 0` and reason; creates pending request. | Outbox event: `EXTENSION_REQUESTED` |
| **Decide Task Extension** | `services/work` | `decideTaskExtension` (Mutation) | Team Leader (if within buffer), Owner/Admin (if exceeding) | Optimistic lock on schedule version; recalculates buffer at decision time. | Outbox event: `EXTENSION_DECIDED` |
| **Dispatch Update Request** | `services/work` | `requestProjectUpdate` (Mutation) | Project Owner, Admin | Form schema validation; dispatched to leader/assignee. | Outbox event: `UPDATE_REQUESTED` |
| **Schedule Internal Check-in**| `services/work` | `scheduleInternalMeeting` (Mutation)| Project Owner, Admin | Working-day window validation; tracks participant acknowledgements. | Outbox event: `MEETING_REQUESTED` |

---

## 11. Acceptance Scenarios (Given-When-Then)

### Scenario 1: Admin-Only Account and Permission Management
* **Given** a user "Alice" with the company role `HR` and a user "Bob" with company role `ADMIN`.
* **When** Alice attempts to invoke `updateEmployeeRole` to promote a user to `MANAGER`.
* **Then** the Gateway rejects the request with a `FORBIDDEN` error.
* **When** Bob invokes `updateEmployeeRole` with valid parameters.
* **Then** the role update succeeds and emits an audit event with Bob's actor ID.

### Scenario 2: First-Login Password Change and Startup Credential Immutability
* **Given** an account is provisioned via `KeycloakAdmin.create_disabled_user`.
* **Then** Keycloak stores credentials with `"temporary": True`.
* **When** the user logs in for the first time, Keycloak forces a password update before redirecting to the application.
* **When** the application restarts or service containers reboot, existing user passwords in Keycloak are preserved untouched.

### Scenario 3: Non-Member and Unauthorized-Manager Project Access Rejection
* **Given** Manager "Frank" owns Project Alpha, and Manager "Grace" owns Project Beta.
* **When** Grace attempts to view tasks or issue update requests on Project Alpha without explicit membership.
* **Then** the Work Service and Gateway reject the operation with a `FORBIDDEN` error.

### Scenario 4: One Active Assignee and Preserved Reassignment History
* **Given** Task `DEV-10` is assigned to Contributor "Dave".
* **When** Team Leader "Eve" reassigns `DEV-10` to Contributor "Dan".
* **Then** `DEV-10` has exactly one active assignee ("Dan").
* **And** a `TaskActivity` of type `ASSIGNMENT_CHANGED` records `from_employee_id: Dave` and `to_employee_id: Dan`.

### Scenario 5: Peer Task-Field Privacy Through Direct and Indirect Access
* **Given** "Alice" and "Bob" are contributors on Project Alpha.
* **And** Alice is assigned Task `DEV-01` with planned duration 4 days, due date 2026-12-05, and progress notes "Refactoring cache".
* **When** Bob queries `DEV-01` via direct GraphQL, nested project tasks, or a CSV export job.
* **Then** Bob sees reference `DEV-01`, title, assignee "Alice", and status `IN_PROGRESS`.
* **And** `durationWorkingDays`, `plannedStartDate`, `plannedEndDate`, `description`, and `comments` return `null` or are excluded from Bob's export.
* **And** Alice, the Team Leader, and the Project Owner query the same task and receive all detailed fields.

### Scenario 6: Leader Self-Review and Self-Extension Confirmation
* **Given** "Eve" is Team Leader for Project Alpha and is also the assignee of Task `DEV-05`.
* **When** Eve submits `DEV-05` for completion review.
* **Then** the task enters `AWAITING_REVIEW`.
* **When** Eve confirms approval of her own task.
* **Then** `DEV-05` enters `COMPLETED`, the review record stores `is_self_approved = True`, and an audit entry records `TASK_SELF_APPROVED`.

### Scenario 7: Approver Absence and Owner/Admin Fallback
* **Given** Team Leader "Eve" has an active dated delegation record marking her absent.
* **When** Contributor "Dave" submits a task for review.
* **Then** Project Owner "Frank" or Admin "Bob" receives fallback authority to approve the review, and the audit log records the deciding actor's ID and role.

### Scenario 8: Calendar Holidays, Timezone Boundaries, and Effective-Dated Changes
* **Given** a company calendar with Monday–Friday working days (09:00–18:00 UTC) and Thanksgiving (Thursday) marked as a holiday.
* **When** a 3-working-day task starts on Wednesday at 10:00 UTC.
* **Then** the planned finish date is Monday at 18:00 UTC (skipping Thursday holiday, Saturday, and Sunday).
* **When** the calendar is updated with an effective date in the future, existing committed task schedules remain unchanged until confirmed by an impact review.

### Scenario 9: Dependency Cycle Prevention and Prerequisite Gating
* **Given** Task 1 is a prerequisite for Task 2.
* **When** a user attempts to add a dependency making Task 2 a prerequisite for Task 1.
* **Then** the service rejects the mutation with `DEPENDENCY_CYCLE_DETECTED`.
* **When** Task 2 is in `PENDING` and Task 1 is `IN_PROGRESS`.
* **Then** Task 2 cannot start; it transitions to `IN_PROGRESS` only after Task 1 reaches `COMPLETED`.

### Scenario 10: Unknown-Impact Pending Requests and Work Continuity
* **Given** Assignee "Dave" submits an extension request on Task `DEV-20`.
* **While** the dependency calculation is pending or unassessed.
* **Then** the request status is `ASSESSMENT_PENDING`, the original approved schedule remains in effect, and Dave continues working and logging progress.

### Scenario 11: Concurrent Approvals and Stale Forecast Rejection
* **Given** Project Alpha has a 5-day buffer before its approved deadline.
* **When** Leader Eve attempts to approve an extension for Task A (consuming 4 days) while Leader Dan simultaneously approves an extension for Task B (consuming 3 days).
* **Then** the second approval fails with an optimistic locking conflict (`VERSION_CONFLICT`), forcing recalculation against the revised project buffer.

### Scenario 12: Deadline Revision vs. Accepted Late Delivery
* **Given** an extension request forecasts project completion past the approved deadline.
* **When** Project Owner "Frank" chooses "Accept Forecast Late Delivery".
* **Then** the approved contractual deadline is preserved in audit records, the forecast completion date is authorized for working schedule display, and "Delivered Late" is applied only upon actual post-deadline completion.

### Scenario 13: Historical Overdue and Completion Preservation
* **Given** legacy tasks completed under Phase 14 with status `DONE`.
* **When** migrated to the portal schema.
* **Then** they transition to `COMPLETED` with `is_legacy_completion = True`, retaining historical completion timestamps without requiring new approvals.

### Scenario 14: Legacy Routes Reject Authorization Bypasses
* **Given** an Employee "Dave" who is not an Admin or Manager.
* **When** Dave attempts to send a legacy GraphQL mutation `createProject` or `changeMemberRole`.
* **Then** the backend service enforces role guards and rejects the request with `FORBIDDEN`, ensuring legacy routes offer no security bypass.

### Scenario 15: HR Role Membership Alone Grants No Project Access
* **Given** User "Helen" holds the company role `HR` and is not a member of Project Alpha.
* **When** Helen attempts to access `/projects/alpha` or query `project(id: "alpha")`.
* **Then** the Gateway returns `FORBIDDEN`.

---

## 12. Open Questions & Settled Decisions

### 12.1 Settled Decisions
1. **Manager Role Scope:** Managers handle ownership, oversight, coordination, and escalation; managers are **not** normal task assignees.
2. **HR Role Scope:** Holding the HR role alone grants zero project or task access. HR manages employment records and coordinates lifecycle events; Admin alone manages application accounts and authorization roles.
3. **Primary Task Lifecycle:** Strictly four states (`PENDING` &rarr; `IN_PROGRESS` &rarr; `AWAITING_REVIEW` &rarr; `COMPLETED`). Blocked is an orthogonal interruption condition; overdue is a dynamic calculation.
4. **Historical Completions:** Legacy completed tasks map to `COMPLETED` with a legacy completion marker, preserving history without fabricated review records.
5. **No Automatic Reopening:** Reopening completed tasks is an exceptional administrative proposal, not a standard lifecycle state transition.
6. **Assignee Progress Ownership:** Normal task progress, status progression, and blocker reporting belong exclusively to the assigned employee; team leaders, managers, and admins do not report progress on an assignee's behalf without an explicitly proposed administrative override procedure.

### 12.2 Open Questions Requiring Policy Decisions
1. **"Pending until finished" phrasing:** Recommended interpretation is **"Pending until impact assessment and approval decisions are complete,"** leaving the original approved schedule effective while pending. Confirm if this interpretation is adopted.
2. **Company Role Composition:** Whether an individual account may ever hold multiple company roles (e.g., composite `HR` + `MANAGER`) or strictly one primary role. (Current storage model enforces a single role; specification preserves single-role storage pending decision).
3. **HR Project Contributor Eligibility:** Whether an individual who holds the `HR` company role may be explicitly assigned as a regular contributor on internal administrative projects via standard project membership. (Security boundary ensures the HR role itself grants no access; policy decision needed on whether project membership may be extended to HR staff).
4. **Partial-Day vs. Whole-Day Scheduling:** Initial proposal establishes whole-working-day scheduling. Confirm whether partial-day or hourly task granularity will be required in later stages.

---

## 13. Implementation Roadmap: Stages R2 through R15

The refinement roadmap consists of fourteen sequential stages (R2 through R15). Each stage delivers frontend views, backend services, schema migrations, tests, and documentation together where applicable. Security enforcement accompanies the introduction of functionality. Each stage terminates with local verification and requires manual user staging, committing, and PR merging before the next stage begins.

**Approved Workflow Exception:** The Stage R1 specification (`docs/portal-refinement-plan.md`) remains unstaged on `portal-r1-baseline` and will be bundled together with the first verified Stage R2 implementation in a single combined PR. Stages R3 through R15 retain their strict individual stage verification gates and manual user Git operations.

* **Stage R2 — Shared Visual Foundation (Implemented & Verified):**
  * Define portal color tokens (navy/ocean foundations, cyan accents, soft typography, restrained shadows).
  * Build reusable visual primitives (cards, stat widgets, segmented status bars, avatar stacks) in `@/components/portal-ui`.
  * Validate responsive viewports and WCAG AA contrast. (Frontend only; no backend/schema changes). Bundled with R1 specification for combined PR submission.
* **Stage R3 — Portal Shell & Access Foundation:**
  * Build role-aware portal layout (`/portals/[role]`) with responsive header, contextual sidebar, and user navigation.
  * Wire role-based route middleware and authorization redirects.
  * Inspect and implement server-side authorization guards, session checks, and Gateway resolvers required for exposed portal entry points (route middleware and redirects alone are not an authorization boundary).
  * Ensure legacy routes remain operational alongside portal routes. (Frontend + Gateway Authorization + Tests).
* **Stage R4 — Admin Account Management & Keycloak Alignment:**
  * Admin Portal view for accounts, role assignments, and credential reset triggers.
  * Add `HR` company role in Keycloak realm and `services/employee` migration.
  * Implement safeguards ensuring runtime application startup never resets or overwrites existing credentials. (Backend + Frontend + Tests).
* **Stage R5 — Company Working Calendar:**
  * Implement `company_calendar_configs` and `company_calendar_exceptions` in Work Service.
  * Admin calendar management interface (working weekdays, hours per weekday, timezone, holidays).
  * Working-day arithmetic engine with effective-date safeguards. (Backend + Frontend + Tests).
* **Stage R6 — Project Ownership & Team Appointments:**
  * Add explicit `owner_employee_id` and `TEAM_LEADER` project role in Work Service.
  * Manager project creation view; team leader appointment dialog.
  * Enforce manager project boundary (managers only access projects they own or lead). (Backend + Frontend + Tests).
* **Stage R7 — Task Planning, Durations & Dependencies:**
  * Task breakdown interface for Team Leaders.
  * Working-day duration inputs; task dependency DAG mapping.
  * Dependency cycle prevention and prerequisite completion gating. (Backend + Frontend + Tests).
* **Stage R8 — Employee Work Portal & Colleague Privacy:**
  * Dedicated Employee Portal view ("My Assigned Work").
  * Status updates (`IN_PROGRESS`, `is_blocked` with blocker reason).
  * Backend and frontend colleague privacy enforcement (masking private dates, notes, and progress from co-members across queries, exports, and notifications). (Backend + Frontend + Tests).
* **Stage R9 — Completion Reviews & Explicit Self-Approval:**
  * Task submission to `AWAITING_REVIEW`.
  * Team Leader review queue with approve and return-for-changes workflows.
  * Explicit self-approval confirmation and immutable audit logging for leader-assigned tasks.
  * Authorized absence delegation fallback to Project Owner or Admin. (Backend + Frontend + Tests).
* **Stage R10 — Extensions & Deadline Decisions:**
  * Assignee extension request workflow (additional working days + reason).
  * Dependency impact evaluation engine supporting unassessed/unknown states.
  * Leader approval within buffer; automatic escalation to Project Owner when exceeding deadline.
  * Concurrency protection via optimistic locking; owner decision flows (revise deadline, accept forecast late delivery, reject with replanning). (Backend + Frontend + Tests).
* **Stage R11 — Manager Coordination & Internal Meetings:**
  * Structured update request forms dispatched to leaders/assignees.
  * Internal check-in and discussion scheduling records with acknowledgement tracking. (Backend + Frontend + Tests).
* **Stage R12 — HR Employee Lifecycle Portal:**
  * HR Portal views for employee directory, departmental transfers, and reporting hierarchies.
  * Onboarding and offboarding checklists coordinated with Admin provisioning.
  * Enforce role boundary: the HR company role alone grants zero project or task access; additional project eligibility remains an unresolved policy decision. (Backend + Frontend + Tests).
* **Stage R13 — Role Dashboards & Purposeful Reporting:**
  * Focused role dashboards (Admin platform overview, Manager project delivery risk, Leader workload distribution, Employee personal schedule).
  * Strict prohibition on decorative vanity charts or ungrounded analytics. (Frontend + Gateway Queries).
* **Stage R14 — Replacement Acceptance & Hardening:**
  * Full end-to-end multi-role browser journeys covering all five portals.
  * Security and permission penetration testing across legacy and portal endpoints.
  * Migration of legacy test coverage to validate new portal views.
  * Preparation and dry-run rehearsal of rollback procedures. (Verification & Acceptance Gate).
* **Stage R15 — Legacy Interface Retirement:**
  * Formal owner acceptance sign-off.
  * Safe deprecation and removal of obsolete legacy views and components.
  * Documentation consolidation and final baseline establishment. (Cleanup).
