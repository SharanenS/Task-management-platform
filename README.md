# Enterprise Task Processing & Workflow Management System

> **Status:** Phase 1 of 15 complete — development infrastructure only. No business
> features (auth, projects, tasks, jobs) exist yet. See [Roadmap](#roadmap).

## Overview

A production-style enterprise platform combining project management, team
management, task management, and an asynchronous background job processing
engine. Built as a modular monolith with clear seams for extracting services
later, rather than a simple CRUD demo.

## Problem Statement

Most portfolio projects stop at CRUD over a single table. This project
instead demonstrates the parts of backend engineering that actually show up
in production systems: durable job queues, retry/failure handling, role-based
access control, audit logging, and operational observability — backed by a
real relational schema with proper migrations, not a NoSQL document dump.

## Architecture

Modular monolith, Maven multi-module:

```
enterprise-task-platform/
├── Frontend/                        (added in Phase 9 onward)
├── Backend/                         Java multi-module backend
│   ├── pom.xml                      parent POM (dependency management)
│   ├── common-core/                 shared constants/utilities, no Spring dependency
│   ├── api-server/                  REST API, persistence, (later) auth & business logic
│   └── job-worker/                  (added in Phase 6/7) consumes the Redis job queue
├── docker-compose.yml               local Postgres + Redis
├── .env.example                     documented environment variables
└── README.md
```

Modules are structured so any of them could later be extracted into an
independently deployable service without a rewrite — but we are **not**
building microservices prematurely. `job-worker` doesn't exist yet because
there's nothing for it to do until the job queue (Phase 6) exists.

Conceptual job flow (implemented starting Phase 5+):

```
Client → REST API → Create Job → PostgreSQL → Redis Queue → Worker
                                                                 ↓
                                          PostgreSQL ← Update status
```

## Technology Stack

**Backend:** Java 21, Spring Boot 3.5.16, Maven, Spring Web, Spring Data JPA,
Hibernate, PostgreSQL, Redis, Flyway, Bean Validation, Lombok, JUnit 5,
Mockito, Testcontainers, Spring Boot Actuator.

**Frontend (from Phase 9 onward):** React, TypeScript, Vite, React Router,
TanStack Query, Axios.

**Infrastructure:** Docker, Docker Compose.

> Spring Boot 3.5.16 is the final patch of the 3.x line (OSS support ended
> June 30, 2026). It was chosen deliberately over the current 4.1.x line to
> keep the dependency surface exactly as originally scoped. This tradeoff —
> and the plan (if any) to migrate — is worth calling out explicitly in an
> interview.

## Project Structure

```
enterprise-task-platform/
├── docker-compose.yml               local Postgres + Redis
├── .env.example                     documented environment variables
├── Frontend/                        (future)
├── Backend/
│   ├── pom.xml                      parent POM (dependency management)
│   ├── common-core/
│   │   ├── pom.xml
│   │   └── src/main/java/com/taskplatform/common/
│   ├── api-server/
│   │   ├── pom.xml
│   │   └── src/main/java/com/taskplatform/apiserver/
│   │   └── src/main/resources/
│   │       ├── application.yml          profile-agnostic config
│   │       ├── application-dev.yml      local dev connection settings
│   │       └── db/migration/            Flyway migrations
│   │   └── src/test/java/...            Testcontainers integration tests
│   └── job-worker/
│       ├── pom.xml
│       └── src/main/java/com/taskplatform/jobworker/
└── README.md
```

## Local Setup

### Prerequisites

- Java 21 (JDK)
- Maven 3.9+
- Docker + Docker Compose

### 1. Clone and configure environment

```bash
git clone <your-repo-url>
cd enterprise-task-platform
cp .env.example .env
# edit .env if you want non-default credentials or ports
```

### 2. Start Postgres and Redis

```bash
docker compose up -d
docker compose ps
```

This project's Postgres runs on **host port 5433** (not 5432) specifically
so it never conflicts with another Postgres installation you may already
have running locally. Redis runs on the standard 6379 — if that's already
taken on your machine, set `REDIS_PORT` in `.env` to something else before
starting the stack.

Verify both containers are healthy:

```bash
docker exec taskplatform-postgres pg_isready -U taskplatform_user -d taskplatform
docker exec taskplatform-redis redis-cli ping
```

### 3. Build the project

```bash
cd Backend
mvn clean install
cd ..
```

### 4. Run the tests

```bash
cd Backend
mvn test
cd ..
```

The integration test in `api-server` uses **Testcontainers** to spin up its
own throwaway Postgres and Redis containers — it does not depend on the
`docker compose` stack from step 2, and is safe to run in CI. Docker must be
running for this test to execute.

### 5. Start the API server

```bash
cd Backend/api-server
mvn spring-boot:run
```

Or run the packaged jar:

```bash
cd Backend
mvn -pl api-server -am package
java -jar api-server/target/api-server.jar
```

### 6. Verify the health endpoint

```bash
curl http://localhost:8080/actuator/health
```

Expected response once Postgres and Redis are both reachable:

```json
{"status":"UP"}
```

## Environment Configuration

All environment-specific values are read from environment variables (see
`.env.example`). Nothing sensitive is hard-coded, and `.env` is gitignored.

| Variable | Purpose | Default |
|---|---|---|
| `DB_NAME` | Postgres database name | `taskplatform` |
| `DB_USER` | Postgres username | `taskplatform_user` |
| `DB_PASSWORD` | Postgres password | `change_me_locally` |
| `DB_HOST` | Postgres host (as seen by the app) | `localhost` |
| `DB_PORT` | Postgres host port | `5433` |
| `REDIS_HOST` | Redis host | `localhost` |
| `REDIS_PORT` | Redis host port | `6379` |
| `SPRING_PROFILES_ACTIVE` | Active Spring profile | `dev` |
| `SERVER_PORT` | API server port | `8080` |

## Database Setup

Schema is entirely managed by **Flyway** — there is no `schema.sql` and
Hibernate DDL auto-generation is disabled (`ddl-auto: validate`). Migrations
live in `api-server/src/main/resources/db/migration/` and are applied
automatically on application startup.

Current migrations:

- `V1__init_extensions.sql` — enables the `pgcrypto` extension, required for
  `gen_random_uuid()` once entity tables are introduced.

## API Documentation

Not applicable yet — no REST endpoints beyond Spring Boot Actuator's
built-in `/actuator/health` exist in this phase. OpenAPI/Swagger will be
added once the first real API surface (auth, Phase 2) exists.

## Testing

- `common-core`: plain JUnit 5 unit tests.
- `api-server`: a Testcontainers-backed integration test
  (`ApiServerHealthIntegrationTest`) that boots the full Spring context
  against real, ephemeral Postgres and Redis containers and asserts
  `/actuator/health` reports `UP`. This is the one test that matters for
  this phase — it's exercising the exact infrastructure Phase 1 was meant
  to establish, not padding for coverage's sake.

Run everything:

```bash
mvn clean test
```

## Screenshots

_(placeholder — will be added once the frontend dashboard exists, Phase 9+)_

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 0 | Repository & architecture setup | ✅ Done |
| 1 | Docker Compose, Postgres, Redis, Flyway, health endpoint | ✅ Done |
| 2 | Authentication & users | ⬜ Not started |
| 3 | Projects | ⬜ Not started |
| 4 | Tasks & team management | ⬜ Not started |
| 5 | Job creation & persistence | ⬜ Not started |
| 6 | Redis queue | ⬜ Not started |
| 7 | Background worker | ⬜ Not started |
| 8 | Retry & failure handling | ⬜ Not started |
| 9 | Job monitoring dashboard (frontend begins) | ⬜ Not started |
| 10 | Workflow engine | ⬜ Not started |
| 11 | Audit logging | ⬜ Not started |
| 12 | Observability (metrics, correlation IDs) | ⬜ Not started |
| 13 | Testing & hardening | ⬜ Not started |
| 14 | Production-style deployment | ⬜ Not started |
| 15 | Documentation & portfolio prep | ⬜ Not started |

## Future Improvements

See Roadmap above — every unimplemented phase is a planned future
improvement, not an afterthought.
