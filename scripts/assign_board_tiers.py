#!/usr/bin/env python3
"""Assign tier A to the 500 boards producing the most new jobs in 30 days."""
from pathlib import Path
import sys
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from app.database import SessionLocal  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        db.execute(text("UPDATE ats_boards SET tier='B', poll_interval_seconds=3600 WHERE tier='A'"))
        result = db.execute(text("""
            WITH ranked AS (
                SELECT board_id, count(*) AS new_count
                FROM jobs
                WHERE board_id IS NOT NULL AND first_seen_at >= now() - interval '30 days'
                GROUP BY board_id ORDER BY new_count DESC LIMIT 500
            )
            UPDATE ats_boards b SET tier='A', poll_interval_seconds=900, updated_at=now()
            FROM ranked r WHERE b.id=r.board_id AND b.status <> 'dead'
        """))
        db.commit()
        print(f"tier_a_boards={result.rowcount or 0}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
