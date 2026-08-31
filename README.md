# CareerOS

> **A full-stack job search and matching platform that aggregates software engineering roles, ranks opportunities against a candidate profile, and manages the workflow from job discovery to application.**

CareerOS was built to solve a simple problem: searching for software engineering jobs across dozens of companies quickly becomes fragmented.

Jobs live across different applicant tracking systems. The same search is repeated across company career pages. Relevant roles have to be manually compared against a resume, and the information needed for an application ends up spread across multiple tools.

CareerOS brings that workflow into one system.

It continuously collects jobs from supported company sources, normalizes them into a common data model, stores them in PostgreSQL, and ranks relevant opportunities against a candidate profile.

---

## Demo

<p align="center">
<b>End-to-end CareerOS demonstration showing resume upload, AI-ranked job matches, and per-job resume tailoring.</b>
</p>

![CareerOS Demo](docs/careeros-demo.gif)

[Watch the full demo video](docs/careeros-demo.mp4)

---

## Key Capabilities

### Multi-Source Job Aggregation

CareerOS collects job postings across a configured company source set rather than depending on one job board.

Source-specific adapters handle differences between external applicant tracking systems and convert incoming jobs into a common internal representation.

```text
Company Career Pages
        |
        v
   Source Resolver
        |
   +----+----+
   v    v    v
Greenhouse Lever Ashby
   |    |    |
   +----+----+
        |
        v
   Normalization
        |
        v
    PostgreSQL
```

This keeps source-specific behavior outside the rest of the application.

---

### Candidate-to-Job Matching

CareerOS evaluates jobs against candidate information and produces ranked matches.

The matching pipeline considers job requirements and candidate signals before returning the strongest opportunities.

```text
Candidate Profile
        +
Available Jobs
        |
        v
Filtering + Matching
        |
        v
Scored Candidates
        |
        v
Ranked Job Matches
```

Expensive filtering and ranking operations are pushed toward the database rather than repeatedly processing the complete job corpus in application memory.

---

### Resume-Aware Workflow

A candidate can upload a resume and use it as part of the matching and application workflow.

CareerOS connects:

```text
Resume
   |
   v
Candidate Profile
   |
   v
Job Matching
   |
   v
Relevant Opportunities
   |
   v
Per-Job Resume Tailoring
```

The goal is to keep discovery and application preparation inside the same system rather than treating them as unrelated tools.

---

### Background Job Processing

Job ingestion and other long-running work should not block user-facing API requests.

CareerOS separates those workloads through background workers.

```text
API Request
    |
    v
Job Queue
    |
    v
Background Worker
    |
    v
External Sources
    |
    v
PostgreSQL
```

This keeps external network work outside latency-sensitive request paths and provides a cleaner boundary for retries and failure handling.

---

### Cached Match Results

Repeatedly recomputing the same job matches is unnecessary.

CareerOS uses caching for reusable results and frequently requested data.

```text
Request
   |
   v
Cache
 |    |
Hit   Miss
 |    |
 v    v
Return Compute
       |
       v
      Cache
```

Cached results are validated before being returned so incomplete or invalid matching records do not silently become user-facing results.

---

## Architecture

CareerOS separates external job ingestion, persistent storage, candidate matching, background processing, caching, API delivery, and the frontend application.

```text
                        JOB SOURCES
                            |
              +-------------+-------------+
              v             v             v
          Greenhouse       Lever         Ashby
              |             |             |
              +-------------+-------------+
                            |
                            v
                     Source Adapters
                            |
                            v
                    Ingestion Pipeline
                            |
                       Redis / RQ
                            |
                            v
                    Background Workers
                            |
                            v
                       PostgreSQL
                            |
                +-----------+-----------+
                v                       v
          Job Repository          Candidate Data
                |                       |
                +-----------+-----------+
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
                         FastAPI
                            |
                            v
                         Next.js
                            |
                            v
                           User
```

The architecture keeps the major workloads independent.

External source failures should not control frontend availability.

Matching should not require fetching jobs from external companies.

Background ingestion should not block API requests.

The frontend should not need to understand how individual applicant tracking systems represent jobs.

See [Architecture](docs/architecture.md) for the complete system design.

---

## Why CareerOS?

CareerOS started as a way to reduce the repetitive work involved in searching company career pages.

The interesting engineering problem quickly became larger than job scraping.

Different companies expose jobs differently.

External sources fail.

The same jobs can appear during multiple ingestion runs.

Job corpora grow continuously.

Matching becomes expensive if every request repeatedly loads and ranks thousands of records.

Long-running ingestion should not block user requests.

Cached results can become stale or invalid.

Those problems pushed CareerOS toward a system built around clear boundaries:

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
Match
   |
   v
Cache
   |
   v
Serve
```

Each stage solves a different problem.

---

## Job Ingestion Pipeline

CareerOS treats external job sources as unreliable systems.

The ingestion pipeline therefore separates source discovery from persistent job storage.

```text
Configured Companies
        |
        v
Source Resolution
        |
        v
ATS Adapter
        |
        v
Fetch Jobs
        |
        v
Normalize
        |
        v
Duplicate Detection
        |
        v
PostgreSQL
```

Source adapters isolate provider-specific formats.

The rest of CareerOS works with normalized job records rather than Greenhouse-, Lever-, or Ashby-specific payloads.

This makes additional sources easier to introduce without redesigning the matching system.

---

## Matching Engine

The matching system is designed around narrowing the candidate set before performing more expensive ranking work.

Instead of repeatedly loading the complete job corpus and filtering it entirely inside application code, database operations are used to eliminate irrelevant candidates earlier.

```text
Job Corpus
    |
    v
Database Filtering
    |
    v
Candidate Jobs
    |
    v
Matching / Ranking
    |
    v
Top Matches
```

This keeps the amount of data entering later matching stages small as the stored job corpus grows.

---

## Performance

CareerOS includes several performance-oriented design choices:

- database-side filtering and ranking,
- batched duplicate checks during ingestion,
- Redis-backed caching,
- asynchronous background workers,
- reusable cached match results,
- separation of external network work from request handling.

These optimizations focus on reducing unnecessary application work rather than simply adding more infrastructure.

Detailed measurements and methodology are documented in [Performance Baseline](docs/performance/baseline.md).

---

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js |
| Backend | FastAPI |
| Database | PostgreSQL |
| Cache | Redis |
| Background Jobs | RQ |
| Job Sources | Greenhouse, Lever, Ashby adapters |
| Containerization | Docker |
| API Style | REST |

---

## Repository Structure

```text
careeros/
|
+-- apps/
|   +-- api/                 # FastAPI backend
|   +-- web/                 # Next.js frontend
|
+-- docs/                    # Architecture and engineering documentation
+-- scripts/                 # Development and operational utilities
+-- docker-compose.yml
+-- docker-compose.prod.yml
+-- .env.example
+-- README.md
```

---

## Engineering Highlights

- Built a multi-source ingestion architecture that isolates ATS-specific behavior behind source adapters.
- Decoupled long-running ingestion from request handling using Redis-backed background workers.
- Moved matching filters and ranking closer to PostgreSQL to reduce unnecessary application-side processing.
- Added persistent caching for frequently requested matching results.
- Added duplicate detection and normalization to make repeated ingestion runs safer.
- Containerized application services for reproducible local and deployment environments.
- Structured the frontend and backend as independent applications with a REST API boundary.

---

## Development

Clone the repository:

```bash
git clone https://github.com/Nitin3560/careeros.git
cd careeros
```

Create the local environment configuration:

```bash
cp .env.example .env
```

Start the local services:

```bash
docker compose up --build
```

Quickstart documentation will be updated soon.

---

## Documentation

- [Architecture](docs/architecture.md)
- [Engineering Design Decisions](docs/design-decisions.md)
- [Job Ingestion Pipeline](docs/ingestion.md)
- [Candidate Matching Engine](docs/matching.md)
- [Performance Baseline](docs/performance/baseline.md)
- [Performance and Caching](docs/performance/caching.md)
- [Quickstart](docs/quickstart.md)

Background-worker documentation will be updated soon.

---

## Project Status

CareerOS is an actively developed MVP.

The core system includes job ingestion, persistent job storage, candidate matching, resume-aware workflows, background processing, caching, and the web application.

Current development is focused on hardening the system, improving observability and deployment workflows, and expanding measurable end-to-end evaluation.

---

## Closing Remarks

CareerOS began as a tool for finding relevant software engineering jobs.

The larger engineering problem became building a system that could continuously collect information from unreliable external sources, normalize it, process it asynchronously, efficiently rank a growing dataset, and expose the results through a responsive application.

The result is more than a job scraper.

> **CareerOS is a full-stack job search system that turns fragmented company job data into a persistent, searchable, and ranked candidate workflow.**
