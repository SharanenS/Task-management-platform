# Enterprise Task Platform — Operational Runbook

## 1. System Architecture

### 1.1 Normal Dispatch & Execution Flow
```
Client Request
      │
      ▼
   [ API ]
      │
      ▼  (Single Atomic PostgreSQL Transaction)
   ┌────────────────────────────────────────────────────────┐
   │ 1. INSERT INTO jobs (status='QUEUED', ...)             │
   │ 2. INSERT INTO outbox_events (status='PENDING', ...)   │
   └────────────────────────────────────────────────────────┘
      │
      ▼  (PostgreSQL Transaction Committed)
[ Outbox Publisher Daemon ]
   │ 1. Atomic claim via SELECT FOR UPDATE SKIP LOCKED
   │ 2. Set status='CLAIMED', claim_owner=UUID, lease_until=now()+30s
   │ 3. Dispatch task to RabbitMQ / Celery queue
   │ 4. Fenced settlement: status='PUBLISHED' (validates claim_owner & active lease)
      │
      ▼
[ RabbitMQ Message Broker ]
      │
      ▼
[ Celery Worker Pool ]
   │ 1. Atomic claim: UPDATE jobs SET status='PROCESSING', claim_owner=UUID,
   │    lease_until=now()+300s WHERE id=:id AND status='QUEUED'
   │ 2. Execute task logic
   │ 3. Fenced settlement: UPDATE jobs SET status='COMPLETED' | 'FAILED'
   │    WHERE id=:id AND status='PROCESSING' AND claim_owner=:owner AND lease_until > now()
```

### 1.2 Recovery Flow (Stalled or Expired Jobs)
```
[ Job Recovery Daemon (Polls every 5s) ]
      │
      ▼
1. Atomic Reclaim:
   SELECT FOR UPDATE SKIP LOCKED
   UPDATE jobs SET claim_owner=UUID, execution_lease_until=now()+300s
   WHERE status='PROCESSING' AND execution_lease_until < now()
      │
      ▼  (Transaction Committed to PostgreSQL)
2. Direct Celery Dispatch to Transport Queue
      │
      ▼
[ Celery Worker Pool ]
   │ 1. Picks up recovered job task
   │ 2. Executes task
   │ 3. Fenced settlement with recovered claim owner & active lease
```

---

### 1.3 Execution Semantics & Idempotency Guarantee
The platform provides:
* **At-least-once** broker and task delivery (RabbitMQ/Celery)
* **Durable PostgreSQL state** as the authoritative source of truth for jobs and outbox events
* **Fenced worker and publisher settlement** preventing stale owners from overwriting newer claims
* **Stale-owner protection** via unexpired lease checks (`lease_until >= NOW()`)
* **Lease-based automatic recovery** for stalled or crashed workers and publishers

> **CRITICAL ARCHITECTURAL LIMITATION — NO ARBITRARY EXACTLY-ONCE SIDE EFFECTS:**
> The platform does **NOT** guarantee exactly-once execution of arbitrary external side effects.
> 
> Consider the unavoidable failure window:
> 1. Worker claims job and begins execution.
> 2. Handler initiates/completes a non-transactional external side effect (e.g., external HTTP call, email send, third-party API write).
> 3. Worker process crashes or loses network connectivity immediately prior to committing PostgreSQL settlement (`status='COMPLETED'`).
> 4. The worker's execution lease expires.
> 5. Job Recovery Daemon reclaims the job and dispatches it to Celery again.
> 6. A subsequent worker claims and re-executes the job.
>
> In this scenario, the external side effect will occur a second time unless the application handler incorporates an application-level idempotency key, unique constraint, or deduplication mechanism. Handlers performing non-transactional external side effects MUST use application-level idempotency keys or deduplication if duplicate effects are unacceptable. The platform cannot be described as "effectively-once" or "exactly-once" for external side effects without this qualification.

---

## 2. Failure Path Guarantees & Behavior

| Failure Scenario | System Behavior & Guarantee |
| :--- | :--- |
| **1. API Crash During Job Creation** | PostgreSQL transaction rolls back. Neither the job nor the outbox event is persisted. No partial state, no orphaned tasks. Client receives a connection error and safely retries. |
| **2. Publisher Crash After Claiming Outbox Event** | The outbox event remains in `CLAIMED` status in PostgreSQL. Its publisher lease expires after `OUTBOX_PUBLISHER_LEASE_SECONDS` (default 30s). Another publisher instance or subsequent poll atomically reclaims the event via `SELECT FOR UPDATE SKIP LOCKED` and publishes it to RabbitMQ. |
| **3. Worker Crash After Claiming Job** | The job remains in `PROCESSING` status. No completion or failure is recorded. When `execution_lease_until` expires (default 300s), the Job Recovery Daemon reclaims the job atomically, assigns a fresh lease and claim owner, and re-dispatches it to Celery. |
| **4. RabbitMQ Unavailable** | Database state remains durable and uncorrupted. Outbox publisher catches the broker error, sanitizes the message, records failure in PostgreSQL (resetting the event to `PENDING` with cleared lease), and retries on the next poll cycle. No in-memory buffering is used; PostgreSQL provides full durability. |
| **5. Recovery Dispatch Failure** | If Celery/RabbitMQ is unreachable during recovery dispatch, the job remains in `PROCESSING` status with its durable recovered claim in PostgreSQL. Settlement cannot occur erroneously. Once the recovery lease expires, the next recovery daemon poll will retry dispatch. |
| **6. Stale Worker Settlement Attempt** | If a worker experiences a long pause exceeding its lease, and another worker or recovery daemon has reclaimed the job, the stale worker's settlement query matches zero rows (`WHERE claim_owner=:stale_owner AND lease_until >= now()`). The stale worker raises a fenced ownership error and aborts without corrupting state. |
| **7. Stale Publisher Settlement Attempt** | If an outbox publisher attempts to settle an event after its lease expired and was reclaimed by another publisher, `OutboxRepository.mark_published` matches zero rows. The stale update is rejected with zero side-effects. |

---

## 3. Operational Inspection Queries (Verified PostgreSQL Schema)

Connect to PostgreSQL via `psql`:
```bash
psql -h localhost -p 5434 -U taskplatform_user -d taskplatform
```

### 3.1 Stuck / Stalled PROCESSING Jobs (Lease Expired)
```sql
SELECT id, project_id, job_type, status, execution_claim_owner,
       execution_lease_until, updated_at
FROM jobs
WHERE status = 'PROCESSING'
  AND execution_lease_until < NOW()
ORDER BY execution_lease_until ASC;
```

### 3.2 Active Processing Jobs (Valid Active Lease)
```sql
SELECT id, project_id, job_type, execution_claim_owner,
       execution_lease_until,
       ROUND(EXTRACT(EPOCH FROM (execution_lease_until - NOW()))) AS lease_remaining_seconds
FROM jobs
WHERE status = 'PROCESSING'
  AND execution_lease_until >= NOW();
```

### 3.3 Stuck / Expired Outbox Events
```sql
SELECT id, aggregate_id, event_type, status, claim_owner,
       lease_until, attempt_count, last_error
FROM outbox_events
WHERE status = 'CLAIMED'
  AND lease_until < NOW();
```

### 3.4 Outbox Publishing Failures
```sql
SELECT id, aggregate_id, event_type, status, attempt_count, last_error, updated_at
FROM outbox_events
WHERE status = 'FAILED'
ORDER BY updated_at DESC
LIMIT 20;
```

### 3.5 Repeated Job Failures
```sql
SELECT id, project_id, job_type, error_message, updated_at
FROM jobs
WHERE status = 'FAILED'
ORDER BY updated_at DESC
LIMIT 20;
```

---

## 4. Safe Restart Procedures

Always adhere to the dependency order when restarting infrastructure:

### 4.1 Safe Restart Order (Full Stack)
1. **PostgreSQL** (`docker compose restart postgres`)
2. **RabbitMQ** (`docker compose restart rabbitmq`)
3. **Redis & Keycloak** (`docker compose restart redis keycloak`)
4. **Backend API** (`docker compose restart backend`)
5. **Worker & Daemons** (`docker compose restart celery-worker outbox-publisher job-recovery`)
6. **Frontend** (`docker compose restart frontend`)

### 4.2 Individual Component Restarts
- **Backend API**: Stateless. Can be restarted anytime with zero downtime if load balanced. Docker healthcheck (`/api/v1/health/live`) ensures readiness before traffic routing.
- **Celery Worker**: Workers handle graceful shutdown via `SIGTERM`. In-flight tasks exceeding the graceful period will have their leases expire and will be cleanly recovered by the recovery daemon.
- **Outbox Publisher**: Daemon can be restarted at any point. Active claimed batches will expire within 30s and resume publication automatically via PostgreSQL durability.
- **Job Recovery Daemon**: Can be restarted without risk. It runs an atomic sweep every 5s; missed cycles simply resume on the next poll.
- **RabbitMQ**: If RabbitMQ restarts, Celery reconnects on backoff. The outbox publisher resets failed dispatches in PostgreSQL and retries once the broker returns.

---

## 5. Operational Metrics Catalog

Prometheus metrics endpoint: `GET /metrics` or `GET /api/v1/metrics`.
Format: `text/plain; version=0.0.4; charset=utf-8` (Prometheus 0.0.4 text exposition format).

| Metric Name | Type | Labels | Operational Meaning / Alert Threshold |
| :--- | :--- | :--- | :--- |
| `jobs_queued` | Gauge | `job_type` | Number of jobs waiting in `QUEUED` state. Scraped from live PostgreSQL. |
| `jobs_processing` | Gauge | `job_type` | Number of jobs currently being executed by workers. Scraped from live PostgreSQL. |
| `jobs_completed` | Gauge | `job_type` | Total number of completed jobs in PostgreSQL. |
| `jobs_failed` | Gauge | `job_type` | Total number of failed jobs in PostgreSQL. |
| `jobs_expired` | Gauge | none | Current number of processing jobs whose execution lease has expired. Alert if sustained > 0. |
| `jobs_recovered_total` | Counter | none | Cumulative count of expired jobs reclaimed by recovery daemon. |
| `job_executions_total` | Counter | `job_type`, `outcome` | Cumulative count of worker job executions. |
| `job_execution_failures_total` | Counter | `job_type`, `error_type` | Cumulative count of worker job execution failures. |
| `job_execution_duration_seconds`| Histogram | `job_type` | Duration of job execution handler in seconds. |
| `outbox_pending` | Gauge | none | Current number of outbox events awaiting publication. |
| `outbox_failures` | Gauge | none | Current number of outbox events that encountered publication errors. |
| `outbox_published_total` | Counter | none | Cumulative count of outbox events published to message broker. |
| `outbox_failures_total` | Counter | none | Cumulative count of outbox event publication failures. |
| `outbox_publish_duration_seconds` | Histogram | none | Duration of outbox event dispatch in seconds. |
| `http_requests_total` | Counter | `method`, `status` | Cumulative count of HTTP requests (bounded labels). |
| `http_request_duration_seconds` | Histogram | `method`, `status` | Duration of HTTP request processing in seconds. |

### 5.1 Multi-Process / Architecture Note
- **PostgreSQL Gauges**: Global and authoritative across the entire cluster on every scrape.
- **HTTP Metrics**: Track the FastAPI container serving the scrape request.
- **Worker Process Counters**: Isolated to respective worker containers. For multi-process counter aggregation in production, an external sidecar/StatsD exporter or Prometheus multiprocess directory is recommended.

---

## 6. Environment Configuration Hardening

### 6.1 Development Mode (`ENVIRONMENT=development`)
- Safe local defaults are enabled for rapid onboarding (`guest:guest` for local RabbitMQ, local Postgres credentials).
- Keycloak JWT verification uses local realm discovery with in-process JWKS caching.

### 6.2 Production Mode (`ENVIRONMENT=production`)
- `ENVIRONMENT=production` activates strict validation at application boot:
  - `SECRET_KEY`: Must be at least 32 characters, trimmed of whitespace, high entropy (> 4 distinct characters), and contain no insecure placeholder markers.
  - `KEYCLOAK_CLIENT_SECRET`: Must be set to a cryptographically secure, non-placeholder value.
  - `RABBITMQ_URL`: Rejects default `guest:guest` credentials; dedicated credentials required.
  - Database and broker URLs must point to production instances.
- Violations cause immediate `ValidationError` on startup, preventing misconfigured deployments.
