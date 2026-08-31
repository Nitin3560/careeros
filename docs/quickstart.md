# Quickstart

This guide runs CareerOS locally using Docker.

## Prerequisites

Install:

```text
Docker
Docker Compose
Git
```

## Clone The Repository

```bash
git clone https://github.com/Nitin3560/careeros.git
cd careeros
```

## Environment

Create the local environment file:

```bash
cp .env.example .env
```

Configure any required values before starting the services.

## Start CareerOS

```bash
docker compose up --build
```

The development stack includes the application services required by CareerOS, including the backend, database, and Redis infrastructure.

## Architecture

```text
Next.js
   |
   v
FastAPI
   |
   +-- PostgreSQL
   +-- Redis / RQ
           |
           v
         Worker
```

FastAPI handles user-facing requests while background workers process longer-running tasks such as job ingestion.

## Database Migrations

CareerOS uses Alembic for database schema migrations.

From the API environment:

```bash
alembic upgrade head
```

## Development Workflow

A typical local workflow is:

```text
Start Services
     |
     v
Run Migrations
     |
     v
Ingest Jobs
     |
     v
Upload Resume
     |
     v
Generate Matches
     |
     v
Open CareerOS UI
```

## Troubleshooting

If the application does not start, verify:

```text
PostgreSQL is running
Redis is running
environment variables are configured
database migrations are current
required ports are available
```

Docker logs can be inspected with:

```bash
docker compose logs
```

## Next Steps

For more information, see:

- [Architecture](architecture.md)
- [Engineering Design Decisions](design-decisions.md)
- [Job Ingestion Pipeline](ingestion.md)
- [Candidate Matching Engine](matching.md)
- [Performance Baseline](performance/baseline.md)
- [Performance and Caching](performance/caching.md)
