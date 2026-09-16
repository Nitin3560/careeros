# Job Ingestion Pipeline

CareerOS continuously collects jobs from supported company sources and converts them into a normalized internal format.

The ingestion pipeline is intentionally separate from the user-facing request path.

## Pipeline

```text
Configured Companies
        |
        v
Source Resolver
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
Duplicate Check
        |
        v
PostgreSQL
```

The main supported source types are:

```text
Amazon
Greenhouse
Lever
Ashby
SmartRecruiters
Workable
LinkedIn
Freehire
```

Each provider has its own adapter so provider-specific formats do not leak into the rest of the application.

CareerOS has two kinds of ingestion sources:

```text
Company board source: company slug -> jobs
Search source: query/profile -> jobs
```

Company board sources are best for known target companies. Search sources are best for candidate-shaped discovery, such as "AI platform engineer", "new grad software engineer", or "remote backend engineer".

## Source Resolution

CareerOS first determines which adapter should handle a company.

```text
Company
   |
   v
Source Configuration
   |
   v
Adapter
```

This keeps company configuration separate from provider implementation.

## Normalization

Different ATS providers use different field names and response structures.

CareerOS converts them into one shared job representation.

```text
External Job
     |
     v
Normalized Job

title
company
location
description
source
source_job_id
apply_url
canonical_url
identity_key
first_seen_at
last_seen_at
last_verified_at
ingestion_status
seen_count
```

The matching engine only works with normalized jobs.

It does not need to know whether a posting originally came from Greenhouse, Lever, or Ashby.

Freshness fields are part of normalization because a job board is a changing inventory, not a static import. `first_seen_at` tells us when CareerOS discovered a job. `last_seen_at` and `last_verified_at` tell us whether it is still appearing in source data. `seen_count` helps separate stable listings from one-off scrape artifacts.

## Duplicate Handling

Ingestion runs repeatedly, so the same job may appear many times.

CareerOS checks existing source identifiers before inserting new records, then refreshes existing records when they appear again.

```text
Incoming Job
     |
     v
Already Exists?
   |       |
  yes      no
   |       |
Update   Insert
```

This makes repeated ingestion safer and prevents the database from filling with duplicate postings.

Duplicate checks can also be batched to reduce unnecessary database round trips.

CareerOS stores two identity forms:

```text
external_id: source-specific hard identity
identity_key: cross-source soft identity
```

`external_id` protects the database from repeated source records. `identity_key` gives ranking and future cleanup logic a way to spot the same job when it appears on multiple surfaces, usually by canonical application URL and then by normalized company/title/location.

## Background Execution

Ingestion is handled outside normal API requests.

```text
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
      |
      v
 PostgreSQL
```

This prevents slow or failing external APIs from blocking user-facing requests.

## Failure Handling

External job sources are treated as unreliable dependencies.

A provider may:

```text
timeout
return invalid data
rate limit requests
temporarily fail
```

A failed source should affect that ingestion run, not the entire CareerOS application.

Previously stored jobs remain available for search and matching.

Health statuses should preserve meaning:

```text
dead: source returned 404/410 and the board is probably gone
rate_limited: source asked us to slow down
unavailable: repeated transient failures crossed the retry threshold
error: one transient failure happened
```

This keeps temporary outages from being treated as proof that a company or board disappeared.

## Polling Tiers

ATS boards are prioritized so direct sources can be polled at different speeds:

```text
priority 1  Tier A companies, hourly
priority 2  good historical fit, every 6 hours
priority 3  long tail, daily
```

`scripts/assign_board_priorities.py` assigns those tiers from recent eligible job volume. `scripts/backfill_jobs.py --priority 1 --stale-days 0` can then refresh the Tier A pool without touching every board.

## Why This Boundary Matters

The ingestion layer has one responsibility:

> Turn unreliable external job data into reliable internal records.

Everything after that point works against CareerOS data rather than directly depending on external career sites.

That separation keeps matching, caching, and the frontend much simpler.

## Summary

```text
Fetch
  |
  v
Normalize
  |
  v
Deduplicate
  |
  v
Persist
```

The ingestion pipeline isolates external job providers from the rest of CareerOS and produces the normalized dataset used by the matching system.
