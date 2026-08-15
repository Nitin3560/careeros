# CareerOS Baseline Measurements

Generated locally against the current Docker Postgres database.

## Commands

```bash
apps/api/.venv/bin/python scripts/baseline_metrics.py \
  --output docs/performance/baseline-local.json

apps/api/.venv/bin/python scripts/baseline_metrics.py \
  --offset 40 \
  --limit 10 \
  --output docs/performance/baseline-local-offset-40.json
```

Use `--allow-llm` only when intentionally measuring the cold LLM path.

## Current Snapshot

- Jobs: 978
- Candidate profiles: 6
- Stored job matches: 192
- Search keywords for measured profile: 106
- Total matching jobs from current Stage 1 scorer: 956

## Offset 0, Limit 10

- Cache state: 10 valid cached, 0 missing
- Valid cache hit rate: 100%
- `count_matching_jobs` median: 676.30 ms
- `shortlist_jobs` median: 692.72 ms
- `get_or_create_matches` median: 691.99 ms

## Offset 40, Limit 10

- Cache state: 0 valid cached, 10 missing
- Valid cache hit rate: 0%
- `count_matching_jobs` median: 480.90 ms
- `shortlist_jobs` median: 484.22 ms
- `get_or_create_matches`: skipped to avoid LLM calls

## Initial Read

The cached page avoids repeated LLM inference, but response time is still dominated by Stage 1 candidate scoring. The current scorer loads broad candidates and ranks them in Python, so it scales with the number of jobs matched by keyword conditions before the cache is checked.

The next optimization target should not be the LLM path yet. First, protect this behavior with tests, then measure and improve Stage 1 retrieval/scoring as data volume grows.
