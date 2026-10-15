# Work Service

The Work Service owns projects, memberships, tasks, task assignment and lifecycle,
comments, append-only task activity, and optimistic versions. It owns a separate
PostgreSQL database and Alembic migration history. It stores stable Employee
Service UUIDs without cross-database foreign keys or copied profile fields.

Only the gateway calls its private HTTP API. Every request requires a dedicated
constant-time validated service credential plus the current actor's Employee UUID
and application role. The gateway reloads the actor from Employee Service before
each protected GraphQL operation; Work Service independently enforces membership
and project-manager rules.

Projects move from `DRAFT` to `ACTIVE`, from `ACTIVE` to `ARCHIVED`, and from
`ARCHIVED` back to `ACTIVE`. Archived projects are read-only. Project keys are
normalized, unique, indexed, and immutable. A draft or active project must retain
at least one `PROJECT_MANAGER`; `CONTRIBUTOR` membership is read-only.

Task references combine the immutable project key with a project-scoped number.
The number is allocated while the project row is locked and is protected by a
database unique constraint. Task mutations lock the relevant rows and require an
optimistic version. Status transitions follow the explicit TODO, IN_PROGRESS,
BLOCKED, DONE, and CANCELLED state machine. Archived projects reject task writes.

Project members may create tasks and comments. Project managers and application
administrators manage metadata and assignment. Contributors may change status only
on tasks assigned to them. Comments are immutable plain text. Activity records are
append-only, contain constrained non-sensitive changes, and are committed in the
same transaction as each mutation.

Run migrations and checks from this directory with the repository virtual
environment:

```powershell
..\..\.venv\Scripts\python.exe -m alembic upgrade head
..\..\.venv\Scripts\python.exe -m pytest
..\..\.venv\Scripts\python.exe -m ruff check .
..\..\.venv\Scripts\python.exe -m ruff format --check .
..\..\.venv\Scripts\python.exe -m mypy app
```
