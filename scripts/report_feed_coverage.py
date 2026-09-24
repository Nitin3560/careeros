#!/usr/bin/env python3
"""Measure misses from manually checked parallel LinkedIn postings."""
import argparse
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))


def miss_rate(misses: int, checked: int) -> float | None:
    return misses / checked if checked else None


def main() -> None:
    from sqlalchemy import text
    from app.database import SessionLocal

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since-days", type=int, default=7)
    parser.add_argument("--min-sample", type=int, default=30)
    args = parser.parse_args()
    if args.since_days < 1 or args.min_sample < 1:
        parser.error("since-days and min-sample must be positive")
    db = SessionLocal()
    try:
        row = db.execute(text("""
            SELECT count(*) AS checked,
                   count(*) FILTER (WHERE NOT was_in_feed) AS misses
            FROM job_feed_coverage_checks
            WHERE checked_at >= now() - (:days * interval '1 day')
        """), {"days": args.since_days}).mappings().one()
        checked, misses = row["checked"], row["misses"]
        rate = miss_rate(misses, checked)
        print(f"window_days={args.since_days} checked={checked} misses={misses}")
        if rate is None:
            print("miss_rate=unavailable (no manually checked LinkedIn postings)")
        else:
            print(f"miss_rate={rate:.1%} target=<15% result={'PASS' if rate < .15 else 'FAIL'}")
        if checked < args.min_sample:
            print(f"warning=small sample; need at least {args.min_sample} checks for a useful weekly signal")
        rows = db.execute(text("""
            SELECT cause, count(*) AS misses
            FROM job_feed_coverage_checks
            WHERE checked_at >= now() - (:days * interval '1 day') AND NOT was_in_feed
            GROUP BY cause ORDER BY cause
        """), {"days": args.since_days}).mappings()
        print("miss_causes:")
        for item in rows:
            print(f"  {item['cause']}: {item['misses']}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
