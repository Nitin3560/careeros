#!/usr/bin/env python3
"""Backfill jobs.board_id and ensure Amazon has a scheduler board row."""
import argparse
from pathlib import Path
import sys

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from app.database import SessionLocal  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=10000)
    args = parser.parse_args()
    total = 0
    db = SessionLocal()
    try:
        db.execute(text("""
            INSERT INTO ats_boards
                (id, ats, slug, company_name, company_display, status, tier, priority,
                 poll_interval_seconds, next_poll_at, consecutive_failures, not_found_count,
                 created_at, updated_at)
            VALUES
                (gen_random_uuid(), 'amazon', 'software-development-engineer', 'Amazon', 'Amazon',
                 'unknown', 'A', 1, 900, now(), 0, 0, now(), now())
            ON CONFLICT (ats, slug) DO NOTHING
        """))
        while True:
            result = db.execute(text("""
                WITH batch AS (
                    SELECT j.id, b.id AS board_id
                    FROM jobs j JOIN ats_boards b
                      ON b.ats = j.source AND (b.slug = j.company OR b.ats = 'amazon')
                    WHERE j.board_id IS NULL
                    LIMIT :limit
                    FOR UPDATE OF j SKIP LOCKED
                )
                UPDATE jobs j SET board_id = batch.board_id
                FROM batch WHERE j.id = batch.id
            """), {"limit": args.batch_size})
            count = result.rowcount or 0
            db.commit()
            total += count
            print(f"board_id_backfilled={total}", flush=True)
            if count < args.batch_size:
                break
    finally:
        db.close()


if __name__ == "__main__":
    main()
