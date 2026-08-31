# Performance and Caching

CareerOS was designed to keep matching and job retrieval responsive as the stored job corpus grows.

The largest performance improvement came from reducing unnecessary application-side processing.

## Matching Optimization

An earlier matching path loaded a large set of jobs into the application before filtering and ranking them.

```text
PostgreSQL
    |
    v
Large Job Set
    |
    v
Python Filtering
    |
    v
Ranking
```

The optimized path pushes appropriate filtering and ranking operations into PostgreSQL first.

```text
PostgreSQL Filtering
        |
        v
Small Candidate Set
        |
        v
Application Processing
        |
        v
Ranked Matches
```

In benchmark testing, Stage-1 matching latency decreased from approximately:

```text
690 ms -> 3.5 ms
```

This represents roughly a 197x reduction in Stage-1 latency.

## Ingestion Performance

CareerOS also reduces database overhead during ingestion by batching duplicate checks instead of querying for every incoming job independently.

```text
Incoming Jobs
      |
      v
Batch Source IDs
      |
      v
Existing Job Lookup
      |
      v
Insert New Records
```

This becomes increasingly important when processing thousands of postings across multiple companies.

## Caching

Redis is used to cache reusable results.

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

Cached match records are validated before being returned so incomplete results do not silently enter the user-facing workflow.

## Performance Principles

CareerOS follows three basic rules:

1. Filter before expensive processing.
2. Batch database operations where possible.
3. Do not recompute results that can safely be reused.

The goal is not simply to add caching or infrastructure, but to reduce unnecessary work throughout the request and ingestion paths.

## Summary

The main performance improvement came from changing where computation happens.

> Moving Stage-1 matching closer to PostgreSQL reduced measured latency from ~690 ms to ~3.5 ms while caching and batching further reduce repeated application and database work.
