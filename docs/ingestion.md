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
Greenhouse
Lever
Ashby
```

Each provider has its own adapter so provider-specific formats do not leak into the rest of the application.

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
```

The matching engine only works with normalized jobs.

It does not need to know whether a posting originally came from Greenhouse, Lever, or Ashby.

## Duplicate Handling

Ingestion runs repeatedly, so the same job may appear many times.

CareerOS checks existing source identifiers before inserting new records.

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
