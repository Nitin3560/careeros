#!/usr/bin/env python3
"""Record a job found elsewhere that the CareerOS feed missed."""
import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))


def make_dedupe_key(company: str, title: str, found_url: str | None) -> str:
    canonical = "|".join((" ".join(company.casefold().split()), " ".join(title.casefold().split()), (found_url or "").strip().rstrip("/").casefold()))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def main() -> None:
    from sqlalchemy import text
    from app.database import SessionLocal

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company", required=True)
    parser.add_argument("--title", required=True)
    result_group = parser.add_mutually_exclusive_group(required=True)
    result_group.add_argument("--in-feed", action="store_true", help="This LinkedIn posting was already present in the feed")
    result_group.add_argument("--cause", choices=("not_polled", "filtered_out", "wrong_classification"))
    parser.add_argument("--location")
    parser.add_argument("--url")
    parser.add_argument("--notes")
    args = parser.parse_args()
    company = " ".join(args.company.split())
    title = " ".join(args.title.split())
    if not company or not title:
        parser.error("company and title must contain non-whitespace text")
    key = make_dedupe_key(company, title, args.url)
    db = SessionLocal()
    try:
        db.execute(text("""
            INSERT INTO job_feed_coverage_checks
                (company, title, location, found_url, was_in_feed, cause, notes)
            VALUES (:company, :title, :location, :url, :was_in_feed, :cause, :notes)
        """), {"company": company, "title": title, "location": args.location,
              "url": args.url, "was_in_feed": args.in_feed, "cause": args.cause,
              "notes": args.notes})
        if args.in_feed:
            db.commit()
            print("coverage_check=matched feed")
            return
        result = db.execute(text("""
            INSERT INTO job_feed_misses
                (dedupe_key, company, title, location, found_url, cause, notes)
            VALUES (:key, :company, :title, :location, :url, :cause, :notes)
            ON CONFLICT (dedupe_key) DO UPDATE SET
                occurrence_count = job_feed_misses.occurrence_count + 1,
                last_reported_at = now(), cause = EXCLUDED.cause,
                location = coalesce(EXCLUDED.location, job_feed_misses.location),
                found_url = coalesce(EXCLUDED.found_url, job_feed_misses.found_url),
                notes = coalesce(EXCLUDED.notes, job_feed_misses.notes)
            RETURNING id, occurrence_count
        """), {"key": key, "company": company, "title": title, "location": args.location,
              "url": args.url, "cause": args.cause, "notes": args.notes}).one()
        db.commit()
        print(f"miss_id={result.id} occurrence_count={result.occurrence_count} cause={args.cause}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
