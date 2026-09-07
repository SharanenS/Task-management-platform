# Enterprise Task Processing & Workflow Management System

A modern enterprise platform built with **FastAPI** (Python) and **Next.js** (TypeScript).

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic |
| Frontend | Next.js (App Router), React, TypeScript, Tailwind CSS |
| Database | PostgreSQL 16 |
| Cache/Queue | Redis 7, RabbitMQ 3 |
| Auth | Keycloak (OAuth2/OIDC) |
| Async Tasks | Celery |
| File Storage | Amazon S3 |

## Quick Start

```bash
# Start infrastructure
docker compose up -d

# Install Python dependencies
cd backend
pip install -e ".[dev]"

# Run database migrations
alembic upgrade head

# Start the backend
uvicorn app.main:app --reload --port 8000

# In another terminal, start the frontend
cd frontend
npm install
npm run dev
```

## API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health: http://localhost:8000/api/v1/health