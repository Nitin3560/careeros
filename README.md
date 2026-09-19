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

- **Job ingestion** - collects roles from supported company sources.
- **Source adapters** - normalizes Greenhouse, Lever, and Ashby jobs.
- **Resume parsing** - converts uploaded resumes into structured profiles.
- **Job matching** - ranks roles against candidate skills and experience.
- **Match caching** - reuses valid scores instead of recomputing.
- **Background workers** - moves slow ingestion and matching work out of API requests.
- **Resume tailoring** - creates per-job resume versions.
- **Application tracking** - stores applied jobs, status, and notes.

---

## Architecture

CareerOS separates external job ingestion, persistent storage, candidate matching, background processing, caching, API delivery, and the frontend application.

![CareerOS End-to-End Architecture](docs/careeros-architecture.png)

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

<!-- ENTRY_JOBS:START -->
## New Grad & Entry-Level Engineering Roles

Auto-updated hourly from CareerOS. Last run: **2026-09-19 20:19 UTC**. Showing only postings found in the last **7 days**.

Quick links: [Tier A](#tier-a) · [Tier B](#tier-b) · [Tier C](#tier-c)

### Tier A

| Company | Role | Posted | Found | Salary | Apply |
|---|---|---|---|---|---|
| stripe | Software Engineer, Early Career — Immediate Start<br><sub>Toronto</sub> | 2026-09-17 | 2026-09-19 19:26 UTC |  | [Apply](https://stripe.com/jobs/search?gh_jid=8212517) |
| stripe | Software Engineer, Early Career — Immediate Start<br><sub>San Francisco, Seattle, New York</sub> | 2026-09-17 | 2026-09-19 19:26 UTC |  | [Apply](https://stripe.com/jobs/search?gh_jid=8212508) |
| stripe | Software Engineer, New Grad<br><sub>Singapore</sub> | 2026-09-10 | 2026-09-16 05:04 UTC |  | [Apply](https://stripe.com/jobs/search?gh_jid=8160776) |
| amazon | Software Development Engineer, Early Career<br><sub>Newark, New Jersey, USA</sub> | 2026-09-04 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10529830/apply) |
| amazon | Software Development Engineer, Early Career<br><sub>Cambridge, Massachusetts, USA</sub> | 2026-09-04 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10530257/apply) |

### Tier B

| Company | Role | Posted | Found | Salary | Apply |
|---|---|---|---|---|---|
| samsara | Software Engineer I, External Platform EMEA (Poland, Remote)<br><sub>Remote - Poland</sub> | 2026-09-18 | 2026-09-19 19:26 UTC |  | [Apply](https://www.samsara.com/company/careers/roles/8210695?gh_jid=8210695) |
| doordashusa | Software Engineer I, Entry-Level (Graduation Date: Fall 2026-Summer 2027) - US<br><sub>Los Angeles, CA; New York, NY; San Francisco, CA; Sunnyvale, CA; Seattle, WA</sub> | 2026-09-17 | 2026-09-16 05:04 UTC |  | [Apply](https://job-boards.greenhouse.io/doordashusa/jobs/8163709) |
| axon | Software Engineer I<br><sub>Bucharest, Bucharest, Romania</sub> | 2026-09-15 | 2026-09-16 05:04 UTC |  | [Apply](https://job-boards.greenhouse.io/axon/jobs/7818932003) |
| esri | Software Engineer I - Front-End Engineer for ArcGIS Enterprise<br><sub>Redlands, CA</sub> | 2026-09-14 | 2026-09-16 05:04 UTC |  | [Apply](https://www.esri.com/careers/5190253007?gh_jid=5190253007) |
| scaleai | Software Engineer - New Grad<br><sub>London, UK</sub> | 2026-09-14 | 2026-09-16 05:04 UTC |  | [Apply](https://job-boards.greenhouse.io/scaleai/jobs/4730862005) |
| scaleai | Software Engineer - New Grad<br><sub>Doha, Qatar</sub> | 2026-09-14 | 2026-09-16 05:04 UTC |  | [Apply](https://job-boards.greenhouse.io/scaleai/jobs/4730851005) |
| affirm | Software Engineer I, Frontend (Upfunnel)<br><sub>Remote Canada</sub> | 2026-09-11 | 2026-09-16 05:04 UTC |  | [Apply](https://job-boards.greenhouse.io/affirm/jobs/7985907003) |
| scaleai | Software Engineer - New Grad<br><sub>San Francisco, CA</sub> | 2026-09-04 | 2026-09-16 05:04 UTC |  | [Apply](https://job-boards.greenhouse.io/scaleai/jobs/4730836005) |

### Tier C

| Company | Role | Posted | Found | Salary | Apply |
|---|---|---|---|---|---|
| axon | Site Reliability Engineer I<br><sub>London, England, United Kingdom</sub> | 2026-09-18 | 2026-09-16 05:04 UTC |  | [Apply](https://job-boards.greenhouse.io/axon/jobs/7667846003) |
| relativity | GNC Simulation Engineer I<br><sub>Long Beach, California, United States</sub> | 2026-09-18 | 2026-09-19 19:26 UTC |  | [Apply](https://boards.greenhouse.io/relativity/jobs/8819367002?gh_jid=8819367002) |
| altentechnologyusa | ADAS Validation Engineer(Junior)<br><sub>Chelsea, Michigan, United States</sub> | 2026-09-17 | 2026-09-19 19:26 UTC |  | [Apply](https://job-boards.greenhouse.io/altentechnologyusa/jobs/5204290007) |
| relativity | Vehicle Mechanisms Engineer I - 2026 Graduate<br><sub>Long Beach, California, United States</sub> | 2026-09-16 | 2026-09-16 05:04 UTC |  | [Apply](https://boards.greenhouse.io/relativity/jobs/8761567002?gh_jid=8761567002) |
| axon | Firmware Engineer I<br><sub>Ho Chi Minh City, Ho Chi Minh City, Vietnam</sub> | 2026-09-11 | 2026-09-16 05:04 UTC |  | [Apply](https://job-boards.greenhouse.io/axon/jobs/7992162003) |
| esri | Product Engineer I – ArcGIS Pro Sharing Team<br><sub>Redlands, CA</sub> | 2026-09-11 | 2026-09-16 05:04 UTC |  | [Apply](https://www.esri.com/careers/5227152007?gh_jid=5227152007) |
| nebius | Junior Identity & Access Engineer (Early Talent)<br><sub>Prague, Czech Republic</sub> | 2026-09-11 | 2026-09-16 05:04 UTC |  | [Apply](https://careers.nebius.com/?gh_jid=4974213101) |
| lilasciences | Engineer I, Research Operations (2nd Shift)<br><sub>Cambridge, MA USA</sub> | 2026-09-08 | 2026-09-16 05:04 UTC |  | [Apply](https://job-boards.greenhouse.io/lilasciences/jobs/4386306009) |
| CesiumAstro | Radiation Effects Engineer I<br><sub>El Segundo, CA</sub> | 2026-09-08 | 2026-09-16 05:04 UTC |  | [Apply](https://jobs.lever.co/CesiumAstro/9e51c48b-593f-4775-9484-64d2465d7cf3) |
| altentechnologyusa | Junior Brake/Suspension Engineer<br><sub>Chelsea, Michigan, United States</sub> | 2026-09-04 | 2026-09-16 05:04 UTC |  | [Apply](https://job-boards.greenhouse.io/altentechnologyusa/jobs/5231655007) |
| CesiumAstro | Mechanical Engineer I<br><sub>Westminster, CO</sub> | 2026-09-03 | 2026-09-16 05:04 UTC |  | [Apply](https://jobs.lever.co/CesiumAstro/ebf75b86-512b-476c-bf66-d0e399a21929) |
| CesiumAstro | Mechanical Engineer I<br><sub>El Segundo, CA</sub> | 2026-09-03 | 2026-09-16 05:04 UTC |  | [Apply](https://jobs.lever.co/CesiumAstro/afe752ca-1eb7-4814-87af-77e7f320a7d8) |
| CesiumAstro | Mechanical Engineer I<br><sub>Austin, TX</sub> | 2026-09-03 | 2026-09-16 05:04 UTC |  | [Apply](https://jobs.lever.co/CesiumAstro/022424e4-8d66-4f94-9ffa-99eb6b77d458) |
| CesiumAstro | Manufacturing Engineer I<br><sub>Austin, TX</sub> | 2026-09-03 | 2026-09-16 05:04 UTC |  | [Apply](https://jobs.lever.co/CesiumAstro/8ec1f26b-a47d-4160-9cbd-1f09c8716b90) |
| CesiumAstro | Electrical Engineer I<br><sub>Westminster, CO</sub> | 2026-09-03 | 2026-09-16 05:04 UTC |  | [Apply](https://jobs.lever.co/CesiumAstro/d40a968c-60b0-4c96-b455-44c72ee5ab13) |
| CesiumAstro | FPGA Engineer I<br><sub>Austin, TX</sub> | 2026-09-03 | 2026-09-16 05:04 UTC |  | [Apply](https://jobs.lever.co/CesiumAstro/fb2ee9a4-646b-41d8-a037-3acb648db8e1) |
| CesiumAstro | Electrical Engineer I<br><sub>Austin, TX</sub> | 2026-09-03 | 2026-09-16 05:04 UTC |  | [Apply](https://jobs.lever.co/CesiumAstro/c783c39b-60c5-4154-9190-96c35e2f8fcb) |

<!-- ENTRY_JOBS:END -->
