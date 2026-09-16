import argparse
import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.database import SessionLocal  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--since-hours", type=int, default=6)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        summary = db.execute(
            text(
                """
                SELECT count(*) AS eligible_rows,
                       count(DISTINCT queue_key) AS queue_items
                FROM jobs
                WHERE eligible IS true
                  AND first_seen_at > now() - (:hours * interval '1 hour')
                """
            ),
            {"hours": args.since_hours},
        ).one()
        print(
            f"eligible_rows={summary.eligible_rows} "
            f"queue_items={summary.queue_items}"
        )

        rows = db.execute(
            text(
                """
                SELECT DISTINCT ON (queue_key)
                       queue_key, company, title, location, date_posted,
                       first_seen_at, application_url
                FROM jobs
                WHERE eligible IS true
                  AND first_seen_at > now() - (:hours * interval '1 hour')
                  AND queue_key IS NOT NULL
                ORDER BY queue_key, first_seen_at DESC, date_posted DESC NULLS LAST
                LIMIT :limit
                """
            ),
            {"hours": args.since_hours, "limit": args.limit},
        ).all()
    finally:
        db.close()

    for row in rows:
        print(
            "\t".join(
                str(value or "").replace("\n", " ")[:160]
                for value in row
            )
        )


if __name__ == "__main__":
    main()
