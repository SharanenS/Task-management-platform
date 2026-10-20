# Job Service

Job Service owns durable job submissions, typed payload validation, actor-scoped
idempotency, execution state, attempt history, and bounded results in its own
PostgreSQL database.

Phase 7 supports `PROJECT_TASK_EXPORT`. Manual dispatch requires a `SUBMITTED` job
at the expected version and publishes only its UUID to the durable
`job.execution` RabbitMQ queue with routing key `job.execute`. The publisher is an
isolated temporary adapter so Phase 8 can replace direct publication with an
outbox without changing the GraphQL contract.

The Celery worker accepts JSON only, has no result backend, and uses late
acknowledgement, worker-loss rejection, prefetch one, concurrency two, two bounded
retries, and bounded task time limits. Claiming a queued job atomically creates a
single running attempt. Duplicate delivery is a safe no-op after a successful
claim. Settlement atomically updates the attempt, job, and persisted result.

At execution time the worker reloads the current Employee profile and revalidates
project access through Work Service. It never reads another service's database.
CSV output uses six allowlisted fields, a 500-row limit, a 256,000-byte limit,
UTF-8, standard CSV quoting, SHA-256 metadata, and formula-prefix neutralization.
CSV content and upstream error details are never logged.

Direct publication has a known commit-to-publish crash window, and a lost
publisher confirmation can make delivery ambiguous. Idempotent claim handles
duplicate delivery but does not guarantee publication. A worker crash after claim
can leave a job running. Phase 8 outbox work and Phase 9 lease, fencing, and
recovery work have not started.

The internal HTTP API and execution dependencies use separate credentials and are
not published on the host. The GraphQL Gateway remains the only public business
API.
