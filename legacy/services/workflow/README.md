# Workflow Service

Owns supported automation definitions, trigger evaluation, and workflow history.
Introduced in Phase 10. It consumes the versioned `TASK_COMPLETED` event
idempotently and requests `PROJECT_TASK_EXPORT` jobs using deterministic
execution-derived idempotency. It owns rules, its source-event inbox, execution
history, and a separate PostgreSQL schema.
No arbitrary user code, visual workflow designer, or Phase 1 process.
