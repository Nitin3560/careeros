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

Auto-updated hourly from classified CareerOS postings. Last run: **2026-09-28 22:08 UTC**. Showing active roles found in the last **7 days**.

Speed: CareerOS refreshes every hour from company career pages, then records the first time each posting was found. Current feed size: **150** roles.

Eligibility: current-version classifier-approved full-time technology roles in the U.S. Explicitly non-U.S., senior, restricted, expired, blocked-company, and over-two-year roles are excluded. Unknown locations and unstated experience are labeled for review.

Quick links: [Tier 1](#tier-1) · [Tier 2](#tier-2) · [Tier 3](#tier-3)

### Tier 1

Large public and established technology, financial, and enterprise companies.

#### 2026-09-24

| Company | Role | Location | Experience | Posted | Found | Salary | Apply |
|---|---|---|---|---|---|---|---|
| Bank of America | Consultant - Applications Programmer - Enterprise Correspondence Operations | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://ghr.wd1.myworkdayjobs.com/lateral-us/job/Newark/Consultant---Applications-Programmer---Enterprise-Correspondence-Operations_26024032) |
| Bank of America | Data Scientist I | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://ghr.wd1.myworkdayjobs.com/lateral-us/job/Atlanta/Data-Scientist-I_26034313-2) |
| Bank of America | Data Scientist I | ⚠ Unknown location | 1 year | Not shown | 4 days ago |  | [Apply](https://ghr.wd1.myworkdayjobs.com/lateral-us/job/Atlanta/Data-Scientist-I_26034307) |
| Bank of America | Data Scientist I | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://ghr.wd1.myworkdayjobs.com/lateral-us/job/Atlanta/Data-Scientist-I_26034343-1) |
| Bank of America | Software Engineer – Golang, System Design, Kubernetes Platform Development &amp; AI Automation | Chandler | Not stated | Not shown | 4 days ago |  | [Apply](https://ghr.wd1.myworkdayjobs.com/lateral-us/job/Chandler/Software-Engineer---Golang--System-Design--Kubernetes-Platform-Development---AI-Automation_26024269) |
| Bank of America | Network Security Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://ghr.wd1.myworkdayjobs.com/lateral-us/job/Denver/Network-Security-Engineer_26023472) |
| Bank of America | Software Engineer II | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://ghr.wd1.myworkdayjobs.com/lateral-us/job/Kennesaw/Software-Engineer-II_25030338-2) |
| Bank of America | Data Scientist II | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://ghr.wd1.myworkdayjobs.com/lateral-us/job/New-York/Data-Scientist-II_26020552-1) |
| Bank of America | Software Engineer II \(AI/ML\) | ⚠ Unknown location | 1 year | Not shown | 4 days ago |  | [Apply](https://ghr.wd1.myworkdayjobs.com/lateral-us/job/Plano/Software-Engineer-II--AI-ML-_26026987) |
| The Home Depot | Data Scientist - Generative BI | STORE SUPPORT CENTER, ATLANTA - 9090 | Not stated | Not shown | 4 days ago |  | [Apply](https://homedepot.wd5.myworkdayjobs.com/CareerDepot/job/STORE-SUPPORT-CENTER-ATLANTA---9090/Data-Scientist--Decision-Analytics_Req192435) |
| The Home Depot | Mobile Service Mechanic | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://homedepot.wd5.myworkdayjobs.com/CareerDepot/job/Mobile-Service-Mechanic_Req123404) |
| The Home Depot | Mobile Service Mechanic | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://homedepot.wd5.myworkdayjobs.com/CareerDepot/job/Mobile-Service-Mechanic_Req123823) |
| The Home Depot | Mobile Service Mechanic | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://homedepot.wd5.myworkdayjobs.com/CareerDepot/job/Mobile-Service-Mechanic_Req124393) |
| The Home Depot | Mobile Service Mechanic | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://homedepot.wd5.myworkdayjobs.com/CareerDepot/job/Mobile-Service-Mechanic_Req124965-1) |
| The Home Depot | Data Scientist | PENNANT PARK, ATLANTA - 9141 | Not stated | Not shown | 4 days ago |  | [Apply](https://homedepot.wd5.myworkdayjobs.com/CareerDepot/job/PENNANT-PARK-ATLANTA---9141/Data-Scientist_Req191791) |
| The Home Depot | Associate Data Scientist - Decision Analytics | STORE SUPPORT CENTER, ATLANTA - 9090 | Not stated | Not shown | 4 days ago |  | [Apply](https://homedepot.wd5.myworkdayjobs.com/CareerDepot/job/STORE-SUPPORT-CENTER-ATLANTA---9090/Associate-Data-Scientist---Decision-Analytics_Req192218) |
| The Home Depot | Associate Data Scientist - Generative BI | STORE SUPPORT CENTER, ATLANTA - 9090 | Not stated | Not shown | 4 days ago |  | [Apply](https://homedepot.wd5.myworkdayjobs.com/CareerDepot/job/STORE-SUPPORT-CENTER-ATLANTA---9090/Associate-Data-Scientist---Generative-BI_Req192214) |
| The Home Depot | Associate Data Scientist | STORE SUPPORT CENTER, ATLANTA - 9090 | Not stated | Not shown | 4 days ago |  | [Apply](https://homedepot.wd5.myworkdayjobs.com/CareerDepot/job/STORE-SUPPORT-CENTER-ATLANTA---9090/Associate-Data-Scientist_Req183776) |
| The Home Depot | Data Scientist - Decision Analytics | STORE SUPPORT CENTER, ATLANTA - 9090 | Not stated | Not shown | 4 days ago |  | [Apply](https://homedepot.wd5.myworkdayjobs.com/CareerDepot/job/STORE-SUPPORT-CENTER-ATLANTA---9090/Data-Scientist---Decision-Analytics_Req190553) |
| The Home Depot | Online Data Engineer | STORE SUPPORT CENTER, ATLANTA - 9090 | Not stated | Not shown | 4 days ago |  | [Apply](https://homedepot.wd5.myworkdayjobs.com/CareerDepot/job/STORE-SUPPORT-CENTER-ATLANTA---9090/Online-Data-Engineer_Req188841) |

### Tier 2

Established mid-sized companies with meaningful engineering organizations.

No matching roles in this tier right now.

### Tier 3

Startups, early-stage companies, and smaller technology businesses.

#### 2026-09-25

| Company | Role | Location | Experience | Posted | Found | Salary | Apply |
|---|---|---|---|---|---|---|---|
| Astranis | Software Defined Radio Hardware Associate \(Summer 2027\) | San Francisco | Not stated | 2026-09-25 | 4 days ago |  | [Apply](https://job-boards.greenhouse.io/astranis/jobs/4715983006) |
| Astranis | Software Defined Radio Hardware Associate \(Winter 2027\) | San Francisco | Not stated | 2026-09-25 | 4 days ago |  | [Apply](https://job-boards.greenhouse.io/astranis/jobs/4715985006) |

#### 2026-09-24

| Company | Role | Location | Experience | Posted | Found | Salary | Apply |
|---|---|---|---|---|---|---|---|
| Pure Storage | Systems Software Engineer | Santa Clara, California | Not stated | 2026-09-24 | 4 days ago |  | [Apply](https://job-boards.greenhouse.io/purestorage/jobs/8220346) |
| Accenture | Custom Software Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Bengaluru/Custom-Software-Engineer_ATCI-5725192-S2065034-1) |
| Accenture | Collibra Platform Engineer \*6472737 | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Charlotte-1120-S-Tryon-St-Corp/Collibra-Platform-Engineer--6472737_14699830-1) |
| Accenture | Custom Software Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Bengaluru/Custom-Software-Engineer_ATCI-5725184-S2065035-1) |
| Citi | Full Stack Engineer - Vice President | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://citi.wd5.myworkdayjobs.com/2/job/PLOT-NO-1-SNO-77/Full-Stack-Engineer---Vice-President_26984463) |
| Citi | Full stack Java Development -Assistant Vice President | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://citi.wd5.myworkdayjobs.com/2/job/1124-SHIVAJI-GARDENS-MOONLI/Full-stack-Java-Development--Assistant-Vice-President_26994358) |
| Booz Allen Hamilton | Appian Developer | Maxwell AFB, AL | Not stated | Not shown | 4 days ago |  | [Apply](https://bah.wd1.myworkdayjobs.com/BAH_Jobs/job/Maxwell-AFB-AL/Appian-Developer_R0250200) |
| Booz Allen Hamilton | Illumio Zero Trust Platform Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://bah.wd1.myworkdayjobs.com/BAH_Jobs/job/Reston-VA/Illumio-Zero-Trust-Platform-Engineer_R0250065) |
| Booz Allen Hamilton | Data Scientist, Mid | Arlington, VA | Not stated | Not shown | 4 days ago |  | [Apply](https://bah.wd1.myworkdayjobs.com/BAH_Jobs/job/Arlington-VA/Data-Scientist--Mid_R0250083) |
| Booz Allen Hamilton | Information System Security Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://bah.wd1.myworkdayjobs.com/BAH_Jobs/job/McLean-VA/Information-System-Security-Engineer_R0240977) |
| T-Mobile | Mobile Associate, Store in Store- Retail Sales | Logan, Utah | Not stated | Not shown | 4 days ago | $18,000/year | [Apply](https://tmobile.wd1.myworkdayjobs.com/External/job/Logan-Utah/Mobile-Associate--Store-in-Store--Retail-Sales_REQ374959-2) |
| T-Mobile | Mobile Associate,  Retail Sales \| Bilingual, Preferred \| Spanish | Chino, California | Not stated | Not shown | 4 days ago | $18,000/year | [Apply](https://tmobile.wd1.myworkdayjobs.com/External/job/Chino-California/Mobile-Associate---Retail-Sales---Bilingual--Preferred---Spanish_REQ374747-1) |
| T-Mobile | Mobile Associate - Retail Sales | Clinton, Mississippi | Not stated | Not shown | 4 days ago | $18,000/year | [Apply](https://tmobile.wd1.myworkdayjobs.com/External/job/Clinton-Mississippi/Mobile-Associate---Retail-Sales_REQ375094-1) |
| T-Mobile | Mobile Associate - Retail Sales | Glendora, California | Not stated | Not shown | 4 days ago | $18,000/year | [Apply](https://tmobile.wd1.myworkdayjobs.com/External/job/Glendora-California/Mobile-Associate---Retail-Sales_REQ374766-1) |
| T-Mobile | Mobile Associate - Retail Sales | Mobile, Alabama | Not stated | Not shown | 4 days ago | $18,000/year | [Apply](https://tmobile.wd1.myworkdayjobs.com/External/job/Mobile-Alabama/Mobile-Associate---Retail-Sales_REQ374930) |
| T-Mobile | Mobile Associate - Retail Sales | Port Lavaca, Texas | Not stated | Not shown | 4 days ago | $18,000/year | [Apply](https://tmobile.wd1.myworkdayjobs.com/External/job/Port-Lavaca-Texas/Mobile-Associate---Retail-Sales_REQ374937-1) |
| T-Mobile | Mobile Associate - Retail Sales | Port Lavaca, Texas | Not stated | Not shown | 4 days ago | $18,000/year | [Apply](https://tmobile.wd1.myworkdayjobs.com/External/job/Port-Lavaca-Texas/Mobile-Associate---Retail-Sales_REQ374938-1) |
| T-Mobile | Mobile Associate- Retail Sales, Bilingual | South Gate, California | Not stated | Not shown | 4 days ago | $18,000/year | [Apply](https://tmobile.wd1.myworkdayjobs.com/External/job/South-Gate-California/Mobile-Associate--Retail-Sales--Bilingual_REQ375093-2) |
| T-Mobile | Mobile Associate - Retail Sales, Bilingual | Union Gap, Washington | Not stated | Not shown | 4 days ago | $18,000/year | [Apply](https://tmobile.wd1.myworkdayjobs.com/External/job/Union-Gap-Washington/Mobile-Associate---Retail-Sales--Bilingual_REQ374108) |
| T-Mobile | Mobile Associate - Retail Sales, Bilingual | West Covina, California | Not stated | Not shown | 4 days ago | $18,000/year | [Apply](https://tmobile.wd1.myworkdayjobs.com/External/job/West-Covina-California/Mobile-Associate---Retail-Sales--Bilingual_REQ374765-1) |
| State Street | Software Engineer - REST API Development, Officer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://statestreet.wd1.myworkdayjobs.com/Global/job/Burlington-Massachusetts/Software-Engineer---REST-API-Development--Officer_R-798140) |
| State Street | Software Engineering &amp; Development, Vice President | Quincy, Massachusetts | Not stated | Not shown | 4 days ago |  | [Apply](https://statestreet.wd1.myworkdayjobs.com/Global/job/Quincy-Massachusetts/Software-Engineering---Development--Vice-President_R-797568-1) |
| State Street | SUMMIT/Fixed-Income application developer, AVP | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://statestreet.wd1.myworkdayjobs.com/Global/job/Quincy-Massachusetts/SUMMIT-Fixed-Income-application-developer--AVP_R-791368) |
| DXC Technology | Analista DevOps | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://dxctechnology.wd1.myworkdayjobs.com/DXCJobs/job/BRA---SP---SAOBERNARDO-DOCAMPO/Analista-DevOps_51589325) |
| New Relic | Software Engineer - Container Fabric | Portland, Oregon, USA | Not stated | 2026-09-24 | 4 days ago |  | [Apply](https://job-boards.greenhouse.io/newrelic/jobs/5431953008) |
| Accenture | Custom Software Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Bengaluru/Custom-Software-Engineer_ATCI-5762977-S2069203-1) |
| Accenture | Custom Software Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Bengaluru/Custom-Software-Engineer_ATCI-5762978-S2069204-1) |
| Accenture | Custom Software Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Bengaluru/Custom-Software-Engineer_ATCI-5776277-S2070182-1) |
| Accenture | Custom Software Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Bengaluru/Custom-Software-Engineer_ATCI-5776283-S2070181-1) |
| Accenture | Custom Software Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Bengaluru/Software-Development-Engineer_ATCI-5222068-S1915736-1) |
| Accenture | Cloud Platform Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Bhubaneswar/Data-Engineer_ATCI-5229870-S1920846-1) |
| Accenture | Custom Software Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Gurugram/Custom-Software-Engineer_ATCI-5730306-S2066098-1) |
| Accenture | AI / ML Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Hyderabad/AI---ML-Engineer_ATCI-5689317-S2061035-1) |
| Accenture | Custom Software Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Hyderabad/Custom-Software-Engineer_ATCI-5561931-S2023679-1) |
| Accenture | Custom Software Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Hyderabad/Custom-Software-Engineer_ATCI-5775194-S2069302) |
| Accenture | Custom Software Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Hyderabad/Custom-Software-Engineer_ATCI-R1-S2034513-1) |
| Accenture | Full Stack Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Hyderabad/Full-Stack-Engineer_ATCI-5696456-S2060451-1) |
| Accenture | Custom Software Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Kolkata/Application-Developer_ATCI-5050721-S1872411-1) |
| Accenture | Custom Software Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Mumbai/Application-Lead_ATCI-5050697-S1882235-1) |
| Accenture | Custom Software Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Mumbai/Custom-Software-Engineer_ATCI-R1-S2033461-1) |
| Accenture | AI / ML Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Pune/AI---ML-Engineer_ATCI-5750257-S2068222) |
| Accenture | Custom Software Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Pune/Application-Developer_ATCI-4961265-S1860605-1) |
| Accenture | Web Developer | ⚠ Unknown location | Not stated | Not shown | 4 days ago | $75,400 to $125,400 | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Toronto-40-King-St-W-Corp/Web-Developer_R00358790) |
| Accenture | Applied &amp; Agentic AI Junior Software Engineer | ⚠ Unknown location | New grad | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Torino/Applied---Agentic-AI-Junior-Software-Engineer_14423162) |
| Accenture | Custom Software Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Bengaluru/Custom-Software-Engineer_ATCI-5762958-S2069201-1) |
| Accenture | Custom Software Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Bengaluru/Custom-Software-Engineer_ATCI-5776230-S2070183-1) |
| Accenture | Infrastructure Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Bengaluru/Infrastructure-Engineer_ATCI-5774895-S2070184-1) |
| Accenture | Custom Software Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Hyderabad/Custom-Software-Engineer_ATCI-R1-S1955857-1) |
| Accenture | AI / ML Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Bengaluru/AI---ML-Engineer_ATCI-5522135-S2018948-1) |
| Accenture | Back-end Engineer Associate Manager | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Bengaluru/Back-end-Engineer-Associate-Manager_14569963) |
| Accenture | Cloud Platform Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Bengaluru/Cloud-Platform-Engineer_ATCI-5772416-S2068911-1) |
| Accenture | Custom Software Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Bengaluru/Custom-Software-Engineer_ATCI-5473091-S2002351-1) |
| Accenture | Custom Software Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Bengaluru/Custom-Software-Engineer_ATCI-5496438-S2030272-1) |
| Accenture | Custom Software Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Bengaluru/Custom-Software-Engineer_ATCI-5713533-S2068523-1) |
| Accenture | Custom Software Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Bengaluru/Custom-Software-Engineer_ATCI-5730305-S2066097-1) |
| Accenture | Custom Software Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Bengaluru/Custom-Software-Engineer_ATCI-5730935-S2066706-1) |
| Accenture | Custom Software Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Bengaluru/Custom-Software-Engineer_ATCI-5762848-S2069199) |
| Accenture | Custom Software Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Bengaluru/Custom-Software-Engineer_ATCI-5762849-S2069200-1) |
| Accenture | Custom Software Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Bengaluru/Custom-Software-Engineer_ATCI-5762959-S2069202-1) |
| Citi | GEN AI Developer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://citi.wd5.myworkdayjobs.com/2/job/Gurugram-Haryana-India/GEN-AI-Developer_26995643) |
| Comcast | Xfinity Mobile Retail Service Associate | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://comcast.wd115.myworkdayjobs.com/Comcast_Careers/job/CO---Arvada-5220-Wadsworth-Byp-Unit-B---Retail-XFR3360/Xfinity-Retail-Service-Associate_R443238) |
| Comcast | Xfinity Mobile Retail Service Associate | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://comcast.wd115.myworkdayjobs.com/Comcast_Careers/job/NM---Santa-Fe-3517-Zafarano---Retail-XFR3369/Xfinity-Retail-Service-Associate_R443576) |
| Comcast | Software Engineer 2 \(AI\) - Hybrid - Reston, VA - Freewheel | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://comcast.wd115.myworkdayjobs.com/Comcast_Careers/job/VA---Reston-11951-Freedom-Dr-Ste-900/Software-Engineer-2--AI----Hybrid---Reston--VA---Freewheel_R442248) |
| Booz Allen Hamilton | Sustainment Data Scientist | San Diego, CA | Not stated | Not shown | 4 days ago |  | [Apply](https://bah.wd1.myworkdayjobs.com/BAH_Jobs/job/San-Diego-CA/Sustainment-Data-Scientist_R0249515-1) |
| Booz Allen Hamilton | Information Systems Security Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://bah.wd1.myworkdayjobs.com/BAH_Jobs/job/Reston-VA/Information-Systems-Security-Engineer_R0250235) |
| Palantir | Forward Deployed Software Engineer - US Government | Kitsap, WA | Not stated | 2026-09-24 | 4 days ago | $135,000 - $200,000 | [Apply](https://jobs.lever.co/palantir/a2e9ab0f-4dd1-4744-92b9-edc7ae393c58) |
| DXC Technology | Analyst I Software Engineering | USA - CT - ANY CITY | Not stated | Not shown | 4 days ago |  | [Apply](https://dxctechnology.wd1.myworkdayjobs.com/DXCJobs/job/USA---CT---ANY-CITY/Analyst-I-Software-Engineering_51586934) |
| Mastercard | Software Engineer II | O'Fallon, Missouri | Not stated | Not shown | 4 days ago |  | [Apply](https://mastercard.wd1.myworkdayjobs.com/CorporateCareers/job/OFallon-Missouri/Software-Engineer-II_R-289524-1) |
| Cadence Design Systems | Software Engineer I: Jasper R&amp;D | ⚠ Unknown location | New grad | Not shown | 4 days ago |  | [Apply](https://cadence.wd1.myworkdayjobs.com/External_Careers/job/BELO-HORIZONTE/Software-Engineer-I--Jasper-R-D_R55752) |
| Booz Allen Hamilton | AI Model Engineer | Springfield, VA | Not stated | Not shown | 4 days ago |  | [Apply](https://bah.wd1.myworkdayjobs.com/BAH_Jobs/job/Springfield-VA/AI-Model-Engineer_R0249971) |
| Booz Allen Hamilton | DevOps Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://bah.wd1.myworkdayjobs.com/BAH_Jobs/job/Arlington-VA/DevOps-Engineer_R0250013) |
| Booz Allen Hamilton | Data Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://bah.wd1.myworkdayjobs.com/BAH_Jobs/job/Arlington-VA/Data-Engineer_R0250042) |
| Booz Allen Hamilton | Cloud Engineer | Chantilly, VA | Not stated | Not shown | 4 days ago |  | [Apply](https://bah.wd1.myworkdayjobs.com/BAH_Jobs/job/Chantilly-VA/Cloud-Engineer_R0249978) |
| Booz Allen Hamilton | Data Scientist, Junior | McLean, VA | New grad | Not shown | 4 days ago |  | [Apply](https://bah.wd1.myworkdayjobs.com/BAH_Jobs/job/McLean-VA/Data-Scientist--Junior_R0248402) |
| Amgen | Data Scientist | United States - Remote | Not stated | Not shown | 4 days ago |  | [Apply](https://amgen.wd1.myworkdayjobs.com/Careers/job/United-States---Remote/Data-Scientist_R-246583) |
| Amgen | Enterprise Generative AI Platform Engineer | United States - Remote | Not stated | Not shown | 4 days ago |  | [Apply](https://amgen.wd1.myworkdayjobs.com/Careers/job/United-States---Remote/Enterprise-Generative-AI-Platform-Engineer_R-250809) |
| Amgen | Sr Associate Software Engineer | United States - Remote | Not stated | Not shown | 4 days ago |  | [Apply](https://amgen.wd1.myworkdayjobs.com/Careers/job/United-States---Remote/Sr-Associate-Software-Engineer_R-251394) |
| Stryker | Design Engineer - Software, RISE | Portage, Michigan | Not stated | Not shown | 4 days ago | $77,700 - $129,500 | [Apply](https://stryker.wd1.myworkdayjobs.com/StrykerCareers/job/Portage-Michigan/Design-Engineer---Software--RISE_R571062) |
| AT&amp;T | Systems Engineer and Integrator \(SE3\) \(Government\) | Columbia, Maryland | Not stated | Not shown | 4 days ago | $130,700 - $243,800 | [Apply](https://att.wd1.myworkdayjobs.com/ATTGeneral/job/Columbia-Maryland/Systems-Engineer-and-Integrator--SE3---Government-_R-123152) |
| Visa | AI-Native Growth Marketer | US - Austin, TX | Not stated | Not shown | 4 days ago |  | [Apply](https://visa.wd5.myworkdayjobs.com/Visa/job/US---Austin-TX/AI-Native-Growth-Marketer_REF088162W-1) |
| Cigna | Technology Strategy Leader - Enterprise Data, AI &amp; Platforms - Hybrid | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://cigna.wd5.myworkdayjobs.com/cignacareers/job/Bloomfield-CT/Technology-Strategy-Leader---Enterprise-Data--AI---Platforms---Hybrid_26007638-1) |
| Cigna | Software Engineering Advisors- Hybrid | Plano, TX | Not stated | Not shown | 4 days ago |  | [Apply](https://cigna.wd5.myworkdayjobs.com/cignacareers/job/Plano-TX/Software-Engineering-Advisors--Hybrid_26005843) |
| Comcast | Xfinity Mobile Retail Service Associate | CO - Denver, 1390 S Colorado Blvd - Retail XFR3358 | Not stated | Not shown | 4 days ago |  | [Apply](https://comcast.wd115.myworkdayjobs.com/Comcast_Careers/job/CO---Denver-1390-S-Colorado-Blvd---Retail-XFR3358/Xfinity-Mobile-Retail-Service-Associate_R444258) |
| Comcast | Mobile Retail Service Associate | DC - Washington, 715 7TH St NW - Retail XFR9100 | Not stated | Not shown | 4 days ago |  | [Apply](https://comcast.wd115.myworkdayjobs.com/Comcast_Careers/job/DC---Washington-715-7TH-St-NW---Retail-XFR9100/Mobile-Retail-Service-Associate_R444530) |
| Comcast | Xfinity Mobile Retail Service Associate - Bilingual Spanish | FL - Miami, 7404 SW 117th Ave - Retail XFR1501 | Not stated | Not shown | 4 days ago |  | [Apply](https://comcast.wd115.myworkdayjobs.com/Comcast_Careers/job/FL---Miami-7404-SW-117th-Ave---Retail-XFR1501/Xfinity-Retail-Service-Associate---Bilingual-Spanish_R441750) |
| Comcast | Xfinity Mobile Retail Service Associate | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://comcast.wd115.myworkdayjobs.com/Comcast_Careers/job/MI---Muskegon-5506-Harvey-St---Retail-XFR1723/Xfinity-Retail-Service-Associate_R443161) |
| Comcast | Python or GoLang Software Engineer \(Tier-2\) - 2 Days Onsite in Reston, VA - FreeWheel | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://comcast.wd115.myworkdayjobs.com/Comcast_Careers/job/VA---Reston-11951-Freedom-Dr-Ste-900/Python-or-GoLang-Software-Engineer--Tier-2----2-Days-Onsite-in-Reston--VA---FreeWheel_R438826) |
| Comcast | Xfinity Mobile Retail Service Associate​ | AZ - Tucson, 8020 N Cortaro Rd - Retail XFR3459 | Not stated | Not shown | 4 days ago |  | [Apply](https://comcast.wd115.myworkdayjobs.com/Comcast_Careers/job/AZ---Tucson-8020-N-Cortaro-Rd---Retail-XFR3459/Xfinity-Mobile-Retail-Service-Associate-_R444175) |
| Comcast | Xfinity Mobile Retail Service Associate | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://comcast.wd115.myworkdayjobs.com/Comcast_Careers/job/CO---Lakewood-7400-W-Alaska-Dr---Retail-XFR3352/Xfinity-Mobile-Retail-Service-Associate_R444373) |
| Comcast | Xfinity Mobile Retail Service | FL - Jacksonville, 4663 River City Dr - Retail XFR1538 | Not stated | Not shown | 4 days ago |  | [Apply](https://comcast.wd115.myworkdayjobs.com/Comcast_Careers/job/FL---Jacksonville-4663-River-City-Dr---Retail-XFR1538/Xfinity-Mobile-Retail-Service_R444247) |
| Comcast | Xfinity Mobile Retail Service Associate | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://comcast.wd115.myworkdayjobs.com/Comcast_Careers/job/FL---Ft-Lauderdale-1550-N-Federal-Hwy---Retail-XFR1515/Xfinity-Mobile-Retail-Service-Associate_R444704) |
| Comcast | Xfinity Mobile Retail Service Associate - Bilingual Spanish | FL - Miami, 2960 Aventura Blvd Suite 1 - Retail XFR1524 | Not stated | Not shown | 4 days ago |  | [Apply](https://comcast.wd115.myworkdayjobs.com/Comcast_Careers/job/FL---Miami-2960-Aventura-Blvd-Suite-1---Retail-XFR1524/Xfinity-Retail-Service-Associate---Bilingual-Spanish_R441327) |
| Comcast | Xfinity Mobile Retail Service Associate- Bilingual Spanish | FL - Miami, 9251 West Flagler St - Retail XFR1511 | Not stated | Not shown | 4 days ago |  | [Apply](https://comcast.wd115.myworkdayjobs.com/Comcast_Careers/job/FL---Miami-9251-West-Flagler-St---Retail-XFR1511/Xfinity-Retail-Service-Associate--Bilingual-Spanish_R442456) |
| Comcast | Xfinity Mobile Retail Service Associate | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://comcast.wd115.myworkdayjobs.com/Comcast_Careers/job/FL---Vero-Beach-5840-20th-St---Retail-XFR1530/Xfinity-Mobile-Retail-Service-Associate_R444236-1) |
| Comcast | Xfinity Mobile Retail Service Associate - Bilingual Spanish | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://comcast.wd115.myworkdayjobs.com/Comcast_Careers/job/IL---Bolingbrook-1122-West-Boughton-Rd---Retail-XFR1304/Xfinity-Retail-Service-Associate_R442458) |
| Comcast | Xfinity Mobile Retail Service Associate | IL - Chicago, 30 South Halsted St - Retail XFR1318 | Not stated | Not shown | 4 days ago |  | [Apply](https://comcast.wd115.myworkdayjobs.com/Comcast_Careers/job/IL---Chicago-30-South-Halsted-St---Retail-XFR1318/Xfinity-Mobile-Retail-Service-Associate_R444628) |
| Comcast | Backend Software Engineer \(Python or PHP\) - Chicago - ONSITE 2X Week- FreeWheel | IL - Chicago, 350 N\. Orleans St 1300N | Not stated | Not shown | 4 days ago |  | [Apply](https://comcast.wd115.myworkdayjobs.com/Comcast_Careers/job/IL---Chicago-350-N-Orleans-St-1300N/Backend-Software-Engineer--Python-or-PHP----Chicago---ONSITE-2X-Week--FreeWheel_R443376) |
| Comcast | Software Engineer \(Python, Java, C\+\+, or GoLang\) - Chicago, IL- ONSITE 2X Week- FreeWheel | IL - Chicago, 350 N\. Orleans St 1300N | Not stated | Not shown | 4 days ago |  | [Apply](https://comcast.wd115.myworkdayjobs.com/Comcast_Careers/job/IL---Chicago-350-N-Orleans-St-1300N/Software-Engineer--Python--Java--C----or-GoLang----Chicago--IL--ONSITE-2X-Week--FreeWheel_R443638) |
| Comcast | Xfinity Mobile Retail Service Associate | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://comcast.wd115.myworkdayjobs.com/Comcast_Careers/job/IL---Morton-Grove-7927-Golf-Rd---Retail-XFR1302/Xfinity-Mobile-Retail-Service-Associate_R444445) |
| Comcast | Xfinity Mobile Retail Service Associate | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://comcast.wd115.myworkdayjobs.com/Comcast_Careers/job/IL---Oak-Brook-3041-Butterfield-Rd---Retail-XFR1305/Xfinity-Mobile-Retail-Service-Associate_R444419) |
| Comcast | Xfinity Mobile Retail Service Associate | MI - Grand Rapids, 1971 E Beltline Ave NE - Retail XFR1706 | Not stated | Not shown | 4 days ago |  | [Apply](https://comcast.wd115.myworkdayjobs.com/Comcast_Careers/job/MI---Grand-Rapids-1971-E-Beltline-Ave-NE---Retail-XFR1706/Xfinity-Retail-Service-Associate_R442518-1) |
| Comcast | Xfinity Mobile Retail Service Associate | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://comcast.wd115.myworkdayjobs.com/Comcast_Careers/job/MI---Grandville-3433-Century-Center-St-SW---Retail-XFR1724/Xfinity-Mobile-Retail-Service-Associate_R444196) |
| Comcast | Backend Software Engineer \(Python or PHP\) - New York - ONSITE 4X Week | NY - New York, 1407 Broadway Floor 12 | Not stated | Not shown | 4 days ago |  | [Apply](https://comcast.wd115.myworkdayjobs.com/Comcast_Careers/job/NY---New-York-1407-Broadway-Floor-12/Backend-Software-Engineer--Python-or-PHP----New-York---ONSITE-4X-Week_R443340) |
| Comcast | Xfinity Mobile Retail Service Associate | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://comcast.wd115.myworkdayjobs.com/Comcast_Careers/job/OR---Portland-7037-NE-Sandy-Blvd---Retail-XFR3550/Xfinity-Mobile-Retail-Service-Associate_R444043) |
| Comcast | Software Release and Triage Engineer | PA - Philadelphia, 1800 Arch St | Not stated | Not shown | 4 days ago |  | [Apply](https://comcast.wd115.myworkdayjobs.com/Comcast_Careers/job/PA---Philadelphia-1800-Arch-St/Software-Release-and-Triage-Engineer_R442881) |
| Comcast | Site Reliability Engineer, Streaming HUB - FreeWheel | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://comcast.wd115.myworkdayjobs.com/Comcast_Careers/job/VA---Reston-11951-Freedom-Dr-Ste-900/Site-Reliability-Engineer--Steaming-HUB---FreeWheel_R439394) |
| Comcast | Xfinity Mobile Retail Service Associate | WA - Spokane, 4423 N Division St - Retail XFR3657 | Not stated | Not shown | 4 days ago |  | [Apply](https://comcast.wd115.myworkdayjobs.com/Comcast_Careers/job/WA---Spokane-4423-N-Division-St---Retail-XFR3657/Xfinity-Mobile-Retail-Service-Associate_R444627) |
| T-Mobile | Mobile Associate, Store-in-Store​ - Retail Sales | Erie, Pennsylvania | Not stated | Not shown | 4 days ago | $18,000/year | [Apply](https://tmobile.wd1.myworkdayjobs.com/External/job/Erie-Pennsylvania/Mobile-Associate--Store-in-Store----Retail-Sales_REQ374783-1) |
| T-Mobile | Mobile Associate - Retail Sales | Paola, Kansas | Not stated | Not shown | 4 days ago | $18,000/year | [Apply](https://tmobile.wd1.myworkdayjobs.com/External/job/Paola-Kansas/Mobile-Associate---Retail-Sales_REQ374038) |
| T-Mobile | Mobile Associate - Retail Sales | Ada, Oklahoma | Not stated | Not shown | 4 days ago | $18,000/year | [Apply](https://tmobile.wd1.myworkdayjobs.com/External/job/Ada-Oklahoma/Mobile-Associate---Retail-Sales_REQ373967-1) |
| T-Mobile | Mobile Associate - Retail Sales | Austin, Texas | Not stated | Not shown | 4 days ago | $18,000/year | [Apply](https://tmobile.wd1.myworkdayjobs.com/External/job/Austin-Texas/Mobile-Associate---Retail-Sales_REQ375008) |
| T-Mobile | Mobile Associate - Retail Sales | Cedar Rapids, Iowa | Not stated | Not shown | 4 days ago | $18,000/year | [Apply](https://tmobile.wd1.myworkdayjobs.com/External/job/Cedar-Rapids-Iowa/Mobile-Associate---Retail-Sales_REQ374881-1) |
| T-Mobile | Mobile Associate, Store in store - Retail Sales | Conway, Arkansas | Not stated | Not shown | 4 days ago | $18,000/year | [Apply](https://tmobile.wd1.myworkdayjobs.com/External/job/Conway-Arkansas/Mobile-Associate--Store-in-store---Retail-Sales_REQ374418) |
| T-Mobile | Mobile Associate - Retail Sales | Fort Smith, Arkansas | Not stated | Not shown | 4 days ago | $18,000/year | [Apply](https://tmobile.wd1.myworkdayjobs.com/External/job/Fort-Smith-Arkansas/Mobile-Associate---Retail-Sales_REQ374158-1) |
| T-Mobile | Mobile Associate - Retail Sales | Joplin, Missouri | Not stated | Not shown | 4 days ago | $18,000/year | [Apply](https://tmobile.wd1.myworkdayjobs.com/External/job/Joplin-Missouri/Mobile-Associate---Retail-Sales_REQ374118-1) |
| T-Mobile | Mobile Associate - Retail Sales | Lawton, Oklahoma | Not stated | Not shown | 4 days ago | $18,000/year | [Apply](https://tmobile.wd1.myworkdayjobs.com/External/job/Lawton-Oklahoma/Mobile-Associate---Retail-Sales_REQ374349-1) |
| T-Mobile | Mobile Associate, Store in Store - Retail Sales | Lawton, Oklahoma | Not stated | Not shown | 4 days ago | $18,000/year | [Apply](https://tmobile.wd1.myworkdayjobs.com/External/job/Lawton-Oklahoma/Mobile-Associate--Store-in-Store---Retail-Sales_REQ373412-1) |
| T-Mobile | Mobile Associate, Store in Store - Retail Sales | Maplewood, Missouri | Not stated | Not shown | 4 days ago | $18,000/year | [Apply](https://tmobile.wd1.myworkdayjobs.com/External/job/Maplewood-Missouri/Mobile-Associate--Store-in-Store---Retail-Sales_REQ372255-2) |
| T-Mobile | Mobile Associate - Retail Sales, Bilingual | Neosho, Missouri | Not stated | Not shown | 4 days ago | $18,000/year | [Apply](https://tmobile.wd1.myworkdayjobs.com/External/job/Neosho-Missouri/Mobile-Associate---Retail-Sales--Bilingual_REQ374564-1) |
| T-Mobile | Mobile Associate - Retail Sales | Portage, Wisconsin | Not stated | Not shown | 4 days ago | $18,000/year | [Apply](https://tmobile.wd1.myworkdayjobs.com/External/job/Portage-Wisconsin/Mobile-Associate---Retail-Sales_REQ374997-1) |
| T-Mobile | Mobile Associate - Retail Sales | Portage, Wisconsin | Not stated | Not shown | 4 days ago | $18,000/year | [Apply](https://tmobile.wd1.myworkdayjobs.com/External/job/Portage-Wisconsin/Mobile-Associate---Retail-Sales_REQ374999-1) |
| T-Mobile | Mobile Associate - Retail Sales | Portage, Wisconsin | Not stated | Not shown | 4 days ago | $18,000/year | [Apply](https://tmobile.wd1.myworkdayjobs.com/External/job/Portage-Wisconsin/Mobile-Associate---Retail-Sales_REQ375001-1) |
| T-Mobile | Mobile Associate - Retail Sales | Poteau, Oklahoma | Not stated | Not shown | 4 days ago | $18,000/year | [Apply](https://tmobile.wd1.myworkdayjobs.com/External/job/Poteau-Oklahoma/Mobile-Associate---Retail-Sales_REQ373068-1) |
| T-Mobile | Mobile Associate, Store-in-Store​-Retail Sales | Rochester, Minnesota | Not stated | Not shown | 4 days ago | $18,000/year | [Apply](https://tmobile.wd1.myworkdayjobs.com/External/job/Rochester-Minnesota/Mobile-Associate--Store-in-Store--Retail-Sales_REQ375105-1) |
| T-Mobile | Mobile Associate - Retail Sales | Rogers, Arkansas | Not stated | Not shown | 4 days ago | $20/hour | [Apply](https://tmobile.wd1.myworkdayjobs.com/External/job/Rogers-Arkansas/Mobile-Associate---Retail-Sales_REQ373018-1) |
| T-Mobile | Mobile Associate, Store-in-Store - Retail Sales | Springfield, Missouri | Not stated | Not shown | 4 days ago | $18,000/year | [Apply](https://tmobile.wd1.myworkdayjobs.com/External/job/Springfield-Missouri/Mobile-Associate--Store-in-Store---Retail-Sales_REQ374544-1) |
| DXC Technology | Java Software Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://dxctechnology.wd1.myworkdayjobs.com/DXCJobs/job/TWN---TPE---TAIPEI/Java-Software-Engineer_51589489-1) |
| Analog Devices | Associate Embedded Software Engineer | ⚠ Unknown location | Not stated | Not shown | 4 days ago |  | [Apply](https://analogdevices.wd1.myworkdayjobs.com/External/job/US-MA-Wilmington/Associate-Embedded-Software-Engineer_R266131) |

<!-- ENTRY_JOBS:END -->
