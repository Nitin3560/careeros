# CareerOS Architecture

CareerOS is built around one main idea:

> Job discovery, matching, and application workflows should operate on a persistent normalized job dataset rather than repeatedly depending on external career sites.

The architecture separates external job collection from user-facing requests. This allows CareerOS to ingest jobs in the background, store them once, rank them efficiently, and serve results without contacting external applicant tracking systems every time a user opens the application.

## Architecture Overview

```text
                        External Job Sources
                               |
                  +------------+------------+
                  v            v            v
              Greenhouse      Lever        Ashby
                  |            |            |
                  +------------+------------+
                               |
                               v
                        Source Adapters
                               |
                               v
                       Ingestion Pipeline
                               |
                               v
                         Redis / RQ
                               |
                               v
                      Background Workers
                               |
                               v
                         PostgreSQL
                               |
                  +------------+------------+
                  v                         v
             Job Dataset              Candidate Data
                  |                         |
                  +------------+------------+
                               |
                               v
                        Matching Engine
                               |
                               v
                         Ranked Matches
                               |
                               v
                             Redis
                               |
                               v
                         FastAPI Backend
                               |
                               v
                         Next.js Frontend
```

Each layer owns a different responsibility. External systems provide raw job data, the ingestion layer normalizes it, PostgreSQL becomes the persistent source of truth, the matching engine determines relevance, Redis supports background processing and reusable results, FastAPI exposes the application boundary, and Next.js provides the user-facing workflow.

## Design Principles

### External Systems Are Not The Database

Company career sites can change, disappear, fail, or respond slowly.

CareerOS stores normalized jobs locally instead of treating external APIs as runtime dependencies for every search.

### Long-Running Work Stays Outside API Requests

Fetching jobs from many companies can take significant time.

That work belongs in background workers rather than inside a request-response cycle.

### Normalize Once, Use Everywhere

Greenhouse, Lever, and Ashby represent jobs differently.

The source adapter layer converts those formats into one internal job representation before downstream processing.

### Filter Early

The matching system reduces the candidate set as early as possible rather than repeatedly processing the entire job corpus in application memory.

### Cache Reusable Work

Results that do not need to be recomputed should be reused.

Caching helps keep user-facing requests fast while more expensive work happens elsewhere.

## External Job Sources

CareerOS interacts with multiple applicant tracking systems. Each source may expose different API structures, field names, location formats, job identifiers, descriptions, and metadata.

Those differences should not leak into the rest of the application. Source-specific adapters handle that translation.

```text
Greenhouse Response --+
Lever Response -------+--> Normalized Job
Ashby Response -------+
```

Once normalized, downstream components no longer need to know where the job came from.

## Source Resolution

Before jobs can be fetched, CareerOS determines which adapter should handle a company.

```text
Company
   |
   v
Source Configuration
   |
   v
Adapter Selection
   |
 +-+------------+
 v v            v
GH Lever       Ashby
```

This creates a clean boundary between company configuration and provider implementation. Adding another supported source should mainly require a new adapter rather than changes throughout the system.

## Ingestion Pipeline

The ingestion pipeline converts external job listings into persistent CareerOS records.

```text
Fetch
  |
  v
Parse
  |
  v
Normalize
  |
  v
Check Existing Jobs
  |
  v
Insert / Update
  |
  v
PostgreSQL
```

The pipeline is designed to run repeatedly. Duplicate detection and stable source identifiers prevent repeated runs from blindly inserting the same postings again.

## Background Workers

Job ingestion is network-heavy and independent from most user requests.

CareerOS separates ingestion from the API process through background jobs.

```text
Trigger
   |
   v
Redis Queue
   |
   v
RQ Worker
   |
   v
Fetch Companies
   |
   v
Persist Jobs
```

The API can enqueue work and return without waiting for the entire ingestion process to complete. This improves responsiveness and creates a better place for retries and operational monitoring.

## PostgreSQL

PostgreSQL is the persistent system of record. It stores information required across application sessions, including job and candidate-related data.

The important architectural distinction is:

```text
PostgreSQL = persistent truth
Redis      = temporary acceleration / coordination
```

Redis should not become the only location for information that cannot safely be lost. Database schema changes are managed separately from application logic through migrations.

## Matching Engine

The matching engine connects candidate information with the stored job dataset.

```text
Candidate
    +
Job Dataset
    |
    v
Eligibility / Filtering
    |
    v
Candidate Set
    |
    v
Scoring / Ranking
    |
    v
Top Matches
```

Filtering happens before more expensive ranking work whenever possible. This prevents later stages from processing jobs that can already be rejected using structured database criteria.

## Database-Side Filtering

One important performance principle in CareerOS is moving appropriate filtering closer to PostgreSQL.

An inefficient approach looks like:

```text
Load Thousands of Jobs
        |
        v
Application Filtering
        |
        v
Matching
```

CareerOS instead aims for:

```text
PostgreSQL
    |
    v
Filter Candidate Jobs
    |
    v
Smaller Result Set
    |
    v
Application Matching
```

This reduces data movement and unnecessary Python processing. It also becomes more important as the job corpus grows.

## Caching

Some results are requested repeatedly without underlying data changing.

CareerOS uses Redis to avoid unnecessary recomputation.

```text
Request
   |
   v
Cache Lookup
 |       |
Hit      Miss
 |       |
 v       v
Return   Compute
          |
          v
        Cache
```

Caching is treated as an optimization rather than the source of truth. If a cached result is missing or invalid, the system can fall back to persistent data and recomputation.

## FastAPI Backend

FastAPI acts as the application-facing backend.

Its responsibilities include request validation, database access, matching endpoints, job workflows, resume workflows, background-job triggers, and cached result delivery.

The API layer coordinates application services but should avoid becoming the location where every domain behavior is implemented. More specialized logic belongs in services and workers.

## Service Layer

CareerOS separates reusable application logic into backend services.

This keeps ingestion, matching, resume processing, and external-source handling outside individual API routes.

```text
API Route
   |
   v
Service
   |
   +-- Database
   +-- Cache
   +-- External Source
   +-- Matching Logic
```

This also makes individual components easier to test without running the full web application.

## Next.js Frontend

The frontend provides the user-facing CareerOS workflow. It communicates with FastAPI rather than directly accessing storage or job providers.

```text
Browser
   |
   v
Next.js
   |
   v
FastAPI
   |
   v
Application Services
```

This keeps frontend responsibilities focused on interaction and presentation. The frontend does not need to understand Greenhouse APIs, Redis queues, or database queries.

## Resume-Aware Workflow

Resume information becomes part of the candidate model used by downstream matching and tailoring workflows.

```text
Resume Upload
     |
     v
Resume Processing
     |
     v
Candidate Information
     |
     +-------------+
     v             v
Matching       Tailoring
     |             |
     +------+------+
            v
      Application Workflow
```

This keeps the resume connected to the same job dataset used for discovery rather than creating a separate disconnected workflow.

## Failure Isolation

A major architectural goal is keeping failures contained.

```text
Greenhouse unavailable
        |
        v
Greenhouse ingestion affected

Existing CareerOS jobs remain available.
Matching remains available.
Frontend remains available.
Other source adapters can continue.
```

Similarly, a failed background ingestion job should not make ordinary job-search endpoints unavailable. This separation is one of the main reasons ingestion and user-facing requests use different execution paths.

## Containerization

CareerOS uses Docker configuration to keep local and deployment environments reproducible.

The system can separate application components into independently managed runtime services:

```text
API
Web
PostgreSQL
Redis
Workers
```

Containerization does not define the architecture itself, but it provides a consistent way to run that architecture.

## Component Responsibilities

| Component | Responsibility |
|---|---|
| Source Adapters | Translate external ATS data |
| Ingestion Pipeline | Fetch, normalize, and persist jobs |
| Redis / RQ | Queue background work and cache reusable results |
| Workers | Execute asynchronous jobs |
| PostgreSQL | Persistent application state |
| Matching Engine | Filter, score, and rank jobs |
| FastAPI | Backend application boundary |
| Next.js | User-facing application |
| Docker | Reproducible runtime environment |

The most important rule is that these responsibilities should remain separated.

## Extending The Architecture

A new job source should fit into the existing ingestion boundary:

```text
New ATS
   |
   v
New Adapter
   |
   v
Normalized Job
   |
   v
Existing Pipeline
```

A new matching strategy should operate on the existing normalized job model.

A new frontend feature should consume backend APIs rather than introducing direct infrastructure dependencies.

This allows CareerOS to grow without turning every new feature into a cross-system rewrite.

## Architecture Summary

CareerOS separates the job-search lifecycle into a small number of clear stages:

```text
Collect
   |
   v
Normalize
   |
   v
Persist
   |
   v
Filter
   |
   v
Rank
   |
   v
Cache
   |
   v
Serve
```

External job systems are treated as inputs. PostgreSQL becomes persistent state. Background workers handle slow workloads. The matching engine operates on normalized data. Redis improves responsiveness. FastAPI and Next.js expose the result as a usable application.

## Closing Remarks

The architecture of CareerOS grew out of the limitations of treating job search as a collection of independent scripts.

Fetching jobs is different from storing them. Storing jobs is different from ranking them. Ranking jobs is different from serving results.

Separating those concerns made the system easier to scale, test, and reason about.

> CareerOS turns unreliable external job sources into a persistent internal dataset that can be processed asynchronously and matched efficiently against a candidate profile.
