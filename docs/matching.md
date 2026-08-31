# Candidate Matching Engine

The CareerOS matching engine ranks stored jobs against a candidate profile.

Its main goal is to reduce a large job corpus into a smaller set of relevant opportunities efficiently.

## Matching Pipeline

```text
Candidate Profile
       +
   Job Corpus
       |
       v
Database Filtering
       |
       v
Candidate Jobs
       |
       v
Scoring / Ranking
       |
       v
 Ranked Matches
       |
       v
     Cache
```

## Stage 1: Filtering

CareerOS first removes jobs that are clearly irrelevant using structured information available in PostgreSQL.

Instead of:

```text
Load Every Job
      |
      v
Filter in Python
```

CareerOS pushes appropriate filtering into the database:

```text
PostgreSQL
     |
     v
Filtered Jobs
     |
     v
Matching
```

This significantly reduces the amount of data processed by later stages.

## Candidate Profile

Matching uses structured candidate information derived from the user's profile and resume.

Relevant signals can include:

```text
skills
experience
target roles
location preferences
resume information
```

Keeping this information structured makes it reusable across matching and resume-tailoring workflows.

## Ranking

Jobs that survive the initial filtering stage are scored and ranked.

```text
Filtered Jobs
      |
      v
Matching Signals
      |
      v
Score
      |
      v
Sort
      |
      v
Top Matches
```

This separates inexpensive elimination from more detailed relevance evaluation.

## Caching

Computed match results can be cached when the underlying candidate and job data have not changed.

```text
Match Request
     |
     v
Cache Available?
   |       |
  yes      no
   |       |
Return   Compute
           |
           v
         Cache
```

Cached records are validated before being returned.

## Why This Design

The matching engine follows one important principle:

> Do not perform expensive ranking on jobs that can already be eliminated cheaply.

Using PostgreSQL for early filtering reduces application work and allows the matching pipeline to remain responsive as the job corpus grows.

## Summary

```text
Filter
  |
  v
Score
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

The matching engine converts CareerOS's normalized job dataset into a ranked set of opportunities for each candidate.
