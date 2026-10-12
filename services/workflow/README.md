# Workflow Service (future phase)

Owns supported automation definitions, trigger evaluation, and workflow history.
Introduced in Phase 10. Consumes versioned domain events idempotently and requests
jobs through explicit durable contracts. Owns its database and outbox.
No arbitrary user code, visual workflow designer, or Phase 1 process.
