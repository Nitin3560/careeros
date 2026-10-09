# CareerOS

> **A full-stack job search and matching platform that aggregates software engineering roles, ranks opportunities against a candidate profile, and manages the workflow from job discovery to application.**

> **Recent jobs:** [Browse the U.S. technology jobs feed](https://nitin3560.github.io/careeros/).

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

### Bulk collection poller rollout

Run these steps in order from the repository root. The poller collects raw jobs and normalized descriptions only; classification and matching stay downstream.

```bash
# 1. Schema and legacy board links
cd apps/api && alembic upgrade head && cd ../..
python scripts/backfill_job_board_ids.py
python scripts/backfill_job_descriptions.py --batch-size 500 --sleep-between-batches 1.0
python scripts/assign_board_tiers.py

# 2. Capacity and real-source quality checks
python scripts/load_test_poller.py
python scripts/smoke_test_sources.py --database-url "$DATABASE_URL"

# 3. One full shadow sweep (expiry remains off)
POLLER_EXPIRY_ENABLED=false python scripts/run_poller.py

# 4. In another terminal, inspect coverage and quality
python scripts/coverage_report.py
```

Run either the Docker `poller` service or the manual command, never both. The
poller holds a PostgreSQL advisory lock and exits non-zero if another instance
is active. It claims due boards in batches of 300 by default
(`POLLER_BATCH_SIZE`) and caps Greenhouse detail requests at 200 per board
(`POLLER_DETAIL_CAP_PER_BOARD`).

Never run the description backfill during the first full poller sweep. Both
jobs write to the `jobs` table, and running them together can saturate
PostgreSQL WAL and Docker disk I/O. Finish the initial sweep first, then run
the resumable backfill by itself, preferably overnight.

Legacy Greenhouse rows are deliberately skipped by the normal sweep. Refresh
their descriptions separately with a resumable, rate-limited command:

```bash
python scripts/refresh_legacy_greenhouse.py --rate 5 --batch-size 500
```

`POLLER_CONCURRENCY` defaults to `64`. Use `POLLER_BOARD_LIMIT` and `POLLER_ATS` for bounded tests. After reviewing a clean full sweep, restart with `POLLER_EXPIRY_ENABLED=true`. Enable the daily cleanup only after that by setting `POLLER_RETENTION_ENABLED=true` and running `scripts/retain_expired_jobs.py`. The coverage report writes `reports/coverage_report.json`; focus on schedule lag, p50/p95 latency, source-level description quality, and first-seen freshness.

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
## Recent U.S. Technology Job Openings

Auto-updated hourly from CareerOS. Last run: **2026-10-09 21:49 UTC**. Showing U.S. software/AI/tech postings found in the last **7 days**.

Speed: CareerOS refreshes every hour from company career pages, then records the first time each posting was found. Current feed size: **20** roles.

Eligibility: recent U.S. software, AI/ML, data, infrastructure, security, embedded, and related engineering roles with explicit posting evidence of no more than two years of required experience. Roles with missing, ambiguous, or greater-than-two-year requirements are excluded, as are internships, obvious non-technical roles, non-U.S. postings, and defense/clearance-restricted roles.

Quick links: [Tier 1](#tier-1) · [Tier 2](#tier-2) · [Tier 3](#tier-3)

### Tier 1

Large public and established technology, financial, and enterprise companies.

| Company | Role | Experience | Posted | Found | Salary | Apply |
|---|---|---|---|---|---|---|
| Roblox | Software Engineer, Engine Systems<br><sub>San Mateo, CA, United States</sub> | 1 year | 2026-10-09 | just now |  | [Apply](https://careers.roblox.com/jobs/8159854?gh_jid=8159854) |
| Roblox | Software Engineer, Test Frameworks & Tooling<br><sub>San Mateo, CA, United States</sub> | 1 year | 2026-10-09 | just now |  | [Apply](https://careers.roblox.com/jobs/8229705?gh_jid=8229705) |
| Stripe | Software Engineer<br><sub>Seattle, WA</sub> | 1–2 years | 2026-10-09 | just now |  | [Apply](https://stripe.com/jobs/search?gh_jid=8267736) |
| Esri | Software Engineer I - Front-End Engineer for ArcGIS Enterprise<br><sub>Redlands, CA</sub> | 1 year | 2026-10-07 | just now |  | [Apply](https://www.esri.com/careers/5190253007?gh_jid=5190253007) |
| Esri | C++ Software Development Engineer II - Graph Algorithms<br><sub>Redlands, CA</sub> | 1 year | 2026-10-06 | just now |  | [Apply](https://www.esri.com/careers/5032353007?gh_jid=5032353007) |
| Amazon | Software Development Engineer<br><sub>Newark, New Jersey, USA</sub> | 1 year | 2026-10-01 | just now |  | [Apply](https://account.amazon.jobs/jobs/10566605/apply) |
| Esri | DevOps Engineer I - ArcGIS Enterprise<br><sub>Redlands, CA</sub> | 1 year | 2026-09-11 | just now |  | [Apply](https://www.esri.com/careers/5012634007?gh_jid=5012634007) |
| Lyft | Data Scientist <br><sub>Seattle, WA</sub> | 2 years | 2026-09-10 | just now | $129,709 - $192,000 | [Apply](https://app.careerpuck.com/job-board/lyft/job/8772592002?gh_jid=8772592002) |
| Lyft | Software Engineer<br><sub>Seattle, WA</sub> | 2 years | 2026-09-09 | just now | $149,240 - $192,000 | [Apply](https://app.careerpuck.com/job-board/lyft/job/8772594002?gh_jid=8772594002) |

### Tier 2

Established mid-sized companies with meaningful engineering organizations.

| Company | Role | Experience | Posted | Found | Salary | Apply |
|---|---|---|---|---|---|---|
| Chime | Full-Stack Engineer, Human Agent Tooling <br><sub>San Francisco, CA, USA</sub> | 1 year | 2026-10-02 | just now |  | [Apply](https://boards.greenhouse.io/chime/jobs/8606649002?gh_jid=8606649002) |
| Chime | Software Engineer, Infrastructure Platform <br><sub>Chicago, IL, USA; New York, NY, USA; San Francisco, CA, USA</sub> | 2 years | 2026-10-02 | just now |  | [Apply](https://boards.greenhouse.io/chime/jobs/8859182002?gh_jid=8859182002) |
| Chime | Software Engineer, Infrastructure<br><sub>Chicago, IL, USA; New York, NY, USA; San Francisco, CA, USA</sub> | 2 years | 2026-10-01 | just now |  | [Apply](https://boards.greenhouse.io/chime/jobs/8616359002?gh_jid=8616359002) |
| Anthropic | Engineering Manager, GPU (ML Accelerator)<br><sub>San Francisco, CA \| New York City, NY \| Seattle, WA</sub> | 1 year | 2026-08-21 | just now |  | [Apply](https://job-boards.greenhouse.io/anthropic/jobs/4741104008) |

### Tier 3

Startups, early-stage companies, and smaller technology businesses.

| Company | Role | Experience | Posted | Found | Salary | Apply |
|---|---|---|---|---|---|---|
| Altentechnologyusa | SAP ABAP & BTP Full Stack Developer (Entry-Level)<br><sub>Foster City, California, United States</sub> | 0–2 years | 2026-10-09 | just now | $70,000 - 80,000 | [Apply](https://job-boards.greenhouse.io/altentechnologyusa/jobs/5262456007) |
| Twitch | Software Engineer I<br><sub>San Francisco, CA</sub> | 1 year | 2026-10-08 | just now |  | [Apply](https://job-boards.greenhouse.io/twitch/jobs/8879673002) |
| Lilasciences | Senior / Staff Machine Learning Engineer, Applied AI<br><sub>Cambridge, MA USA; San Francisco, CA USA</sub> | 1–2 years | 2026-10-07 | just now |  | [Apply](https://job-boards.greenhouse.io/lilasciences/jobs/4400741009) |
| Nimblerobotics | Robotics Software Engineer<br><sub>San Francisco, CA</sub> | 1 year | 2026-09-28 | just now | $230,000/year | [Apply](https://job-boards.greenhouse.io/nimblerobotics/jobs/4371388009) |
| Connectionshealthsolutions | Registered Nurse (RN) (FT, Front End Nights)<br><sub>Phoenix, Arizona, United States</sub> | 1 year | 2026-09-22 | just now |  | [Apply](https://job-boards.greenhouse.io/connectionshealthsolutions/jobs/4405220009) |
| Twitch | Software Engineer I, Payments<br><sub>San Francisco, CA</sub> | 1 year | 2026-09-18 | just now |  | [Apply](https://job-boards.greenhouse.io/twitch/jobs/8700578002) |
| Oldmissioncapital | Junior Trading Operations/DevOps Engineer<br><sub>Chicago, IL, United States</sub> | 0–2 years | 2026-09-08 | just now | $150,000 - $200,000 | [Apply](https://www.oldmissioncapital.com/careers/?gh_jid=7989374003) |

<!-- ENTRY_JOBS:END -->
