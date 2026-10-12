# Job Execution Service (future phase)

Owns durable job records, attempts, publication, worker claims, retries,
leases, fencing, and recovery. Introduced in Phase 6 and expanded in Phases 7–9.
PostgreSQL is authoritative; Celery and RabbitMQ provide execution and transport.
At-least-once delivery, not exactly-once execution. Owns its database and outbox.
No running workers, job submission, or job tables in Phase 1.
