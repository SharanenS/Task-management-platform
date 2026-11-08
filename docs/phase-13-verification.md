# Phase 13 verification — Observability + Security Hardening

Status: **Implemented; pending owner acceptance**

Baseline: Merge commit `4a3edcb` on `main`. Branch: `phase-13-observability-security`.
All unstaged changes remain preserved. No Git commits, branch modifications, or remote changes were made. Local-only files `.env` and `AGENTS.md` remain untracked and ignored. Phase 14 remains unstarted.

---

## 1. Implementation Boundary and Scope

### 1.1 In-Scope Deliverables
1. **Shared Structured Logging & Sanitization**:
   - Standardized JSON logging across Gateway, backend services, publishers, workers, and consumers.
   - Fields: `timestamp` (ISO 8601 UTC), `level`, `service`, `event` (fixed identifier), `correlation_id`, `trace_id`, `span_id`, `outcome` (`success`, `failure`, `rejected`), and sanitized failure classifications.
   - Strict redaction: Passwords, tokens, `Authorization`/`Cookie` headers, internal service keys, OIDC parameters, CSV contents, task/comment text, emails, employee names, and raw SQL parameters.
   - Correlation ID validation: Permitted characters `^[a-zA-Z0-9_\-]{1,64}$`; invalid or missing identifiers fall back to safe generated UUIDv4 to eliminate log injection.
2. **Distributed Context & W3C TraceContext Propagation**:
   - Inbound HTTP requests: Frontend `/graphql` server route passes/originates `x-correlation-id` and W3C `traceparent`.
   - Gateway middleware: Validates correlation ID, creates root span, propagates downstream via `httpx` headers.
   - Downstream service HTTP calls: `X-Correlation-ID` and `traceparent` headers forwarded.
   - Asynchronous job execution: Outbox events persist `correlation_id` and W3C `traceparent` in database; Celery worker consumes context and sets trace link.
   - Asynchronous domain events: Work `TASK_COMPLETED` and `TASK_ASSIGNED` outbox events persist `correlation_id` and `traceparent` in database; publisher extracts context into AMQP message headers; Workflow and Notification consumers extract context into consumer spans.
   - Workflow-generated jobs: Workflow executions persist `correlation_id` and `traceparent`; dispatching jobs passes headers to Job service `/internal/workflow/jobs`.
3. **OpenTelemetry Tracing**:
   - Standard W3C TraceContext (`traceparent`).
   - Bounded, asynchronous, non-blocking OTLP HTTP trace exporter targeting Jaeger (`http://jaeger:4318/v1/traces`).
   - Bounded in-memory span queue (maximum 1,000 spans), non-blocking worker thread, 1.5s export timeout, drop on full. Telemetry backend unavailability never blocks or degrades business processing.
   - Asynchronous spans: Celery execution spans link to dispatch spans; retries create independent attempt spans linked to the root trace.
4. **Prometheus Metrics**:
   - Internal `/metrics` endpoint on Gateway and backend services.
   - Dedicated token protection on host-accessible Gateway `/metrics`.
   - Explicit metrics:
     - `http_requests_total{service, method, handler, status}`
     - `http_request_duration_seconds{service, method, handler}`
     - `graphql_operations_total{operation_type, operation_category, status}` (bounded operation categories, e.g. `query_dashboard`, `query_projects`, `mutation_create_task`).
     - `dependency_up{service, dependency}` (1 for healthy, 0 for unavailable).
     - `job_executions_total{job_type, outcome}`
     - `job_attempts_total{job_type, outcome}`
     - `job_recovery_events_total{outcome}`
     - `events_published_total{service, event_type, status}`
     - `events_consumed_total{consumer, event_type, status}`
   - Cardinality controls: Disallowing dynamic IDs, usernames, email addresses, error messages, or raw query text in metric labels.
5. **Observability Infrastructure Deployment**:
   - **Jaeger** (`jaegertracing/all-in-one:1.64.0`): Bounded in-memory trace storage, loopback UI `127.0.0.1:16686:16686`, internal OTLP ingestion on 4317/4318.
   - **Prometheus** (`prom/prometheus:v3.2.1`): Loopback UI `127.0.0.1:9090:9090`, internal service scrapes of HTTP `/metrics` endpoints using `credentials_file: /etc/prometheus/gateway_token` mounted via Docker Compose secret.
   - **Grafana** (`grafana/grafana:11.5.2`): Loopback UI `127.0.0.1:3001:3000`, provisioned Prometheus & Jaeger datasources, provisioned Taskspace Operational Dashboard, anonymous access disabled (`GF_AUTH_ANONYMOUS_ENABLED: "false"`), credentials in local configuration (`.env`).
6. **ADMIN Operational Dashboard & GraphQL API**:
   - Screen: `/operations` route in protected Next.js shell with role-aware navigation item visible only to `ADMIN`.
   - GraphQL: Typed, bounded `operationsSummary: OperationsSummary!` query on Gateway.
   - Server-side derivation: Current Employee profile reloaded; non-ADMIN (`MEMBER`, `MANAGER`), inactive, or missing profiles rejected with `FORBIDDEN`.
   - Honest indicators: Explicit service health (`alive`, `ready`, `degraded`, `unavailable`), dependency state, freshness timestamps (ISO 8601 UTC), publication/worker/recovery counters where measured.
   - Truthful zero handling: "0" displayed only when source returns 0; unavailable dependencies show "Unavailable" with retry, not false zeros.
   - Links to local tools: Grafana (`http://127.0.0.1:3001`), Jaeger (`http://127.0.0.1:16686`), Prometheus (`http://127.0.0.1:9090`).
7. **Focused Security Hardening**:
   - Internal endpoint authentication: Verification of `X-Internal-Service-Key` across all internal routes.
   - Gateway `/metrics` protected with `GATEWAY_METRICS_TOKEN` via constant-time `hmac.compare_digest`.
   - Redaction filters: Scrubbing sensitive tokens, credentials, and personal data.
   - Correlation ID sanitization: Preventing log injection and header forgery.
   - Browser security headers & CSP: In Next.js server configuration, compatible with Keycloak OIDC redirects and CSV downloads.
   - GraphQL query complexity (`MaxAliasesLimiter(max_alias_count=10)`) and depth bounds (`QueryDepthLimiter(max_depth=4)`).
   - Host binding: Loopback `127.0.0.1` only for all host ports.

### 1.2 Deferred and Unobservable Boundaries
- No public REST business API: GraphQL remains the sole public business API.
- No SIEM or arbitrary user-defined query engine: No arbitrary PromQL or log query execution from web clients.
- Background worker metric collection: Background worker, publisher, and consumer processes (`job-worker`, `job-publisher`, `job-recovery`, `job-domain-publisher`, `work-event-publisher`, `workflow-consumer`, `notification-consumer`) run as non-HTTP CLI/worker processes. Because Prometheus scrapes via HTTP endpoints and Python process memories are isolated, in-memory metric increments in these workers are not scraped by Prometheus. Operational counts and queue observations are obtained directly via authoritative PostgreSQL queries and RabbitMQ passive queue inspect in the API services.
- Trace storage: Bounded local Jaeger in-memory buffer; long-term cold trace persistence is deferred.
- Transport security: Local stack uses loopback HTTP; production TLS termination is out of local development scope.

---

## 2. Instrumentation Coverage Matrix

| Service / Component | HTTP / Request Metrics | Domain & Asynchronous Metrics | Structured Logging Events | Tracing Spans & Propagation | Health Semantics |
|---|---|---|---|---|---|
| **Gateway** | `http_requests_total`, `http_request_duration_seconds`, `graphql_operations_total` | `dependency_up{dependency="employee\|work\|job\|workflow\|notification"}` | `http_request`, `graphql_operation`, `dependency_call`, `auth_verification` | Root span `GraphQL <Category>`, propagates `traceparent` & `x-correlation-id` downstream | Liveness: process alive; Readiness: downstream availability check |
| **Employee Service** | `http_requests_total`, `http_request_duration_seconds` | `dependency_up{dependency="postgres"}` | `http_request`, `profile_lookup`, `profile_provision`, `reconciliation` | Child span `employee_request`, inherits W3C context | Liveness: process alive; Readiness: DB `SELECT 1` |
| **Work Service** | `http_requests_total`, `http_request_duration_seconds` | `events_published_total{event="TASK_COMPLETED\|TASK_ASSIGNED"}` | `http_request`, `project_mutation`, `task_mutation`, `outbox_commit` | Child span `work_request`, inherits W3C context; persists `correlation_id` & `traceparent` in `work_outbox_events` | Liveness: process alive; Readiness: DB `SELECT 1` |
| **Work Event Publisher** | N/A (background process) | `events_published_total`, `publication_failures_total` | `publisher_poll`, `event_claimed`, `event_published`, `lease_settled` | Span `publish_work_event`, extracts persisted `traceparent` across restarts, injects AMQP headers | Liveness: process alive (`/proc/1`) |
| **Job Service** | `http_requests_total`, `http_request_duration_seconds` | `job_executions_total`, `job_attempts_total`, `dependency_up{dependency="postgres"}` | `http_request`, `job_submitted`, `job_dispatched`, `job_settled` | Child span `job_request`, inherits W3C context; persists context in `jobs`, `job_publication_outbox`, `job_domain_outbox` | Liveness: process alive; Readiness: DB `SELECT 1` |
| **Job Publisher** | N/A (background process) | `events_published_total{service="job"}`, `publication_failures_total` | `publisher_poll`, `publication_claimed`, `publication_published` | Span `publish_job_task`, extracts persisted `traceparent` across restarts, injects Celery headers | Liveness: DB check & process alive |
| **Job Worker (Celery)** | N/A (queue consumer) | `job_attempts_total`, `job_executions_total`, `worker_processing_seconds` | `worker_task_received`, `job_claimed`, `export_executed`, `job_settled` | Span `execute_job`, linked to dispatch trace; separate attempt spans | Liveness: Celery ping inspect pong |
| **Job Recovery** | N/A (background process) | `job_recovery_events_total` | `recovery_poll`, `attempt_recovered`, `attempt_abandoned` | Span `recover_expired_execution`, links to original attempt | Liveness: DB check & process alive |
| **Job Domain Publisher** | N/A (background process) | `events_published_total{event="REPORT_SUCCEEDED|REPORT_FAILED"}` | `domain_publisher_poll`, `domain_event_published` | Span `publish_job_domain_event`, extracts persisted context, injects AMQP headers | Liveness: process alive (`/proc/1`) |
| **Workflow Service** | `http_requests_total`, `http_request_duration_seconds` | `workflow_rules_total`, `dependency_up{dependency="postgres"}` | `http_request`, `rule_created`, `rule_updated`, `execution_created` | Child span `workflow_request`, inherits W3C context; persists context in `workflow_executions` | Liveness: process alive; Readiness: DB `SELECT 1` |
| **Workflow Consumer** | N/A (queue consumer) | `events_consumed_total{consumer="workflow"}`, `executions_triggered_total` | `event_received`, `inbox_persisted`, `rule_evaluated`, `action_dispatched` | Span `consume_work_event`, extracts AMQP headers, links to publisher trace | Liveness: process alive (`/proc/1`) |
| **Notification Service** | `http_requests_total`, `http_request_duration_seconds` | `notifications_created_total`, `dependency_up{dependency="postgres"}` | `http_request`, `notifications_listed`, `notification_marked_read` | Child span `notification_request`, inherits W3C context | Liveness: process alive; Readiness: DB `SELECT 1` |
| **Notification Consumer**| N/A (queue consumer) | `events_consumed_total{consumer="notification"}` | `event_received`, `inbox_persisted`, `notification_created` | Span `consume_notification_event`, extracts AMQP headers, links to publisher trace | Liveness: process alive (`/proc/1`) |
| **Frontend** | Client telemetry disabled | N/A | Server-side `/graphql` proxy log: `proxy_request`, `correlation_id`, `status`, `duration_ms` | Injects `x-correlation-id` and W3C `traceparent` headers to Gateway | Liveness: HTTP `/sign-in` 200 OK |

---

## 3. Telemetry Topology and Access Controls

```
               +-----------------------------------------------------------+
               |                  Browser (Local Host)                     |
               |  http://localhost:3010  (App Shell & /operations)         |
               |  http://127.0.0.1:3001  (Grafana Dashboards)             |
               |  http://127.0.0.1:16686 (Jaeger UI Traces)               |
               |  http://127.0.0.1:9090  (Prometheus UI)                  |
               +-----------------------------+-----------------------------+
                                             |
                  +--------------------------+--------------------------+
                  | Loopback (127.0.0.1 only)| Host Port Bindings       |
                  v                          v                          v
          +---------------+          +---------------+          +---------------+
          |    Grafana    |          |    Jaeger     |          |  Prometheus   |
          |  (Port 3001)  |          | (Port 16686)  |          |  (Port 9090)  |
          +-------+-------+          +-------^-------+          +-------^-------+
                  |                          |                          |
                  |                          | OTLP/HTTP                | Scrapes (Bearer
                  | (Queries metrics &       | (4318 internal)          |  credentials_file)
                  |  traces internally)      |                          |
                  |                          |                          |
+-----------------v--------------------------+--------------------------+-----------------+
| Docker Network (taskspace-internal)                                                     |
|                                                                                         |
|   Frontend (3000) ----> Gateway (8000)                                                  |
|                            |                                                            |
|          +-----------------+-----------------+-----------------+-----------------+      |
|          |                 |                 |                 |                 |      |
|          v                 v                 v                 v                 v      |
|    Employee (8020)    Work (8030)       Job (8040)      Workflow (8050) Notification    |
|       [DB: 5435]       [DB: 5436]       [DB: 5437]        [DB: 5438]       (8060)       |
|                            |                 |                 |         [DB: 5439]     |
|                            | (Outbox)        | (Celery/Outbox) | (AMQP)          |      |
|                            v                 v                 v                 v      |
|                     RabbitMQ (amqp://rabbitmq:5672) / Redis (session-store:6379)        |
+-----------------------------------------------------------------------------------------+
```

### 3.1 Loopback and Port Isolation
- All host port publications bind strictly to `127.0.0.1`:
  - Frontend: `127.0.0.1:3010:3000`
  - Gateway: `127.0.0.1:8010:8000`
  - Keycloak: `127.0.0.1:8080:8080`
  - Prometheus: `127.0.0.1:9090:9090`
  - Grafana: `127.0.0.1:3001:3000`
  - Jaeger UI: `127.0.0.1:16686:16686`
- Internal service ports (`8020`, `8030`, `8040`, `8050`, `8060`, `4317`, `4318`, `5432`, `5672`, `6379`) remain on the internal Compose network and are not exposed on host interfaces.

### 3.2 Authentication & Secret Isolation
- Grafana:
  - `GF_AUTH_ANONYMOUS_ENABLED=false`
  - `GF_SECURITY_ADMIN_USER=admin`
  - `GF_SECURITY_ADMIN_PASSWORD` read from `.env` (placeholder `GRAFANA_ADMIN_PASSWORD=` in `.env.example`).
  - No committed credentials or tokens.
- Internal Service Keys:
  - `X-Internal-Service-Key` enforced on all service `/internal/*` routes.
- Gateway Metrics Token:
  - `GATEWAY_METRICS_TOKEN` read from `.env` and mounted as a Compose secret to `/etc/prometheus/gateway_token`.
  - Prometheus scrapes using `credentials_file: /etc/prometheus/gateway_token`. Missing token halts Prometheus config validation.
- Operational GraphQL API:
  - `operationsSummary` query requires an authenticated active `ADMIN` role.
  - `MEMBER` and `MANAGER` roles receive `FORBIDDEN`.

---

## 4. Preflight Verification & Hardening Record

### 4.1 Dependency Security Audit & Triage
Audits were performed against actual committed lockfiles and configuration, separating container runtime dependencies from host/developer tooling:

1. **Python Service Lockfiles (`pip-audit 2.10.1`, Python 3.13.5)**:
   - `gateway/requirements.lock`: **0 known vulnerabilities found**. (Upgraded `graphql-core==3.3.1`).
   - `services/employee/requirements.lock`: **0 known vulnerabilities found**.
   - `services/work/requirements.lock`: **0 known vulnerabilities found**.
   - `services/job/requirements.lock`: **0 known vulnerabilities found**.
   - `services/workflow/requirements.lock`: **0 known vulnerabilities found**.
   - `services/notification/requirements.lock`: **0 known vulnerabilities found**.
2. **Frontend Runtime Dependencies (`npm 11.7.0`, Node v24.22.2)**:
   - `npm --prefix frontend audit --omit=dev`: **0 vulnerabilities found** across production runtime dependencies.
   - Full `npm audit`: 12 findings in `devDependencies` (10 moderate in `minimatch` via `@graphql-codegen/cli` and `eslint-config-next`; 2 high in `undici` and `zod` via `jsdom` and `eslint-plugin-react-hooks`). These packages are dev/test tooling on the host machine and are not bundled into the standalone production image.
3. **Container Image Versions**:
   - Prometheus: `prom/prometheus:v3.2.1` (pinned upstream release).
   - Grafana: `grafana/grafana:11.5.2` (pinned upstream release).
   - Jaeger: `jaegertracing/all-in-one:1.64.0` (pinned upstream release).
   - Removed unsupported "LTS/stable" labels; container versions are explicitly documented as pinned upstream releases.

### 4.2 Gateway `/metrics` Protection & Telemetry Boundaries
- **Threat Model**: Gateway port 8010 is published on host `127.0.0.1`. Sanitized content does not replace authorization.
- **Access Control**: `/metrics` enforces mandatory authentication via `GATEWAY_METRICS_TOKEN` (via `Authorization: Bearer <token>` or `X-Metrics-Token: <token>`) using constant-time comparison `hmac.compare_digest`.
- **Enforcement**:
   - Unauthorized requests receive `HTTP 401 Unauthorized` with `WWW-Authenticate: Bearer`.
   - Authorized requests with the dedicated scrape token receive `HTTP 200 OK` with Prometheus text exposition.
   - Verified deterministically in `gateway/tests/test_observability.py::test_http_observability_middleware_and_metrics`.
- **Prometheus Scrape Configuration**:
   - `infrastructure/prometheus/prometheus.yml` scrapes `gateway:8000/metrics` with `credentials_file: /etc/prometheus/gateway_token`.
   - `compose.yaml` mounts `GATEWAY_METRICS_TOKEN` via Docker Compose secrets without command-line exposure. Missing token causes Prometheus configuration validation to fail closed (`stat /etc/prometheus/gateway_token: no such file or directory`).
- **Local Telemetry Tool Boundaries**:
   - Prometheus (9090) and Jaeger (16686) UIs are bound to loopback `127.0.0.1` and are unauthenticated in this development environment. This tooling boundary is strictly separated from application ADMIN authorization enforced on `/operations` and `/graphql`.
   - Grafana (3001) has anonymous access disabled (`GF_AUTH_ANONYMOUS_ENABLED: "false"`) and requires credentials provided via local `.env`.

### 4.3 Durable HTTP-to-Outbox Continuity & Migration Proof
- **Forward-Only Database Migrations**:
   - `services/work/migrations/versions/20261108_03_outbox_trace_context.py`: Adds `correlation_id` (String(64), nullable=True) and `traceparent` (String(64), nullable=True) to `work_outbox_events`.
   - `services/job/migrations/versions/20261108_07_outbox_trace_context.py`: Adds `correlation_id` (String(64), nullable=True) and `traceparent` (String(64), nullable=True) to `jobs`, `job_publication_outbox`, and `job_domain_outbox`.
   - `services/workflow/migrations/versions/20261108_02_execution_trace_context.py`: Adds `correlation_id` (String(64), nullable=True) and `traceparent` (String(64), nullable=True) to `workflow_executions`.
- **Context Capture & Persistence**:
   - Work service captures inbound HTTP trace context and writes it transactionally with domain outbox events on task completion and task assignment.
   - Job service captures inbound HTTP trace context and writes it transactionally with job records and publication outbox events on job submission, retry, recovery, and domain reports.
   - Workflow service records inbound consumer trace context on workflow executions and passes `X-Correlation-ID` and `traceparent` downstream when dispatching jobs.
- **Trace Continuity Across Restarts**:
   - Outbox publishers (`work-event-publisher`, `job-publisher`, `job-domain-publisher`) extract persisted `traceparent` and start continuous child spans linked to the persisted trace ID, injecting continuous W3C headers into AMQP and Celery deliveries.
   - Contextless legacy events safely start honest root spans.
   - Verified deterministically in `services/work/tests/test_event_publisher.py` and `services/job/tests/test_domain_events.py`.
- **Isolated PostgreSQL Migration Verification**:
   - Executed against temporary isolated PostgreSQL databases without touching retained development databases:
     - Work (`20261029_02` -> `20261108_03`): Zero-to-Head passed; repeated head idempotent; upgrade from previous head passed; transactional persistence verified.
     - Job (`20261029_06` -> `20261108_07`): Zero-to-Head passed; repeated head idempotent; upgrade from previous head passed; transactional persistence verified across `jobs`, `job_publication_outbox`, and `job_domain_outbox`.
     - Workflow (`20261028_01` -> `20261108_02`): Zero-to-Head passed; repeated head idempotent; upgrade from previous head passed; transactional persistence verified on `workflow_executions`.
   - Confirmed retained development databases remain untouched at heads `20261029_02` (Work), `20261029_06` (Job), and `20261028_01` (Workflow).

### 4.4 Data Ownership & Service Encapsulation
- The operations dashboard obtains database-derived summaries strictly through authenticated owning-service HTTP REST endpoints:
  - `http://work:8030/internal/operations/summary` (Work service queries its own `work-db` for outbox stats; returns `WorkOutboxSummaryResponse`)
  - `http://job:8040/internal/operations/summary` (Job service queries its own `job-db` for job status breakdowns and RabbitMQ for queue stats; returns `JobOperationsSummaryResponse`)
  - `http://employee:8020/internal/operations/summary`
  - `http://workflow:8050/internal/operations/summary`
  - `http://notification:8060/internal/operations/summary`
  - `http://<service>:80XX/health/live` and `/health/ready`
- All inter-service calls require and enforce `X-Internal-Service-Key` with 403 rejection on unauthenticated calls (verified by tests in `services/work/tests/test_work.py` and `services/job/tests/test_api.py`).
- Gateway possesses zero direct database connections, drivers, connection pools, or credentials to `work-db` (5436) or `job-db` (5437). Service encapsulation and database ownership are strictly maintained.

### 4.5 GraphQL Query Depth & Complexity Protections
- **Empirical Depth Validation Against Strawberry Runtime Engine**:
  - Every operation across all 10 GraphQL query files in `frontend/src/graphql/operations/` was empirically evaluated against the actual runtime Strawberry schema using `QueryDepthLimiter(max_depth=4).create_validator()`:
    - `dashboard.graphql`: `Dashboard` (depth 2)
    - `employees.graphql`: `EmployeeDirectory` (depth 2), `EmployeeDetail` (depth 1), mutations (depth 1)
    - `jobs.graphql`: `Jobs` (depth 3), `JobDetail` (depth 2), `JobPublications` (depth 2), mutations (depth 1-2)
    - `notifications.graphql`: `Notifications` (depth 2), `UnreadNotificationCount` (depth 0), mutations (depth 1)
    - `operations.graphql`: `OperationsSummary` (depth 3)
    - `projects.graphql`: `ProjectDirectory` (depth 3), `ProjectDetail` (depth 2), `EligibleProjectMembers` (depth 2), mutations (depth 1-2)
    - `reports.graphql`: `Reports` (depth 3), `Report` (depth 2), `ReportArtifact` (depth 1), mutations (depth 1)
    - `system-info.graphql`: `SystemInfo` (depth 1)
    - `tasks.graphql`: `ProjectTaskBoard` (depth 3), `ProjectTasks` (depth 2), `TaskDetail` (depth 2), mutations (depth 1)
    - `workflows.graphql`: `WorkflowRules` (depth 2), `WorkflowRule` (depth 2), mutations (depth 1)
  - Every legitimate query succeeds with 0 errors and depth <= 3.
  - Fragment spreads were explicitly validated: legitimate fragment spreads calculate correct cumulative depth; cyclic/deep fragment trees exceeding depth 4 are strictly rejected with `"exceeds maximum operation depth of 4"`. Tested and verified in `gateway/tests/test_observability.py::test_query_depth_limiter`.
- **Query Complexity & Alias Limits**:
  - `MaxAliasesLimiter(max_alias_count=10)` configured on schema; 11+ aliases are rejected (verified in `gateway/tests/test_gateway.py::test_alias_abuse_is_rejected`).
  - GET queries disabled; only POST with bounded payload processed.

### 4.6 Automated Test Suite Accounting
- Unit & Component Test Results:
  - `services/employee`: 40/40 passed (0 failures).
  - `services/work`: 61/61 unit tests passed (13 PostgreSQL integration tests separated into the dedicated isolated database gate below).
  - `services/job`: 69/69 unit tests passed (22 PostgreSQL integration tests separated into the dedicated isolated database gate below).
  - `services/workflow`: 10/10 unit tests passed (3 PostgreSQL integration tests separated into the dedicated isolated database gate below).
  - `services/notification`: 23/23 unit tests passed (5 PostgreSQL integration tests separated into the dedicated isolated database gate below).
  - `gateway`: 138/138 passed (0 failures).
  - `frontend`: 15 test files / 75 tests passed (0 failures); `tests/operations.test.tsx` 4 passed.
  - `frontend build`: Next.js production build (`next build`) compiled successfully with all 26 static/dynamic routes.
- Note on Evidence Separation: Browser acceptance tests and migration upgrade tests provide distinct runtime and schema evidence; they do not substitute for the deterministic PostgreSQL suites below.

---

## 5. Deployment Execution and Runtime Acceptance Results

### 5.1 14-Process Image Build
All 14 affected application process images were built cleanly via `docker compose build`:
`employee`, `work`, `work-event-publisher`, `job`, `job-publisher`, `job-worker`, `job-recovery`, `job-domain-publisher`, `workflow`, `workflow-consumer`, `notification`, `notification-consumer`, `gateway`, `frontend`.
All builds completed with exit code 0. No process image was left stale.

### 5.2 Ordered Additive Database Migrations on Retained Databases
Approved forward-only Alembic migrations executed against retained application databases in strict sequence:
1. **Work Database** (`work` service): `20261029_02` -> `20261108_03` (adds `correlation_id` and `traceparent` to `work_outbox_events`). Upgrade succeeded; head verified `20261108_03`.
2. **Job Database** (`job` service): `20261029_06` -> `20261108_07` (adds `correlation_id` and `traceparent` to `jobs`, `job_publication_outbox`, and `job_domain_outbox`). Upgrade succeeded; head verified `20261108_07`.
3. **Workflow Database** (`workflow` service): `20261028_01` -> `20261108_02` (adds `correlation_id` and `traceparent` to `workflow_executions`). Upgrade succeeded; head verified `20261108_02`.
Confirmed: Existing rows preserved; newly added columns nullable; zero destructive drops; zero rollback/downgrades executed.

### 5.3 Scoped `--no-deps --force-recreate` Service Recreation
Executed `docker compose up -d --no-deps --force-recreate --wait` for all 17 application and telemetry services:
`employee`, `work`, `work-event-publisher`, `job`, `job-publisher`, `job-worker`, `job-recovery`, `job-domain-publisher`, `workflow`, `workflow-consumer`, `notification`, `notification-consumer`, `gateway`, `jaeger`, `prometheus`, `grafana`, `frontend`.
Retained infrastructure (`keycloak-db`, `employee-db`, `work-db`, `job-db`, `workflow-db`, `notification-db`, `session-store`, `rabbitmq`, `keycloak`) remained completely untouched with zero downtime.
Post-recreation health check: **All 26 Compose services healthy and running.**

### 5.4 Telemetry Scrape & Tooling Boundary Verification
- **Unauthorized Gateway `/metrics`**: `curl.exe -i http://127.0.0.1:8010/metrics` returned `HTTP/1.1 401 Unauthorized` with `WWW-Authenticate: Bearer` and sanitized response body `{"detail":"Unauthorized metrics access"}`.
- **Authorized Gateway `/metrics` Scrape**: Authenticated request with `Authorization: Bearer <GATEWAY_METRICS_TOKEN>` returned `HTTP/1.1 200 OK` with sanitized Prometheus metric exposition.
- **Prometheus Target Status**: Query to `http://127.0.0.1:9090/api/v1/targets` verified all 6 scrape targets (`employee:8020`, `work:8030`, `job:8040`, `workflow:8050`, `notification:8060`, `gateway:8000`) in state `health: "up"` with `lastError: ""` (Gateway scraped via mounted `gateway_token` secret).
- **Jaeger Health & Traces**: Responding on `http://127.0.0.1:16686/` (HTTP 200); registered services actively exporting spans include `jaeger-all-in-one`, `gateway`, `employee`, `work`, `job`, `workflow`, `notification`.
- **Grafana Health & Dashboards**: Responding on `http://127.0.0.1:3001/` (HTTP 200); datasources (`Prometheus`, `Jaeger`) and dashboard `TaskSpace Platform Overview` automatically provisioned and accessible.

### 5.5 Comprehensive End-to-End Acceptance Journey (`operations-acceptance.spec.ts`)
- **Runner**: Playwright desktop project, single worker, zero retries:
  `npx playwright test tests/e2e/operations-acceptance.spec.ts --project=desktop --workers=1 --retries=0`
- **Execution & Invariants Verified**:
  1. *Unauthenticated & Direct GraphQL Rejection*: Anonymous navigation to `/operations` immediately redirected to `/session-expired`; direct anonymous GraphQL query `operationsSummary` rejected with GraphQL errors.
  2. *MEMBER & MANAGER Direct GraphQL Denial*: Disposable `MEMBER` and `MANAGER` authenticated; verified sidebar link absent; direct page navigation redirected to `/access-denied`; direct GraphQL query `operationsSummary` denied with `"Administrator access is required."`.
  3. *ADMIN Operations Dashboard*: Admin authenticated; verified `/operations` link visible and navigable; verified page heading, freshness timestamp (`Updated HH:MM:SS`), and status badges. Direct GraphQL query `operationsSummary` succeeds returning `overallStatus: "HEALTHY"` and all service states.
  4. *Service Health Matrix*: Gateway, Work Service, Job Service, Employee Service, Workflow Service, Notification Service verified healthy with underlying dependency latencies.
  5. *Job Operations Diagnostics*: Oldest pending job age and 24h failure counts truthfully rendered.
  6. *Queues & Outbox Observations & Truthful Nulls*: Queues table rendered with live counts for `job.execution` and `work.outbox.events`. Table cleanly distinguishes `Broker Queue` from `Database Outbox`. The non-existent broker queue `celery` fails passive declaration and truthfully renders as an amber `Unavailable` badge rather than a false zero count.
  7. *Local Tooling Links*: Grafana (`:3001`), Jaeger (`:16686`), and Prometheus (`:9090`) links verified with mandatory `target="_blank"` and `rel="noopener noreferrer"`.
  8. *Interactive Refresh*: Verified operational refresh action re-fetches without regression.
  9. *Multi-Viewport Responsiveness*: Tested desktop (1280x800), tablet (768x1024), and mobile (390x844); zero horizontal document overflow detected across all viewports.
  10. *Real Asynchronous Distributed Trace Journey*:
      - Request report export through `/reports` UI.
      - Await publication outbox settlement in `job_publication_outbox` (`PUBLISHED`).
      - Await Celery worker execution attempt in `job_attempts` (1 attempt).
      - Await Job completion in `jobs` (`SUCCEEDED`).
      - Await terminal domain event outbox publication in `job_domain_outbox` (`PUBLISHED`).
      - Await Notification consumer materialization in `notifications` (1 notification).
      - Verify persisted W3C context in `jobs` (`traceparent` matching `00-[0-9a-f]{32}-[0-9a-f]{16}-01` and validated `correlation_id`).
      - Query Jaeger API (`http://127.0.0.1:16686/api/traces/<trace_id>`).
      - Verified 5+ spans sharing the exact same root `traceID`:
        - `publish_job_task`
        - `job_execution`
        - `publish_job_domain_event`
        - `notification_consume_event`
      - Verified parent-child references:
        - `job_execution` is `CHILD_OF` `publish_job_task`
        - `publish_job_domain_event` is `CHILD_OF` `job_execution`
        - `notification_consume_event` is `CHILD_OF` `publish_job_domain_event`
  11. *CSV Download & CSP Compatibility*: Navigated to `/reports/[id]`, executed real CSV download via browser download handler, verified CSV filename and content, and monitored browser console throughout: **0 CSP console violations detected**.
- **Result**: `1 passed (1.0m)`, exit code 0.

### 5.6 Isolation and Cleanup
- **Primary Administrator**: Preserved in Keycloak and `employee-db` (`local.user`, role `ADMIN`, `active=True`, `provisioning_status='COMPLETE'`).
- **Disposable Identities**: Cleaned up from Keycloak and PostgreSQL database (`SELECT username FROM employees WHERE username LIKE 'P13-%'` returned 0).
- **Run Fixtures**: Cleaned up from `jobs`, `job_publication_outbox`, `job_domain_outbox`, `notifications`, `notification_inbox`, `projects`, and `tasks`. Exact removal verified via `assertOwnedRowsRemoved`.
- **Docker Resources**: Zero orphaned or exited application containers created (`assertNoOneOffContainers` and `docker ps -a` check).
- **Git State**: All changes remain strictly unstaged (`git diff --cached` is empty). Phase 14 remains unstarted.

### 5.7 Isolated PostgreSQL Regression Suites
In accordance with repository standards, the complete PostgreSQL integration suites for all four stateful domain services were executed against dedicated, isolated temporary databases with their current migrations applied. Retained development databases were never touched.

1. **Work PostgreSQL Suite (`services/work/tests/test_postgres.py`)**:
   - Target database: `work_test_p13_regression` on `work-db` (port 5436).
   - Migration: Clean upgrade from zero to current head `20261108_03` via Alembic.
   - Command: `WORK_POSTGRES_TEST_URL="postgresql+psycopg://work:***@127.0.0.1:5436/work_test_p13_regression" pytest services/work/tests/test_postgres.py -v`
   - Result: **13 passed, 0 failed in 4.17s**.
   - Verified: Concurrent duplicate membership conflicts; project lock serializing final manager removals; concurrent task number allocations; task optimistic lock conflict rejection; assignment/removal race prevention; concurrent task completion outbox atomicity; disjoint ordered batch publisher claims; expired lease reclaim with exact token fencing; completion and assignment rollback integrity; dashboard overdue date boundary logic; O(1) dashboard SQL statement invariance (6 queries); and revocation isolation with manager authority reduction.
   - Cleanup: Database dropped cleanly via `DROP DATABASE work_test_p13_regression;`; verified absent with `SELECT 1 FROM pg_database WHERE datname='work_test_p13_regression'` returning 0 rows.
2. **Job PostgreSQL Suite (`services/job/tests/test_postgres.py`)**:
   - Target database: `job_test_p13_regression` on `job-db` (port 5437).
   - Migration: Clean upgrade from zero to current head `20261108_07` via Alembic.
   - Command: `JOB_POSTGRES_TEST_URL="postgresql+psycopg://job:***@127.0.0.1:5437/job_test_p13_regression" pytest services/job/tests/test_postgres.py -v`
   - Result: **22 passed, 0 failed in 5.22s**.
   - Verified: Concurrent identical submission single-job guarantee; idempotency collision winner/conflict resolution; cross-actor idempotency key reuse; persistence across engine disconnects; concurrent dispatch winner guarantee; dispatch/publication outbox atomicity; duplicate batch claim partitioning; lease reclaim and token-bound settlement; classified publisher failure scheduling and recovery; duplicate delivery idempotency; retry status persistence; multi-process recovery single-claim fencing; stale settlement fencing against recovered generations; concurrent admin retry single-generation guarantee; atomic report terminal state and domain event commit; domain event uniqueness rollback; domain event cascade deletion; submitter ownership metrics; and O(1) query count invariance (3 queries).
   - Cleanup: Database dropped cleanly via `DROP DATABASE job_test_p13_regression;`; verified absent with `SELECT 1 FROM pg_database WHERE datname='job_test_p13_regression'` returning 0 rows.
3. **Workflow PostgreSQL Suite (`services/workflow/tests/test_postgres.py`)**:
   - Target database: `workflow_test_p13_regression` on `workflow-db` (port 5438).
   - Migration: Clean upgrade from zero to current head `20261108_02` via Alembic.
   - Command: `WORKFLOW_POSTGRES_TEST_URL="postgresql+psycopg://workflow:***@127.0.0.1:5438/workflow_test_p13_regression" pytest services/workflow/tests/test_postgres.py -v`
   - Result: **3 passed, 0 failed in 1.46s**.
   - Verified: Concurrent duplicate event idempotency (single source event and single execution); crash recovery after job acceptance reusing key to settle original job; rule deletion cascade isolation preserving source events and other rules.
   - Cleanup: Database dropped cleanly via `DROP DATABASE workflow_test_p13_regression;`; verified absent with `SELECT 1 FROM pg_database WHERE datname='workflow_test_p13_regression'` returning 0 rows.
4. **Notification PostgreSQL Suite (`services/notification/tests/test_postgres.py`)**:
   - Target database: `notification_test_p13_regression` on `notification-db` (port 5439).
   - Migration: Clean upgrade from zero to current head `20261029_02` via Alembic.
   - Command: `NOTIFICATION_POSTGRES_TEST_URL="postgresql+psycopg://notification:***@127.0.0.1:5439/notification_test_p13_regression" pytest services/notification/tests/test_postgres.py -v`
   - Result: **5 passed, 0 failed in 1.43s**.
   - Verified: Recipient cursor forward pagination, unread counts, and concealed foreign notifications; concurrent duplicate delivery resolving to single logical notification; transactional rollback and source cascade integrity; single notification per source event constraint; malformed/unsupported event quarantine without unverified payload persistence.
   - Cleanup: Database dropped cleanly via `DROP DATABASE notification_test_p13_regression;`; verified absent with `SELECT 1 FROM pg_database WHERE datname='notification_test_p13_regression'` returning 0 rows.

**PostgreSQL Regression Summary**: **43 passed, 0 failed across all 4 services**. Zero temporary databases remain on any database server; all permanent development databases remained untouched.

### 5.8 Static Analysis, Formatting, and Lint Verification
- **Frontend Code Formatting (Prettier)**:
  - Command: `npm --prefix frontend run format:check`
  - Result: **All matched files use Prettier code style!** (5 files formatted: `src/components/ui/badge.tsx`, `src/features/operations/operations-panel.tsx`, `src/graphql/operations/operations.graphql`, `tests/e2e/operations-acceptance.spec.ts`, and `tests/operations.test.tsx`).
- **Frontend Linting (ESLint)**:
  - Command: `npm --prefix frontend run lint`
  - Result: **0 problems (0 errors, 0 warnings)**.
  - Correction: In `tests/e2e/operations-acceptance.spec.ts`, removed the redundant unused binding `persistedCorrelationId` from line 419 while preserving the explicit line 418 regex `expect(traceMeta).toMatch(/^00-[0-9a-f]{32}-[0-9a-f]{16}-01\|.+$/)` asserting the durable presence of both the W3C traceparent and non-empty correlation ID. No executable assertion was removed or weakened.
- **Frontend Type Checking (TypeScript)**:
  - Command: `npm --prefix frontend run typecheck`
  - Result: **0 errors** (`tsc --noEmit`).
- **Python Linting & Formatting (Ruff)**:
  - Commands: `ruff check gateway/ services/` and `ruff format --check gateway/ services/`
  - Result: **All checks passed! 126 files already formatted.**
- **Python Static Type Checking (MyPy)**:
  - Command: Strict MyPy across all 6 service apps (`gateway`, `services/work`, `services/job`, `services/workflow`, `services/notification`, `services/employee`).
  - Result: **Success: no issues found across all source files.**

### 5.9 Review and Classification of Python Edits from Static Analysis Corrections
The Python edits made during the latest Ruff/MyPy pass were reviewed and compared against the code deployed and verified during the passing runtime acceptance run:

| File | Change Description | Classification | Executable / Persistence Impact |
|---|---|---|---|
| `gateway/app/operations_client.py` | Replaced multi-variable tuple unpack on `asyncio.gather` with explicit index access using `typing.cast(...)` (`results[0]` to `results[7]`) for MyPy type narrowing; sorted imports. | **Type-only / Formatting** | **None.** At runtime, `cast` is an identity no-op. Indexing extracts identical objects in identical order. |
| `gateway/app/observability.py` | Added `val_dict: dict[str, Any]` annotation in `to_otlp_dict()`; added defensive `if not self.endpoint: return` before HTTP export request in `_flush_batch()`. | **Executable Defensive & Type-only** | **Executable defensive change on missing-endpoint path.** Bypasses HTTP export when `self.endpoint` is unset or empty. Persistence is unaffected. |
| `services/employee/app/observability.py` | Added `val_dict: dict[str, Any]` annotation; added defensive `if not self.endpoint: return`. | **Executable Defensive & Type-only** | **Executable defensive change on missing-endpoint path.** Identical to Gateway observability change. |
| `services/work/app/observability.py` | Added `val_dict: dict[str, Any]` annotation; added defensive `if not self.endpoint: return`. | **Executable Defensive & Type-only** | **Executable defensive change on missing-endpoint path.** Identical to Gateway observability change. |
| `services/job/app/observability.py` | Added `val_dict: dict[str, Any]` annotation; added defensive `if not self.endpoint: return`. | **Executable Defensive & Type-only** | **Executable defensive change on missing-endpoint path.** Identical to Gateway observability change. |
| `services/workflow/app/observability.py` | Added `val_dict: dict[str, Any]` annotation; added defensive `if not self.endpoint: return`. | **Executable Defensive & Type-only** | **Executable defensive change on missing-endpoint path.** Identical to Gateway observability change. |
| `services/notification/app/observability.py` | Added `val_dict: dict[str, Any]` annotation; added defensive `if not self.endpoint: return`. | **Executable Defensive & Type-only** | **Executable defensive change on missing-endpoint path.** Identical to Gateway observability change. |
| `services/work/app/service.py` | Refactored `_current_trace_metadata()` to use single ternary `valid_tp: str | None = tp if (tp and parse_traceparent(tp)) else None` instead of mutating `tp = None`. | **Type-only Refactor** | **None.** Boolean logic and return values are strictly identical for all inputs. |
| `services/job/app/service.py` | Refactored `_current_trace_metadata()` to use single ternary assignment; sorted imports. | **Type-only Refactor** | **None.** Boolean logic and return values are strictly identical for all inputs. |
| `services/workflow/app/service.py` | Refactored `_current_trace_metadata()` to use single ternary assignment. | **Type-only Refactor** | **None.** Boolean logic and return values are strictly identical for all inputs. |
| `services/job/app/publisher.py` | Removed unused import `get_tracing_headers`. | **Dead-code Removal** | **None.** Unused import removed; publisher execution unchanged. |
| `services/job/app/publisher_process.py` | Changed parameter type `adapter: object` to `adapter: Any` in `publish_batch`; removed unused `# type: ignore[attr-defined]` comments; sorted imports. | **Type-only / Formatting** | **None.** Python function argument annotations have zero runtime effect. |
| `services/job/migrations/versions/20261108_07_outbox_trace_context.py` | Wrapped long line to satisfy 100-character line length limit; removed trailing newline. | **Formatting-only** | **None.** DDL statements and migration schema logic are unchanged. |
| `services/work/migrations/versions/20261108_03_outbox_trace_context.py` | Removed trailing newline. | **Formatting-only** | **None.** Unchanged. |
| `services/workflow/migrations/versions/20261108_02_execution_trace_context.py` | Removed trailing newline. | **Formatting-only** | **None.** Unchanged. |
| `gateway/tests/test_observability.py` | Reordered import block in `test_query_depth_limiter`. | **Formatting-only** | **None.** Unchanged. |
| `services/job/tests/test_api.py` | Trimmed trailing whitespace. | **Formatting-only** | **None.** Unchanged. |
| `services/job/tests/test_domain_events.py` | Trimmed trailing whitespace. | **Formatting-only** | **None.** Unchanged. |
| `services/work/tests/test_event_publisher.py` | Trimmed trailing whitespace. | **Formatting-only** | **None.** Unchanged. |
| `services/notification/tests/test_consumer.py` | Wrapped long function signature and replaced `setattr(msg, "headers", ...)` with direct `msg.headers = ...`. | **Formatting / Idiomatic** | **None.** Identical attribute assignment on mock object. |

**Runtime and Verification Sequence**:
- The successful configured-endpoint runtime acceptance run (Section 5.3 through 5.7) predates the addition of these defensive guards and type annotations.
- In that runtime acceptance run, all services operated with `OTEL_EXPORTER_OTLP_ENDPOINT` populated (`http://jaeger:4318/v1/traces`), exercising the configured-endpoint export path.
- The added `if not self.endpoint: return` guards introduce an executable defensive early exit strictly for the missing-endpoint fallback path, preventing unconfigured HTTP dispatches when no OTLP collector is provided.
- After these edits were made, the complete affected unit test suites across the Gateway and backend services were rerun and verified clean (341 tests passing).
- No runtime rerun occurred after these static analysis corrections, and no container images were rebuilt or recreated.
- Persistence semantics, database outbox schemas, SQL queries, and transactional boundaries remain completely untouched; therefore, isolated PostgreSQL integration suite reruns were not required.

**Post-Correction Suite Verification**:
- Gateway unit tests: **138 passed, 0 failed in 14.84s**
- Employee Service unit tests: **40 passed, 0 failed in 2.85s**
- Work Service unit tests: **61 passed, 0 failed in 7.63s** (13 PostgreSQL tests skipped in SQLite mode)
- Job Service unit tests: **69 passed, 0 failed in 47.90s** (22 PostgreSQL tests skipped in SQLite mode)
- Workflow Service unit tests: **10 passed, 0 failed in 1.25s** (3 PostgreSQL tests skipped in SQLite mode)
- Notification Service unit tests: **23 passed, 0 failed in 30.90s** (5 PostgreSQL tests skipped in SQLite mode)
- Total post-correction unit suite pass: **341 passed, 0 failed**.
- Structural & Configuration checks: `git diff --check` passed with 0 errors; `docker compose config --quiet` passed with exit code 0.

---

## 6. Requirement-to-Evidence Matrix & Residual Limitations

| Gap Requirement | Verification Method & Test File | Observed Result | Status |
|---|---|---|---|
| **1. Real Asynchronous Trace Journey** | Live end-to-end acceptance run in `frontend/tests/e2e/operations-acceptance.spec.ts` querying Jaeger API `http://127.0.0.1:16686/api/traces/<trace_id>` | 5+ exported spans verified across GraphQL request, Job publication outbox, Celery worker execution, Job terminal domain publication outbox, and Notification consumption. Correct `CHILD_OF` span parentage and W3C context inheritance confirmed without fabricated context. | **PASS** |
| **2. Authorization Enforcement** | Playwright test `frontend/tests/e2e/operations-acceptance.spec.ts` & unit test `gateway/tests/test_observability.py::test_operations_summary_authorization` | Direct `operationsSummary` GraphQL queries rejected for unauthenticated, `MEMBER`, and `MANAGER` with `"Administrator access is required."`. Inactive and missing employee profiles fail closed with `FORBIDDEN` and `SERVICE_UNAVAILABLE`. `ADMIN` succeeds. | **PASS** |
| **3. Operational Data Truthfulness** | UI assertions in `operations-acceptance.spec.ts`, schema tests in `gateway/tests/test_observability.py`, unit test in `frontend/tests/operations.test.tsx`, and Grafana `/api/ds/query` checks | Outbox database state (`work.outbox.events`) labeled `Database Outbox`; broker queues labeled `Broker Queue`. Non-existent queue `celery` passive declaration failure returns `null` count and renders as amber `Unavailable` badge rather than false zero. Grafana panels return real series frames via `uid: prometheus`. | **PASS** |
| **4. CSP Regression** | Full browser console listener in `frontend/tests/e2e/operations-acceptance.spec.ts` across login, logout, session refresh, and real CSV download | Zero Content Security Policy violations detected across all phases. CSV download successfully triggered via browser click and completed with `.csv` filename. | **PASS** |
| **5. Failure Isolation** | Deterministic unit tests in `gateway/tests/test_observability.py`, `services/job/tests/test_domain_events.py`, `services/job/tests/test_execution.py`, and `services/notification/tests/test_consumer.py` | Business requests, outbox event publication, Celery worker settlement, and consumer message acknowledgement all succeed uninterrupted even when the OTLP trace exporter is non-responsive or failing. | **PASS** |
| **6. Complete Regression & Cleanup** | Complete backend test suites (Gateway 138, Employee 40, Work 61 unit + 13 PG, Job 69 unit + 22 PG, Workflow 10 unit + 3 PG, Notification 23 unit + 5 PG), frontend unit tests (4), Next.js production build (`next build`), and `assertOwnedRowsRemoved` | All suites passed with 0 failures; all 43 PostgreSQL integration tests passed against isolated temporary databases and dropped cleanly; production build succeeded; all test fixtures deleted; primary admin verified intact; 0 one-off containers; all 26 Compose services healthy. | **PASS** |

### Residual Limitations
1. **Background Worker Prometheus Scraping**: Background publisher, worker, and consumer processes (`job-worker`, `job-publisher`, `job-recovery`, `job-domain-publisher`, `work-event-publisher`, `workflow-consumer`, `notification-consumer`) do not expose dedicated HTTP metrics scrape ports; their operational health and metrics are observed through authoritative PostgreSQL status queries and RabbitMQ broker queue telemetry in the API services.
2. **Local Loopback Telemetry Storage**: Jaeger runs in-memory (`jaegertracing/all-in-one:1.64.0`) with bounded capacity; long-term cold trace persistence is deferred.
3. **Local Loopback UI Tooling Boundary**: Prometheus and Jaeger local web interfaces bound to loopback `127.0.0.1` are unauthenticated developer tooling, separated from the application ADMIN-only GraphQL operational dashboard. Grafana is credentialed with local `.env` configuration.
