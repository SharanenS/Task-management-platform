# Work Service

The Work Service owns projects, project lifecycle, project membership, project
roles, and optimistic versions. It owns a separate PostgreSQL database and Alembic
migration history. It stores stable Employee Service UUIDs without cross-database
foreign keys.

Only the gateway calls its private HTTP API. Every request requires a dedicated
constant-time validated service credential plus the current actor's Employee UUID
and application role. The gateway reloads the actor from Employee Service before
each protected GraphQL operation; Work Service independently enforces membership
and project-manager rules.

Projects move from `DRAFT` to `ACTIVE`, from `ACTIVE` to `ARCHIVED`, and from
`ARCHIVED` back to `ACTIVE`. Archived projects are read-only. Project keys are
normalized, unique, indexed, and immutable. A draft or active project must retain
at least one `PROJECT_MANAGER`; `CONTRIBUTOR` membership is read-only.

Run migrations and checks from this directory with the repository virtual
environment:

```powershell
..\..\.venv\Scripts\python.exe -m alembic upgrade head
..\..\.venv\Scripts\python.exe -m pytest
..\..\.venv\Scripts\python.exe -m ruff check .
..\..\.venv\Scripts\python.exe -m ruff format --check .
..\..\.venv\Scripts\python.exe -m mypy app
```
