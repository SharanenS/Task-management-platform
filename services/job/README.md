# Job Service

Job Service owns durable job submissions, typed payload validation, idempotency,
ownership enforcement, and the empty attempt-history foundation in its own
PostgreSQL database.

Phase 6 supports only `PROJECT_TASK_EXPORT`. Its payload contains a project UUID,
the fixed `CSV` format, and an `includeCompleted` boolean. Gateway verifies current
project access before submission. Job Service stores the stable project identifier
without copying Work Service or Employee Service data.

Every Phase 6 submission starts as `SUBMITTED`. RabbitMQ, Celery, workers,
dispatch, execution, retries, progress, and results are absent until Phase 7. The
attempt table therefore remains empty for Phase 6 jobs.

The internal HTTP API requires a dedicated service credential and validated actor
headers. It is not published on the host. The GraphQL Gateway is the only public
business API.
