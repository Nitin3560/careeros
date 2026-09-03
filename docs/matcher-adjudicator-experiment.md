# Matcher Adjudicator Experiment

This experiment tests whether a bounded LLM adjudicator improves CareerOS matching without replacing deterministic hard gates.

## Fixed Rule

Adopt the adjudicator only if all are true:

1. It agrees with human judgment at least as often as the deterministic matcher.
2. It is consistent across two runs on the same 50 jobs.
3. A hand sample of 20 `MET` verdicts contains no verdict the candidate disagrees with.
4. It never changes a deterministic `SKIP_HARD` decision.

Otherwise, keep the matcher deterministic and expand the ontology by hand.

## Isolation Boundary

The adjudicator only sees unresolved soft requirements from deterministic matching:

```text
missing_profile_fact_or_exact_match
```

It does not see:

```text
SKIP_HARD jobs
years gates
clearance gates
citizenship gates
sponsorship gates
the full profile
the running score
the final decision
```

## Adjudicator Input

```text
one requirement string
5-10 preselected candidate facts
```

## Adjudicator Output

```text
MET | PARTIAL | UNMET
supporting fact IDs
one-line reasoning
```

`PARTIAL` is logged only. It contributes zero to the match count in this experiment.

## Current Checkpoint

After loading five project fact sets and attested resume facts, the 500-job checkpoint is:

```text
APPLY      3
STRETCH   22
SKIP      46
SKIP_HARD 256
REVIEW    172
```

The current APPLY/STRETCH set is mixed:

```text
good fit / plausible:
- Stirling PDF, Full Stack Developer
- Truebill, Full Stack Engineer
- Fable, Full-Stack Product Engineer
- Stitch Fix, ML Platform Engineer
- Garner Health, Senior Site Reliability Engineer

questionable:
- Lyft and Reddit data scientist roles
- security-only roles
- QA automation role
- senior roles with high missing counts

wrong direction:
- Anduril / defense / robotics-adjacent roles still appear too high
```

Conclusion: the matcher is no longer dead, but ranking is not clean enough for the full run. The adjudicator experiment should measure only whether bounded requirement-level adjudication improves the unresolved soft-match cases.
