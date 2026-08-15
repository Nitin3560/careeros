import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
sys.path.insert(0, str(API_DIR))
load_dotenv(API_DIR / ".env")

from app import models  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.services.job_matching import (  # noqa: E402
    MATCHING_PROMPT_VERSION,
    build_search_keywords,
    count_matching_jobs,
    get_or_create_matches,
    build_title_search_keywords,
    shortlist_jobs,
)


def timed(fn, repeats: int):
    values = []
    result = None
    for _ in range(repeats):
        start = time.perf_counter()
        result = fn()
        values.append((time.perf_counter() - start) * 1000)
    return result, summarize(values)


def summarize(values: list[float]):
    return {
        "runs": len(values),
        "min_ms": round(min(values), 2),
        "median_ms": round(statistics.median(values), 2),
        "max_ms": round(max(values), 2),
    }


def table_counts(db):
    tables = [
        models.User,
        models.CandidateProfile,
        models.Job,
        models.JobMatch,
        models.ResumeVersion,
        models.Application,
        models.CompanyTarget,
    ]
    return {table.__tablename__: db.query(table).count() for table in tables}


def find_profile(db, user_id: str | None):
    query = db.query(models.CandidateProfile)
    if user_id:
        query = query.filter(models.CandidateProfile.user_id == user_id)
    return query.order_by(models.CandidateProfile.updated_at.desc()).first()


def cache_state(db, user_id: str, profile, jobs):
    job_ids = [job.id for job in jobs]
    existing = (
        db.query(models.JobMatch)
        .filter(models.JobMatch.user_id == user_id, models.JobMatch.job_id.in_(job_ids))
        .all()
        if job_ids
        else []
    )
    existing_by_job_id = {match.job_id: match for match in existing}

    valid = 0
    estimated = 0
    stale = 0
    missing = 0
    for job in jobs:
        match = existing_by_job_id.get(job.id)
        if not match:
            missing += 1
        elif (
            match.profile_version == profile.profile_version
            and match.prompt_version == MATCHING_PROMPT_VERSION
            and not match.is_estimated
        ):
            valid += 1
        elif match.is_estimated:
            estimated += 1
        else:
            stale += 1

    total = len(jobs)
    return {
        "page_size": total,
        "valid_cached": valid,
        "estimated_cached": estimated,
        "stale_cached": stale,
        "missing": missing,
        "valid_cache_hit_rate": round(valid / total, 4) if total else 0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--allow-llm", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        profile = find_profile(db, args.user_id)
        if not profile:
            raise SystemExit("No candidate profile found")

        user_id = str(profile.user_id)
        keywords = build_search_keywords(profile.data)
        title_keywords = build_title_search_keywords(profile.data)

        total_matches, total_matches_timing = timed(
            lambda: count_matching_jobs(db, profile.data), args.repeats
        )
        jobs, shortlist_timing = timed(
            lambda: shortlist_jobs(
                db, profile.data, limit=args.limit, offset=args.offset
            ),
            args.repeats,
        )
        state = cache_state(db, user_id, profile, jobs)

        get_or_create_timing = None
        get_or_create_sample = None
        skipped_reason = None
        if args.allow_llm or state["missing"] == 0:
            results, get_or_create_timing = timed(
                lambda: get_or_create_matches(
                    db,
                    user_id,
                    profile,
                    offset=args.offset,
                    page_size=args.limit,
                ),
                args.repeats,
            )
            get_or_create_sample = [
                {
                    "title": result["job_title"],
                    "company": result["company"],
                    "score": result["match"].get("overall_score"),
                    "estimated": result["match"].get("estimated"),
                }
                for result in results[:5]
            ]
        else:
            skipped_reason = "page has uncached jobs; rerun with --allow-llm to measure cold LLM path"

        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "profile_id": str(profile.id),
            "profile_version": profile.profile_version,
            "parameters": {
                "offset": args.offset,
                "limit": args.limit,
                "repeats": args.repeats,
                "allow_llm": args.allow_llm,
            },
            "database_counts": table_counts(db),
            "keyword_count": len(keywords),
            "title_keyword_count": len(title_keywords),
            "retrieval_strategy": "postgres_title_full_text_rank",
            "total_matching_jobs": total_matches,
            "timings": {
                "count_matching_jobs": total_matches_timing,
                "shortlist_jobs_page": shortlist_timing,
                "get_or_create_matches": get_or_create_timing,
            },
            "cache_state": state,
            "sample_shortlist": [
                {"title": job.title, "company": job.company, "location": job.location}
                for job in jobs[:5]
            ],
            "sample_results": get_or_create_sample,
            "skipped_reason": skipped_reason,
        }

        text = json.dumps(payload, indent=2, default=str)
        print(text)

        if args.output:
            output = ROOT / args.output
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(text + "\n")
    finally:
        db.close()


if __name__ == "__main__":
    main()
