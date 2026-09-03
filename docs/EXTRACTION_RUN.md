# Full Requirement Extraction Run

This run extracts verified job requirements for the eligible job pool.

```text
1  alembic upgrade head
2  export keys and curl-test them
3  run --limit 500
4  inspect extraction stats and matcher top 20
5  run full extraction with nohup
6  retry failed rows
7  run matcher over all extracted jobs
```

## Schema

```bash
cd apps/api
alembic upgrade head
```

The migration creates `job_requirements` with:

```text
job_id
requirements
status
error
model
prompt_version
key_index
input_tokens
output_tokens
extracted_at
```

`prompt_version` is stored per row so future prompt changes can reprocess only stale extractions.

## Keys

Export up to four Gemini keys:

```bash
export GEMINI_KEY_1=...
export GEMINI_KEY_2=...
export GEMINI_KEY_3=...
export GEMINI_KEY_4=...
```

Verify them before a long run:

```bash
for i in 1 2 3 4; do
  k=$(eval echo \$GEMINI_KEY_$i)
  code=$(curl -s -o /dev/null -w "%{http_code}" \
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key=$k" \
    -H 'Content-Type: application/json' \
    -d '{"contents":[{"parts":[{"text":"say ok"}]}]}')
  echo "key $i -> $code"
done
```

All configured keys should return `200`.

## Checkpoint

Run 500 jobs first:

```bash
python scripts/extract_all_requirements.py --limit 500
```

Then inspect the results:

```sql
SELECT status, count(*) FROM job_requirements GROUP BY 1;
```

```sql
SELECT r->>'verification_state' AS state, count(*)
FROM job_requirements jr,
     jsonb_array_elements(jr.requirements->'hard_requirements') r
WHERE jr.status = 'ok'
GROUP BY 1;
```

```sql
SELECT round(avg(jsonb_array_length(requirements->'preferred')), 1) AS mean,
       percentile_cont(0.5) WITHIN GROUP (
         ORDER BY jsonb_array_length(requirements->'preferred')) AS median
FROM job_requirements
WHERE status = 'ok';
```

```sql
SELECT key_index, count(*)
FROM job_requirements
GROUP BY 1
ORDER BY 1;
```

Stop and fix before scaling if rejection is high, preferred extraction is shallow, or one key is doing much less work than the others.

## Full Run

```bash
nohup python scripts/extract_all_requirements.py > extract.log 2>&1 &
tail -f extract.log
```

The run is resumable. Completed current-version rows are skipped.

## Retry Failures

```bash
python scripts/extract_all_requirements.py --retry-failed
```

Failures are recorded as `extraction_failed` or `parse_failed`, not silently skipped.

## Final Check

After extraction, run the matcher over all extracted jobs and read the top 20.

The goal is not just good extraction statistics. The top-ranked jobs must be jobs the candidate would actually consider applying to.
