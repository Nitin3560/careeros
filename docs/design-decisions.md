# Engineering Design Decisions

The architecture documentation explains how CareerOS is organized.

This document explains why I designed it that way.

CareerOS started as a job aggregation and matching tool, but the interesting engineering problems came from everything around that core idea: unreliable external sources, repeated ingestion, duplicate jobs, slow matching, long-running network work, and the need to keep the user-facing application responsive.

## Why I Used Source Adapters

Different applicant tracking systems expose jobs in different formats.

Greenhouse, Lever, and Ashby may represent fields such as title, location, description, job id, department, and application URL differently.

Initially, it would have been easy to let each part of the application understand those differences.

I avoided that.

Instead, each provider has its own adapter and everything downstream works with a normalized internal job model.

```text
Greenhouse --+
Lever -------+--> Normalized Job
Ashby -------+
```

This keeps provider-specific logic isolated and makes new sources easier to add later.

## Why I Normalize Jobs Before Matching

The matching engine should not care where a job came from.

If matching logic had to handle separate Greenhouse, Lever, and Ashby formats, every new source would increase the complexity of the ranking system.

Normalizing once during ingestion gives the rest of CareerOS one consistent representation.

That keeps matching, caching, search, and frontend delivery much simpler.

## Why I Separated Ingestion From User Requests

Fetching jobs from many external sources is slow and unpredictable.

External APIs may be rate-limited, unavailable, or simply take several seconds.

I did not want a user opening CareerOS to wait for dozens of companies to respond.

So ingestion runs independently from normal request handling.

```text
User Request ----------> FastAPI

Ingestion Trigger
      |
      v
   Redis / RQ
      |
      v
    Worker
      |
      v
External Sources
```

The application serves data that has already been persisted instead of rebuilding the dataset on every request.

## Why I Used Background Workers

Some operations naturally take longer than a normal API request should.

Job ingestion is the clearest example.

Using workers creates a better boundary for retries, failure handling, long-running work, queueing, and future scheduling.

It also keeps the API process focused on user-facing requests.

## Why PostgreSQL Is The Source Of Truth

CareerOS needs persistent structured data.

Jobs, candidate information, matching state, and application-related information should survive process restarts and cache eviction.

PostgreSQL gives the system a reliable persistent store with strong querying capabilities.

I also wanted the database to do more than simply hold records.

It is part of the matching architecture.

## Why I Moved Filtering Into PostgreSQL

An early matching approach can be very simple:

```text
SELECT all jobs
      |
      v
Load into Python
      |
      v
Filter
      |
      v
Rank
```

That works while the dataset is small.

As the number of jobs grows, most of that work becomes unnecessary.

If structured criteria can eliminate irrelevant jobs in SQL, those records never need to enter the application matching path.

So I moved appropriate filtering and ranking work closer to PostgreSQL.

```text
PostgreSQL
    |
    v
Smaller Candidate Set
    |
    v
Application Ranking
```

This was one of the most important performance improvements in the system.

## Why I Used Redis For More Than One Purpose

Redis fits two different needs in CareerOS.

The first is coordination for background work through RQ.

The second is caching reusable application results.

```text
Redis
 +-- Job Queue
 +-- Cache
```

These uses are related by infrastructure but serve different application responsibilities.

PostgreSQL remains the persistent source of truth.

Redis is used where temporary fast state is useful.

## Why I Cache Match Results

Matching can be significantly more expensive than simply returning an already-computed result.

If the candidate profile and relevant job data have not changed, recalculating the same page of matches provides no additional value.

Caching allows CareerOS to reuse that work.

The important part was making sure the cache remains an optimization rather than blindly trusting anything stored in it.

Invalid or incomplete cached records should not be treated as valid user results.

## Why I Made Ingestion Repeatable

Job ingestion is not a one-time operation.

The same companies need to be checked repeatedly as jobs open, change, and close.

That means the pipeline has to assume it will see the same job again.

A repeated ingestion run should not create another copy of every posting.

Stable source identifiers and duplicate checks make repeated ingestion safe.

This is essentially an idempotency problem.

```text
Same Source Job
      |
      v
Already Exists?
  |           |
 yes          no
  |           |
Update      Insert
```

## Why I Batched Duplicate Checks

Checking every incoming job individually against the database creates unnecessary round trips.

When ingestion processes many jobs, small inefficiencies multiply quickly.

Batching duplicate checks allows CareerOS to compare a larger set of incoming identifiers with fewer database operations.

This is a simple optimization, but it matters in ingestion pipelines because the operation is repeated across many companies and jobs.

## Why I Treat External Sources As Unreliable

External job providers are outside CareerOS control.

A source can timeout, change its response, return malformed data, rate limit requests, or temporarily disappear.

The rest of the application should not fail because one provider is unavailable.

That is why external source logic sits behind adapters and background workers.

Existing persisted jobs remain usable even when fresh ingestion fails.

## Why I Separated Services From API Routes

FastAPI routes should coordinate requests.

They should not become the place where all application behavior lives.

CareerOS therefore keeps reusable behavior in service modules.

```text
Route
  |
  v
Service
  |
  +-- Database
  +-- Cache
  +-- Matching
  +-- External Sources
```

This makes logic easier to test and reduces coupling between HTTP behavior and domain behavior.

## Why I Kept The Frontend Separate

The Next.js frontend communicates with CareerOS through the API boundary.

It does not query PostgreSQL directly or know how ATS adapters work.

This lets the frontend focus on interaction, state, presentation, and workflow while the backend owns application and infrastructure concerns.

That separation also makes it easier to change one side without forcing changes throughout the other.

## Why I Used Docker

CareerOS depends on multiple services.

A typical local environment needs at least:

```text
API
Web
PostgreSQL
Redis
Worker
```

I wanted the environment to be reproducible rather than depending on every developer manually configuring each service.

Docker provides a consistent runtime boundary for those components.

It is not the architecture itself, but it makes the architecture easier to run.

## Why I Avoided Putting Everything Behind AI

CareerOS includes AI-assisted workflows, but the core system should not depend on a language model for basic job storage, filtering, or ingestion.

Structured operations are handled deterministically where possible.

AI is more useful where language understanding actually matters, such as resume interpretation or tailoring.

This keeps expensive or probabilistic reasoning out of paths where ordinary software is more reliable.

## Engineering Challenges

The most interesting CareerOS challenges were not individual features.

They were system-boundary problems.

Examples included keeping ingestion repeatable, handling multiple ATS formats, reducing matching latency, avoiding unnecessary database work, preventing bad cached results, separating long-running jobs from API traffic, and keeping external failures isolated.

Each of those pushed the system toward clearer boundaries.

## Lessons Learned

One of the biggest lessons from CareerOS was that performance problems often come from where work happens rather than the algorithm itself.

Moving filtering into PostgreSQL had more impact than trying to optimize Python loops.

Batching database work mattered more than micro-optimizing individual requests.

Caching was useful only after defining when cached data was valid.

Background workers became valuable once external network operations were treated as separate workloads instead of normal API logic.

The architecture became simpler as responsibilities became more explicit.

## Future Directions

There are several places where CareerOS can continue to improve.

These include better ingestion observability, source health monitoring, stronger retry policies, incremental job freshness handling, distributed worker scaling, authentication and user isolation, deployment automation, matching evaluation, and ranking explainability.

The main goal is not to add features for their own sake.

It is to make the existing system more reliable and measurable.

## Closing Thoughts

CareerOS began as a way to reduce the repetitive work of searching for software engineering jobs.

The more I built it, the more the project became about system design.

External data had to be normalized.

Long-running work had to be moved out of request paths.

Repeated ingestion had to become safe.

Matching had to move closer to the database.

Caching had to remain trustworthy.

The most useful architectural decision was consistently separating responsibilities instead of allowing the application to become one large pipeline.

> CareerOS works best when external collection, persistent storage, matching, caching, and user-facing delivery remain independent parts of the same system.
