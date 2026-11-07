# Phase 12 verification — Advanced Dashboard + UX Refinement

Status: **Implemented; pending owner acceptance**

Baseline: Merge commit `36eb11b` on `main`. Branch: `phase-12-dashboard-ux`.
All unstaged changes remain preserved. No Git commits, branch modifications, or remote changes were made.

---

## 1. Architecture and Authorization Boundaries

### 1.1 GraphQL Contract (`gateway/schema.graphql`, `gateway/app/schema.py`)
Exposes a single typed, bounded aggregate query `dashboard: DashboardData!` derived securely from the authenticated caller's profile (`EmployeeProfile`). Identity, role, and scoping are enforced exclusively on the server:

```graphql
type DashboardData {
  workAvailable: Boolean!
  jobAvailable: Boolean!
  projectMetrics: DashboardProjectMetrics
  taskMetrics: DashboardTaskMetrics
  assignedTaskMetrics: DashboardTaskMetrics
  recentProjects: [Project!]
  recentAssignedTasks: [DashboardAssignedTask!]
  jobMetrics: DashboardJobMetrics
  recentJobs: [Job!]
}
```

- Inactive or missing profiles fail closed with `FORBIDDEN` before downstream aggregate requests execute.
- Downstream request pattern per dashboard query: exactly 1 profile query to Employee Service, followed concurrently by up to 2 aggregate queries (1 to Work Service and 1 to Job Service). Aggregate requests are distinct from the initial caller identity verification.

### 1.2 Downstream Service Authorization & Query Scoping
- **Work Service (`services/work/app/service.py`, `services/work/app/main.py`)**:
  - Internal endpoint: `GET /internal/dashboard/metrics`
  - Authorization scoping:
    - `MEMBER`:
      - Accessible projects include only projects where the caller is an active member.
      - Personal assigned task totals include only tasks assigned to that employee within currently accessible projects.
      - `taskMetrics` (managed project overview) returns `null`.
    - `MANAGER`:
      - Managed project metrics include only projects where the caller holds `ProjectRole.MANAGER`.
      - Managed task totals (`taskMetrics`) include only tasks within projects managed by the caller, excluding projects where they are only a contributor or reader.
      - Personal assigned tasks are scoped to accessible projects.
    - `ADMIN`:
      - Receives platform-wide project and task metrics across all active, draft, and archived projects.
  - Project joins cannot double-count projects or tasks because aggregation uses grouped/filtered subqueries and distinct counts.
  - Overdue date boundary: `Task.due_date < date.today() & ~Task.status.in_([TaskStatus.DONE, TaskStatus.CANCELLED])`. Tasks due today or in the future are never counted as overdue; tasks with `null` due dates are not overdue; terminal tasks (`DONE`, `CANCELLED`) are excluded regardless of due date. Tested against yesterday, today, tomorrow, null, and terminal states.
  - Revocation reactivity & task assignment isolation:
    - Work domain membership removal rule: `remove_member` in `services/work/app/service.py` requires reassigning or unassigning tasks before membership can be removed (`WorkError("MEMBER_HAS_ASSIGNED_TASKS", 409)`).
    - Database aggregate defense: If a task remains assigned to an employee whose project membership was removed (simulated in DB), `get_dashboard_metrics` inner-joins `ProjectMembership` on `(ProjectMembership.project_id == Task.project_id) & (ProjectMembership.employee_id == actor.employee_id)`, which evaluates to 0 rows and cleanly excludes the stale task from personal assigned counts and previews.
    - Manager authority reduction: When a manager is demoted to `CONTRIBUTOR` via `change_member_role`, `managed_total_count` and `task_metrics` drop to 0, while `project_metrics.total_count` and personal `assigned_task_metrics` remain preserved.
    - Both behaviors verified in unit test `test_revocation_isolation_stale_assignment_and_manager_authority_reduction` (`test_dashboard.py`) and PostgreSQL integration test `test_postgres_revocation_isolation_and_manager_authority_reduction` (`test_postgres.py`).
  - SQL query count invariance: Uses conditional SQL aggregation (`func.count(case(...))`) to calculate all status totals and overdue counts in single SQL statements per entity. Executed statement count is strictly invariant across fixture sizes: exactly **6 SQL statements** executed regardless of the number of projects or tasks (measured query-count invariance across scale, not constant execution time).
- **Job Service (`services/job/app/service.py`, `services/job/app/main.py`)**:
  - Internal endpoint: `GET /internal/dashboard/metrics`
  - Submitter ownership scoping:
    - `MEMBER` and `MANAGER` receive counts and history of only their own submitted jobs (`submitter_employee_id == actor.id`).
    - `ADMIN` receives platform-wide background job summaries.
  - Eager loads `selectinload(Job.publications)` to eliminate $N+1$ serialization overhead.
  - SQL query count invariance: Executed statement count is strictly invariant across fixture sizes: exactly **3 SQL statements** executed regardless of the number of jobs (measured query-count invariance across scale, not constant execution time).

### 1.3 Gateway Resilience & Partial Failure
- Aggregate requests to Work and Job services execute concurrently via `asyncio.gather`.
- If Work Service fails: `workAvailable: false`, Work metrics are `null`, Job metrics are returned normally without failing the GraphQL request.
- If Job Service fails: `jobAvailable: false`, Job metrics are `null`, Work metrics are returned normally.
- If both services fail: Returns a typed `GraphQLError` with code `SERVICE_UNAVAILABLE`.
- Partial failure surfaces section-level inline retry banners in the UI without crashing the overall dashboard view.

### 1.4 Frontend UX, Pagination Reset, and Accessibility
- **Dashboard (`frontend/src/features/dashboard/workspace-dashboard.tsx`, `frontend/src/app/(protected)/page.tsx`)**:
  - Replaced all static mock numbers and demo banners with typed live metrics.
  - Role-adaptive interface for `MEMBER`, `MANAGER`, and `ADMIN`.
  - Accessible skeleton loading states (`aria-label="Loading workspace dashboard"`).
  - Truthful legitimate zero handling: 0 counts render as "0", and genuine empty states (`EmptyState`) render when lists are empty.
  - Section-level inline error banners with retry for partial failures.
- **Responsive Layout & Viewport Overflow Elimination**:
  - Grid layouts adapt across screen sizes (`grid-cols-2 sm:grid-cols-4`, `p-4 sm:p-6` cards, `min-w-0 flex-1` on list items and grid containers).
  - Fully eliminates document horizontal overflow across desktop (1280px), tablet (768px), and mobile (390px) viewports (`document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1`).
- **Pagination Reset on Filter Changes**:
  - Changing any filter after navigating past the first page resets the pagination request/cursor to `null` across all directories:
    - `ProjectDirectory`: changing `status` resets `cursor` to `null` and clears history. Verified in `frontend/tests/projects.test.tsx`.
    - `TaskDirectory`: changing `status`, `priority`, or `unassigned` resets `after` to `null`. Verified in `frontend/tests/tasks.test.tsx`.
    - `JobDirectory`: changing `status` or `jobType` resets `cursor` to `null` and clears history. Verified in `frontend/tests/jobs.test.tsx`.
- **Tied-Value Ordering**:
  - Timestamp ordering ties are deterministically resolved by entity UUID descending:
    - Work projects: `.order_by(Project.updated_at.desc(), Project.id.desc())`
    - Work tasks: `.order_by(Task.updated_at.desc(), Task.id.desc())`
    - Jobs: `.order_by(Job.created_at.desc(), Job.id.desc())`
- **Keyboard Reachability & Visible Focus**:
  - Verified accessible names for interactive controls (`Refresh`, `View all projects`, `System status`, metric card links, task preview links).
  - Verified keyboard focusability via `Tab` navigation, visible focus styling (`focus:ring-2`, `focus:underline`), and keyboard activation via `Enter`. Verified in `frontend/tests/dashboard.test.tsx` and Playwright acceptance test.
- **Filter Handoffs & URL Parameters**:
  - Metric cards link directly to filtered views:
    - Active projects: `/projects?status=ACTIVE`
    - Draft projects: `/projects?status=DRAFT`
    - Archived projects: `/projects?status=ARCHIVED`
    - Recent project detail: `/projects/[id]`
    - Assigned tasks: `/projects/[id]/tasks`
    - Background jobs: `/jobs`, `/jobs?status=SUCCEEDED`, `/jobs?status=FAILED`, `/jobs?status=RUNNING`, `/jobs?status=SUBMITTED`
  - Refined `ProjectDirectory`, `JobDirectory`, and `TaskDirectory` to initialize filters from URL parameters and preserve them across navigation, browser history (back/forward), and page reloads.
  - Expanded `JobDirectory` status `<select>` to expose all 6 `JobStatus` values (`SUBMITTED`, `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED`).

---

## 2. Container Build, Parity, and Service Health

### 2.1 Authorized Rebuild and Recreation
The four authorized containers (`work`, `job`, `gateway`, `frontend`) were rebuilt and recreated via:
```bash
docker compose build work job gateway frontend
docker compose up -d --no-deps --force-recreate --wait work job gateway frontend
```
No workers, publishers, consumers, databases, Keycloak, RabbitMQ, or Redis containers were touched. Run-owned disposable resources were completely reconciled and removed; persistent development databases and pre-existing volumes were preserved untouched.

### 2.2 Image Identities & Runtime Evidence
- **Image IDs**:
  - `frontend`: `0235d6259fbc`
  - `gateway`: `63a71139e106`
  - `work`: `aa318f32e06e`
  - `job`: `2c871cc5f732`
- **Frontend Parity**:
  - Served behavior verified: HTTP 307 redirecting unauthenticated `/` requests to `/sign-in?returnTo=%2F`, authenticated dashboard rendering, live data. Note that missing source files inside a standalone production Next.js image do not establish staleness; image/build identity and served behavior are the appropriate evidence.
  - Frontend-to-Gateway internal connectivity confirmed: `wget http://gateway:8000/health/live` returned `{"status":"alive"}`, and `/health/ready` returned `{"status":"ready"}`.
- **Service Parity**:
  - Work service live container matches source: `/internal/dashboard/metrics` defined in `/app/app/main.py` (line 145).
  - Job service live container matches source: `/internal/dashboard/metrics` defined in `/app/app/main.py` (line 85).
  - Gateway live container matches source: `dashboard: DashboardData` defined in `/app/app/schema.py` (line 1099).
- **Compose Service Health**:
  - All 23 services running and healthy (`docker compose ps`).
- **Database Migration Heads**:
  - `work`: `20261029_02`
  - `job`: `20261029_06`
  - `employee`: `20261014_02`
  - `notification`: `20261029_02`
  - `workflow`: `20261028_01`

---

## 3. Browser Acceptance Verification

### 3.1 Test Execution
- **Specification**: `frontend/tests/e2e/dashboard-acceptance.spec.ts`
- **Runner**: Playwright desktop project, single worker, zero retries:
  ```powershell
  Get-Content .env | ForEach-Object { if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') { [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2]) } }; cd frontend; npx playwright test tests/e2e/dashboard-acceptance.spec.ts --project=desktop --workers=1 --retries=0
  ```
- **Result**: **1 passed in 2.8m** (100% pass with 0 retries)

### 3.2 Emitted Milestone Sequence
1. `MULTI_ROLE_ENV_READY`: Environment and disposable test actors verified.
2. `ADMIN_SETUP_COMPLETE`: Seeded disposable project, task, and job fixtures via GraphQL mutations.
3. `MEMBER_BOUNDARY_COMPLETE`: Verified member personal assigned work, accessible project count, submitted jobs, and absence of managed project sections.
4. `VIEWPORT_AND_ACCESSIBILITY_COMPLETE`: Verified responsive layout without horizontal overflow across 1280px desktop, 768px tablet, and 390px mobile viewports (`scrollWidth <= clientWidth + 1`). Verified accessibility headings, keyboard focusability (`focus:ring-2`), and skeleton loading states.
5. `FILTER_AND_HISTORY_COMPLETE`: Verified metric card click navigating to `/projects?status=ACTIVE` URL filter handoff, confirmed absence of pagination cursor in URL, verified browser Back, Forward, Back history navigation, page reload, and Refresh button action.
6. `MANAGER_BOUNDARY_COMPLETE`: Verified manager view showing managed project card (1 managed project, "Projects you manage" note) and "Managed Projects Tasks" breakdown.
7. `ADMIN_BOUNDARY_COMPLETE`: Verified platform-wide view showing "Platform Tasks Breakdown" heading and "All managed projects" scope note.
8. `DYNAMIC_REVOCATION_COMPLETE`: Verified Work domain rejected removing member while task was assigned; unassigned disposable task via `assignTask`; removed member from project; verified member re-login immediately reflects 0 accessible projects and "No assigned tasks" empty state.
9. `CLEANUP_COMPLETE`: Scoped cleanup of all disposable projects, tasks, activity entries, outbox records, notifications, and Keycloak test users. Exact post-cleanup assertions verified 0 remaining records.

---

## 4. Automated Test Suite Results

### 4.1 Work Service Unit Tests
- **Command**: `cd services/work; pytest tests/test_dashboard.py`
- **Result**: **7 passed in 12.41s**
- **Covered**: Empty workspace zeros, member metrics scoping, manager managed vs. accessible distinction, admin platform-wide coverage, overdue date boundary, O(1) query count invariance with scale, internal HTTP API endpoint, and revocation isolation with stale task assignment defense and manager authority reduction.

### 4.2 Job Service Unit Tests
- **Command**: `cd services/job; pytest tests/test_dashboard.py`
- **Result**: **7 passed in 9.06s**
- **Covered**: Empty workspace zeros, member/manager ownership scoping, admin platform-wide coverage, logical job vs. attempt counting, bounded deterministic recent jobs, O(1) query count invariance with scale, and internal HTTP API endpoint.

### 4.3 Gateway Unit Tests
- **Command**: `cd gateway; pytest tests/test_gateway.py`
- **Result**: **122 passed in 28.65s**
- **Covered**: Unauthenticated rejection, inactive and missing profile rejection (`FORBIDDEN`), `MEMBER`, `MANAGER`, and `ADMIN` typed aggregate responses, partial failure of Work Service, partial failure of Job Service, dual service failure (`SERVICE_UNAVAILABLE`), and bounded downstream request counts.

### 4.4 Frontend Unit Tests
- **Command**: `npm --prefix frontend test -- tests/projects.test.tsx tests/tasks.test.tsx tests/jobs.test.tsx tests/dashboard.test.tsx --run`
- **Result**: **4 test files passed, 28 tests passed in 29.50s**
- **Covered**:
  - `dashboard.test.tsx` (9 tests): Skeleton loading, role-adaptive rendering (MEMBER, MANAGER, ADMIN), truthful empty states with legitimate zeros, partial Work Service failure resilience, and accessible control names, keyboard reachability, visible focus styling, and keyboard activation.
  - `projects.test.tsx` (6 tests): Accessible project list, creation controls, optimistic metadata update, assigned member visibility protection, and pagination cursor/history reset on status filter change.
  - `tasks.test.tsx` (5 tests): Task list rendering, board lanes, contributor controls scoping, and pagination cursor (`after`) reset on status, priority, or unassigned filter changes.
  - `jobs.test.tsx` (8 tests): Job list, creation, duplicate prevention, terminal CSV rendering, failure summaries, recovered attempts, ADMIN retry confirmation, and pagination cursor/history reset on status or jobType filter changes.

### 4.5 Isolated PostgreSQL Integration Tests
- **Work PostgreSQL Suite (`services/work/tests/test_postgres.py`)**:
  - Target: Isolated temporary database `work_test_p12` on `work-db` (port 5436), migrated from zero to head (`20261029_02`).
  - Result: **13 passed, 0 failed in 21.20s**.
  - Verified:
    - `test_postgres_dashboard_metrics_and_date_boundaries`: Proved overdue semantics against real PostgreSQL date types across yesterday (`due_date < today`), today (`due_date == today`), tomorrow (`due_date > today`), and `null`. Proved terminal tasks (`DONE`, `CANCELLED`) are never counted as overdue regardless of due date. Proved MEMBER, MANAGER, and ADMIN scoping boundaries.
    - `test_postgres_revocation_isolation_and_manager_authority_reduction`: Proved that deleting project membership while leaving a task assigned in DB excludes the stale task from personal aggregates via inner-join semantics; proved that demoting a manager to CONTRIBUTOR reduces managed totals to 0 while preserving accessible project and personal task totals.
    - `test_postgres_dashboard_query_count_invariance`: Query count measured via cursor execute listeners across small (2 projects, 6 tasks) vs. large (8 projects, 80 tasks) fixtures: exactly **6 SQL statements** executed in both cases ($O(1)$ statement count invariance).
  - Cleanup: `work_test_p12` dropped cleanly; zero temporary databases remain. Retained development data untouched.
- **Job PostgreSQL Suite (`services/job/tests/test_postgres.py`)**:
  - Target: Isolated temporary database `job_test_p12` on `job-db` (port 5437), migrated from zero to head (`20261029_06`).
  - Result: **22 passed, 0 failed in 16.61s**.
  - Verified:
    - `test_postgres_job_dashboard_metrics`: Proved submitter ownership boundaries (`MEMBER` sees only their jobs; `ADMIN` sees all jobs).
    - `test_postgres_job_dashboard_query_invariance`: Query count measured across small (2 jobs) vs. large (15 jobs) fixtures: statement count remains strictly constant at **3 SQL statements** ($O(1)$ statement count invariance).
  - Cleanup: `job_test_p12` dropped cleanly; zero temporary databases remain. Retained development data untouched.

---

## 5. Static Analysis, Linting, and Type Safety

- **Prettier**: `npm --prefix frontend run format:check` -> **Passed** (All matched files use Prettier code style!).
- **ESLint**: `npm --prefix frontend run lint` -> **Passed** (0 warnings, 0 errors).
- **TypeScript**: `npm --prefix frontend run typecheck` -> **Passed** (0 errors).
- **Next.js Production Build**: `npm --prefix frontend run build` -> **Passed** (compiled successfully).
- **Python Ruff**: `ruff check gateway/ services/` -> **Passed** (All checks passed).
- **Python Ruff Format**: `ruff format --check gateway/ services/` -> **Passed** (115 files already formatted).
- **Python Strict Mypy (`mypy app`)**:
  - `gateway`: Success: no issues found in 10 source files
  - `services/work`: Success: no issues found in 9 source files
  - `services/job`: Success: no issues found in 15 source files
  - `services/notification`: Success: no issues found in 9 source files
  - `services/employee`: Success: no issues found in 10 source files
  - `services/workflow`: Success: no issues found in 9 source files
- **Compose Configuration Validation**: `docker compose config --quiet` -> **Passed** (code 0).
- **Schema Export & Codegen Consistency**:
  - `pytest gateway/tests/test_gateway.py -k test_schema_export_matches_runtime` -> **1 passed**.
  - `npm --prefix frontend run codegen` -> **Passed** (code 0).
- **Git Diff Check**: `git diff --check` -> **Passed** (0 whitespace or indentation errors).

---

## 6. Database Integrity and Cleanup Evidence

- **Disposable Task & Project Fixture Removal**:
  - Query: `SELECT count(*) FROM tasks WHERE title LIKE 'Task for Member%';` -> **0**
  - Query: `SELECT count(*) FROM projects WHERE name LIKE 'Dashboard Project%';` -> **0**
- **Disposable User Fixture Removal**:
  - Query: `SELECT count(*) FROM employees WHERE username LIKE 'p12-%';` -> **0**
- **Primary Administrator Preservation**:
  - Query: `SELECT id, keycloak_subject, username, email, role, active, provisioning_status FROM employees WHERE username = 'local.user';`
  - Result: UUID `590e0b8f-b774-4db4-84c7-82942e23eea3`, Keycloak subject `2926ca8c-93d4-4c69-9280-fa826b423aae`, role `ADMIN`, `active=t`, `provisioning_status=COMPLETE` verified intact and unmodified.
- **Temporary Database Absence**:
  - Confirmed via `\l` on `work-db` and `job-db` that `work_test_p12` and `job_test_p12` are completely dropped; only permanent system and service databases (`work`, `job`, `postgres`, `template0`, `template1`) remain. Retained development data untouched.
