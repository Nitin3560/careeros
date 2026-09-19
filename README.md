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

Auto-updated hourly from CareerOS. Last run: **2026-09-19 20:59 UTC**. Showing U.S. software/AI/tech postings found in the last **7 days**.

Speed: CareerOS refreshes every hour from company career pages, then records the first time each posting was found. Current feed size: **100** roles.

Quick links: [Tier A](#tier-a) · [Tier B](#tier-b) · [Tier C](#tier-c)

### Tier A

Exact new-grad / university-grad / early-career full-time tech roles.

| Company | Role | Posted | Found | Salary | Apply |
|---|---|---|---|---|---|
| stripe | Software Engineer, Early Career — Immediate Start<br><sub>San Francisco, Seattle, New York</sub> | 2026-09-17 | 2026-09-19 19:26 UTC |  | [Apply](https://stripe.com/jobs/search?gh_jid=8212508) |

### Tier B

Engineer I/II, SDE I/II, junior, associate, and MTS-style tech roles.

| Company | Role | Posted | Found | Salary | Apply |
|---|---|---|---|---|---|
| pinterest | Software Engineer II, Data Analytics & Engineering<br><sub>San Francisco, CA, US; Remote, US</sub> | 2026-09-19 | 2026-09-19 19:26 UTC |  | [Apply](https://www.pinterestcareers.com/jobs/?gh_jid=8213988) |
| torcrobotics | Software Engineer 2<br><sub>Blacksburg, VA</sub> | 2026-09-18 | 2026-09-19 19:26 UTC |  | [Apply](https://job-boards.greenhouse.io/torcrobotics/jobs/8783949002) |
| amazon | Software Dev Engineer II, EC2 Capacity Reservations<br><sub>Seattle, Washington, USA</sub> | 2026-09-18 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10553910/apply) |
| amazon | Embedded Software Development Engineer II (C/C++), AWS EC2 VPC NX<br><sub>Seattle, Washington, USA</sub> | 2026-09-18 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10553911/apply) |
| amazon | Software Development Engineer II, AWS WorkSpaces, AWS WorkSpaces Control Plane Backend<br><sub>Seattle, Washington, USA</sub> | 2026-09-18 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10553627/apply) |
| amazon | Software Development Engineer II, OrcaLabs<br><sub>Seattle, Washington, USA</sub> | 2026-09-18 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10553852/apply) |
| amazon | Software Development Engineer II, PACMAN<br><sub>Bellevue, Washington, USA</sub> | 2026-09-18 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10554069/apply) |
| amazon | Software Development Engineer II, S3 Storage Control Plane - Durability<br><sub>Bellevue, Washington, USA</sub> | 2026-09-18 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10553307/apply) |
| amazon | Software Development Engineer 2, Prime Video Personalization and Discovery<br><sub>Seattle, Washington, USA</sub> | 2026-09-18 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10553194/apply) |
| amazon | Software Development Engineer II, AWS Fintech<br><sub>Seattle, Washington, USA</sub> | 2026-09-18 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10553922/apply) |
| amazon | Software Development Engineer II, Amazon Leo<br><sub>Redmond, Washington, USA</sub> | 2026-09-18 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10553807/apply) |
| axon | Software Engineer II<br><sub>Sterling, Virginia, United States</sub> | 2026-09-17 | 2026-09-19 19:26 UTC |  | [Apply](https://job-boards.greenhouse.io/axon/jobs/6288464003) |
| doordashusa | Software Engineer I, Entry-Level (Graduation Date: Fall 2026-Summer 2027) - US<br><sub>Los Angeles, CA; New York, NY; San Francisco, CA; Sunnyvale, CA; Seattle, WA</sub> | 2026-09-17 | 2026-09-16 05:04 UTC |  | [Apply](https://job-boards.greenhouse.io/doordashusa/jobs/8163709) |
| amazon | Software Development Engineer II, AWS Marketplace<br><sub>Austin, Texas, USA</sub> | 2026-09-17 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10552221/apply) |
| amazon | Software Dev Engineer II, Device Engagament Metrics<br><sub>Denver, Colorado, USA</sub> | 2026-09-17 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10552789/apply) |
| amazon | SDE II , AWS IoT Fleet Management<br><sub>Seattle, Washington, USA</sub> | 2026-09-17 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10552293/apply) |
| brex | Software Engineer II, Backend<br><sub>New York, New York, United States</sub> | 2026-09-16 | 2026-09-19 19:26 UTC | $152,000 - $190,000 | [Apply](https://www.brex.com/careers/8815443002?gh_jid=8815443002) |
| axon | Site Reliability Engineer II<br><sub>Boston, Massachusetts, United States</sub> | 2026-09-16 | 2026-09-19 19:26 UTC |  | [Apply](https://job-boards.greenhouse.io/axon/jobs/7997565003) |
| amazon | Software Dev Engineer II-TEST , Agentic Workspaces <br><sub>Seattle, Washington, USA</sub> | 2026-09-16 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10544628/apply) |
| amazon | Software Development Engineer II, Hosted Execution (HEX)<br><sub>Seattle, Washington, USA</sub> | 2026-09-16 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10544701/apply) |
| amazon | Software Dev Engineer II, Prime Air<br><sub>Seattle, Washington, USA</sub> | 2026-09-16 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10545581/apply) |

### Tier C

Other U.S. non-senior software/AI/tech roles found this week.

| Company | Role | Posted | Found | Salary | Apply |
|---|---|---|---|---|---|
| roblox | Software Engineer, Engine Infrastructure<br><sub>San Mateo, CA, United States</sub> | 2026-09-19 | 2026-09-16 05:04 UTC |  | [Apply](https://careers.roblox.com/jobs/8171506?gh_jid=8171506) |
| roblox | Software Engineer, Discovery UX<br><sub>San Mateo, CA, United States</sub> | 2026-09-19 | 2026-09-19 19:26 UTC |  | [Apply](https://careers.roblox.com/jobs/8168383?gh_jid=8168383) |
| rdccareers | Full Stack Software Engineer <br><sub>Austin, Texas, United States</sub> | 2026-09-19 | 2026-09-19 19:26 UTC |  | [Apply](https://boards.greenhouse.io/rdccareers/jobs/7997475003?gh_jid=7997475003) |
| reddit | Frontend Engineer, Ads<br><sub>Remote - United States</sub> | 2026-09-19 | 2026-09-16 05:04 UTC |  | [Apply](https://job-boards.greenhouse.io/reddit/jobs/8194576) |
| block | Software Engineer<br><sub>Bay Area, CA, United States of America</sub> | 2026-09-19 | 2026-09-19 19:26 UTC |  | [Apply](http://block.xyz/careers/jobs/5426213008?gh_jid=5426213008) |
| reddit | Software Engineer, Ingestion Platform<br><sub>Remote - United States</sub> | 2026-09-18 | 2026-09-19 19:26 UTC |  | [Apply](https://job-boards.greenhouse.io/reddit/jobs/8214910) |
| esri | Software and Mobility Asset Supervisor<br><sub>Redlands, CA</sub> | 2026-09-18 | 2026-09-16 05:04 UTC |  | [Apply](https://www.esri.com/careers/5233640007?gh_jid=5233640007) |
| lyft | Backend Software Engineer, Airports<br><sub>San Francisco, CA</sub> | 2026-09-18 | 2026-09-19 19:26 UTC | $128,000 - $160,000 | [Apply](https://app.careerpuck.com/job-board/lyft/job/8806570002?gh_jid=8806570002) |
| andurilindustries | IT Systems Engineer<br><sub>Costa Mesa, California, United States</sub> | 2026-09-18 | 2026-09-19 19:26 UTC |  | [Apply](https://boards.greenhouse.io/andurilindustries/jobs/5239480007?gh_jid=5239480007) |
| andurilindustries | Mission Software Engineer<br><sub>Lexington, Massachusetts, United States</sub> | 2026-09-18 | 2026-09-19 19:26 UTC |  | [Apply](https://boards.greenhouse.io/andurilindustries/jobs/5239687007?gh_jid=5239687007) |
| andurilindustries | Production Software Engineer<br><sub>Fort Collins, Colorado, United States</sub> | 2026-09-18 | 2026-09-16 05:04 UTC |  | [Apply](https://boards.greenhouse.io/andurilindustries/jobs/5189514007?gh_jid=5189514007) |
| andurilindustries | Site Reliability Engineer<br><sub>Waltham, Massachusetts, United States</sub> | 2026-09-18 | 2026-09-16 05:04 UTC |  | [Apply](https://boards.greenhouse.io/andurilindustries/jobs/5236881007?gh_jid=5236881007) |
| andurilindustries | Quality Systems Engineer<br><sub>Ashville, Ohio, United States</sub> | 2026-09-18 | 2026-09-16 05:04 UTC |  | [Apply](https://boards.greenhouse.io/andurilindustries/jobs/5200601007?gh_jid=5200601007) |
| twitch | Software Engineer, Data Platform<br><sub>San Francisco, CA</sub> | 2026-09-18 | 2026-09-19 19:26 UTC |  | [Apply](https://job-boards.greenhouse.io/twitch/jobs/8817023002) |
| waymo | Marketplace Platform, TLM<br><sub>Mountain View, CA, USA</sub> | 2026-09-18 | 2026-09-19 19:27 UTC |  | [Apply](https://careers.withwaymo.com/jobs?gh_jid=7436212) |
| waymo | Machine Learning Engineer, Perception<br><sub>Mountain View, CA, USA; San Francisco, CA, USA</sub> | 2026-09-18 | 2026-09-19 19:27 UTC |  | [Apply](https://careers.withwaymo.com/jobs?gh_jid=8212478) |
| scoutmotors | AI Workflow Engineer<br><sub>Charlotte, North Carolina, United States</sub> | 2026-09-18 | 2026-09-19 19:26 UTC |  | [Apply](https://job-boards.greenhouse.io/scoutmotors/jobs/5240865007) |
| torcrobotics | Software Engineer, II - Map Enablement<br><sub>Ann Arbor, MI</sub> | 2026-09-18 | 2026-09-19 19:26 UTC | $139,000 - $166,800 | [Apply](https://job-boards.greenhouse.io/torcrobotics/jobs/8789483002) |
| doordashusa | Software Engineer<br><sub>San Francisco, CA; Seattle, WA; NYC, NY</sub> | 2026-09-18 | 2026-09-19 19:26 UTC |  | [Apply](https://job-boards.greenhouse.io/doordashusa/jobs/8212984) |
| coinbase | Software Engineer, Developer Infrastructure<br><sub>Remote - USA</sub> | 2026-09-18 | 2026-09-16 05:04 UTC |  | [Apply](https://www.coinbase.com/careers/positions/7991839?gh_jid=7991839) |
| anthropic | Recruiting Analytics Data Engineer <br><sub>San Francisco, CA \| New York City, NY \| Seattle, WA</sub> | 2026-09-18 | 2026-09-16 05:04 UTC |  | [Apply](https://job-boards.greenhouse.io/anthropic/jobs/5424111008) |
| amazon | Software Development Engineer, Amazon Devices, DS2 (Device Software & Services)<br><sub>Denver, Colorado, USA</sub> | 2026-09-18 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10553819/apply) |
| amazon | Software Development Engineer, Leo Data Science Platform<br><sub>Redmond, Washington, USA</sub> | 2026-09-18 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10553004/apply) |
| amazon | Software Development Engineer, Prime Video ML Infrastructure<br><sub>Seattle, Washington, USA</sub> | 2026-09-18 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10553195/apply) |
| amazon | Software Development Engineer, AWS Analytics Engineering<br><sub>Seattle, Washington, USA</sub> | 2026-09-18 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10553986/apply) |
| amazon | Software Development Engineer, AWS OpenSearch Service<br><sub>Austin, Texas, USA</sub> | 2026-09-18 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10554084/apply) |
| amazon | Software Development Engineer, Devices & Services Trust CX Innovations<br><sub>Sunnyvale, California, USA</sub> | 2026-09-18 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10553155/apply) |
| amazon | Software Development Engineer, Advengers - Amazon Ads Brand & Video<br><sub>New York, New York, USA</sub> | 2026-09-18 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10553871/apply) |
| amazon | Software Development Engineer, SageMaker Unified Studio<br><sub>Bellevue, Washington, USA</sub> | 2026-09-18 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10553306/apply) |
| anthropic | Pre-training Data Infrastructure Engineer<br><sub>San Francisco, CA</sub> | 2026-09-17 | 2026-09-16 05:04 UTC |  | [Apply](https://job-boards.greenhouse.io/anthropic/jobs/4973067008) |
| verkada | Embedded Engineer - Streaming<br><sub>San Mateo, CA United States</sub> | 2026-09-17 | 2026-09-16 05:04 UTC |  | [Apply](https://job-boards.greenhouse.io/verkada/jobs/5230322007) |
| alpaca | Software Engineer - Core Trading<br><sub>Remote - Americas or EU</sub> | 2026-09-17 | 2026-09-19 19:26 UTC |  | [Apply](https://job-boards.greenhouse.io/alpaca/jobs/6194973004) |
| rebuildmanufacturing | Software Development Engineer<br><sub>Los Angeles, CA; Seattle, WA</sub> | 2026-09-17 | 2026-09-16 05:04 UTC | $111,543 – $167,315 | [Apply](https://job-boards.greenhouse.io/rebuildmanufacturing/jobs/4732952005) |
| reddit | Front End Software Engineer, Consumer Engineering<br><sub>Remote - United States</sub> | 2026-09-17 | 2026-09-19 19:26 UTC |  | [Apply](https://job-boards.greenhouse.io/reddit/jobs/8147559) |
| flyzipline | ML Infrastructure Engineer<br><sub>South San Francisco, California, USA</sub> | 2026-09-17 | 2026-09-16 05:04 UTC | $160,000 - $250,000 | [Apply](https://www.zipline.com/open-roles/7989516003?gh_jid=7989516003) |
| flyzipline | Embedded Firmware Engineer<br><sub>South San Francisco, California, USA</sub> | 2026-09-17 | 2026-09-16 05:04 UTC | $160,000 - $250,000 | [Apply](https://www.zipline.com/open-roles/7989547003?gh_jid=7989547003) |
| doordashusa | Software Engineer, Full Stack - Developer Insights<br><sub>San Francisco, CA; New York, NY; Los Angeles, CA; Seattle, WA</sub> | 2026-09-17 | 2026-09-19 19:26 UTC |  | [Apply](https://job-boards.greenhouse.io/doordashusa/jobs/8207877) |
| doordashusa | Software Engineer - Developer Experience, Web<br><sub>San Francisco, CA; Sunnyvale, CA; Los Angeles, CA; Seattle, WA; New York, NY</sub> | 2026-09-17 | 2026-09-16 05:04 UTC |  | [Apply](https://job-boards.greenhouse.io/doordashusa/jobs/8197854) |
| doordashusa | Software Engineer, Code Quality<br><sub>San Francisco, CA; Seattle, WA; New York, NY; Los Angeles, CA</sub> | 2026-09-17 | 2026-09-16 05:04 UTC |  | [Apply](https://job-boards.greenhouse.io/doordashusa/jobs/8202736) |
| doordashusa | Software Engineer, Cloud Infrastructure<br><sub>New York, NY</sub> | 2026-09-17 | 2026-09-16 05:04 UTC |  | [Apply](https://job-boards.greenhouse.io/doordashusa/jobs/8180903) |
| doordashusa | Software Engineer, Storage - Distributed Caching<br><sub>San Francisco, CA; Seattle, WA; New York, NY</sub> | 2026-09-17 | 2026-09-16 05:04 UTC |  | [Apply](https://job-boards.greenhouse.io/doordashusa/jobs/8191134) |
| point72 | Quant Library Developer, Macro Technology<br><sub>United States</sub> | 2026-09-17 | 2026-09-16 05:04 UTC | $200,000-$300,000 | [Apply](https://boards.greenhouse.io/point72/jobs/8782787002?gh_jid=8782787002) |
| amazon | Software Development Engineer , Amazon Leo Commerce<br><sub>Redmond, Washington, USA</sub> | 2026-09-17 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10552346/apply) |
| amazon | Software Development Engineer, AWS Lambda<br><sub>Seattle, Washington, USA</sub> | 2026-09-17 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10552708/apply) |
| amazon | Software Development Engineer, Network Fabric Engineering<br><sub>Seattle, Washington, USA</sub> | 2026-09-17 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10552082/apply) |
| amazon | Software Development Engineer, Amazon Connect Telecom Engineering<br><sub>Sunnyvale, California, USA</sub> | 2026-09-17 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10552602/apply) |
| amazon | Software Development Engineer, Amazon Vulnerability Management Service (AVMS)<br><sub>Seattle, Washington, USA</sub> | 2026-09-17 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10551950/apply) |
| amazon | Software Development Engineer, Agentic AI DevOps<br><sub>Seattle, Washington, USA</sub> | 2026-09-17 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10552775/apply) |
| amazon | Software Development Engineer , Ground Control Console (GC2)<br><sub>Redmond, Washington, USA</sub> | 2026-09-17 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10551480/apply) |
| amazon | Software Development Engineer<br><sub>Seattle, Washington, USA</sub> | 2026-09-17 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10551443/apply) |
| amazon | Software Development Engineer, EC2 Machine Learning Supercompute<br><sub>Seattle, Washington, USA</sub> | 2026-09-17 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10552548/apply) |
| amazon | Software Dev Engineer, Benefits Experience & Technology (BXT)<br><sub>Seattle, Washington, USA</sub> | 2026-09-17 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10552585/apply) |
| amazon | Software Development Engineer, AWS Partnerships<br><sub>Seattle, Washington, USA</sub> | 2026-09-17 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10552237/apply) |
| amazon | Software Development Engineer, Distributed Systems, Annapurna Labs<br><sub>Seattle, Washington, USA</sub> | 2026-09-17 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10552584/apply) |
| amazon | Software Development Engineer, Amazon WorkSpaces Applications<br><sub>Sunnyvale, California, USA</sub> | 2026-09-17 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10552157/apply) |
| amazon | Software Engineer, AWS SageMaker Unified Studio<br><sub>Arlington, Virginia, USA</sub> | 2026-09-17 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10551396/apply) |
| reddit | Software Engineer, Consumer Engineering<br><sub>Remote - United States</sub> | 2026-09-16 | 2026-09-19 19:26 UTC |  | [Apply](https://job-boards.greenhouse.io/reddit/jobs/8172457) |
| anthropic | Copywriter, Developer<br><sub>San Francisco, CA \| New York City, NY</sub> | 2026-09-16 | 2026-09-19 19:26 UTC |  | [Apply](https://job-boards.greenhouse.io/anthropic/jobs/5423931008) |
| esri | Software Developer II - Android Apps<br><sub>Portland, ME</sub> | 2026-09-16 | 2026-09-19 19:26 UTC |  | [Apply](https://www.esri.com/careers/5040328007?gh_jid=5040328007) |
| stripe | Backend Engineer, Intelligent Commerce<br><sub>Seattle, San Francisco, New York</sub> | 2026-09-16 | 2026-09-16 05:04 UTC |  | [Apply](https://stripe.com/jobs/search?gh_jid=7988264) |
| anthropic | Software Engineer, Tokens and Prompt Structures<br><sub>San Francisco, CA \| New York City, NY</sub> | 2026-09-16 | 2026-09-19 19:26 UTC |  | [Apply](https://job-boards.greenhouse.io/anthropic/jobs/5421263008) |
| reddit | Front End Software Engineer, Media Player<br><sub>Remote - United States</sub> | 2026-09-16 | 2026-09-16 05:04 UTC |  | [Apply](https://job-boards.greenhouse.io/reddit/jobs/8198102) |
| amazon | Software Development Engineer , Inventory Accounting<br><sub>Redmond, Washington, USA</sub> | 2026-09-16 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10546898/apply) |
| amazon | Software Development Engineer, AWS Transform Migrations <br><sub>Boston, Massachusetts, USA</sub> | 2026-09-16 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10544626/apply) |
| amazon | Software Development Engineer, AWS Quick<br><sub>Bellevue, Washington, USA</sub> | 2026-09-16 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10550866/apply) |
| amazon | Software Development Engineer, Specialist AI Tooling, Specialist Technology Team<br><sub>Austin, Texas, USA</sub> | 2026-09-16 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10547170/apply) |
| amazon | Software Dev Engineer<br><sub>Seattle, Washington, USA</sub> | 2026-09-16 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10548148/apply) |
| amazon | Software Development Engineer, Amazon Publisher Monetization - Video Ads, Ads - Video Demand - Fixed<br><sub>New York, New York, USA</sub> | 2026-09-16 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10551376/apply) |
| amazon | Software Development Engineer, Tax and Account Compliance Tech<br><sub>Seattle, Washington, USA</sub> | 2026-09-16 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10550363/apply) |
| amazon | Software Development Engineer, Agentic AI, Velocity Labs<br><sub>Seattle, Washington, USA</sub> | 2026-09-16 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10545820/apply) |
| amazon | Software Development Engineer, Infrastructure Reliability Engineering<br><sub>Arlington, Virginia, USA</sub> | 2026-09-16 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10545098/apply) |
| amazon | Software Development Engineer, Humorphic Labs<br><sub>Austin, Texas, USA</sub> | 2026-09-16 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10547103/apply) |
| amazon | Software Development Engineer , Leo Commerce Data Platform<br><sub>Redmond, Washington, USA</sub> | 2026-09-16 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10547041/apply) |
| amazon | Software Development Engineer, Special Projects<br><sub>Seattle, Washington, USA</sub> | 2026-09-16 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10547105/apply) |
| amazon | Software Development Engineer, FSx for Lustre<br><sub>Boston, Massachusetts, USA</sub> | 2026-09-16 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10547306/apply) |
| amazon | Software Development Engineer, AWS Security<br><sub>Seattle, Washington, USA</sub> | 2026-09-16 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10544608/apply) |
| amazon | Software Development Engineer , AWS Kubernetes (K8s), AWS Kubernetes<br><sub>Santa Clara, California, USA</sub> | 2026-09-16 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10544200/apply) |
| amazon | Software Development Engineer, Amazon DSP, Amazon Ad Exchange<br><sub>Arlington, Virginia, USA</sub> | 2026-09-16 | 2026-09-19 19:39 UTC |  | [Apply](https://account.amazon.jobs/jobs/10547074/apply) |

<!-- ENTRY_JOBS:END -->
