import argparse
import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.database import SessionLocal  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tier-a", type=int, default=100)
    parser.add_argument("--tier-b", type=int, default=1000)
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        db.execute(text("UPDATE ats_boards SET priority = 3"))
        tier_a = assign_priority(db, priority=1, limit=args.tier_a, days=args.days)
        tier_b = assign_priority(
            db,
            priority=2,
            limit=max(args.tier_b - args.tier_a, 0),
            days=args.days,
            exclude_priority=1,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(
        "board priorities assigned: "
        f"tier_a={tier_a}, tier_b={tier_b}, tier_c=remaining"
    )


def assign_priority(
    db,
    priority: int,
    limit: int,
    days: int,
    exclude_priority: int | None = None,
) -> int:
    if limit <= 0:
        return 0

    exclude_clause = ""
    params = {"limit": limit, "days": days}
    if exclude_priority is not None:
        exclude_clause = "AND b.priority != :exclude_priority"
        params["exclude_priority"] = exclude_priority

    result = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT j.source, j.company, count(*) AS eligible_jobs
                FROM jobs j
                WHERE j.eligible IS true
                  AND j.date_posted > now() - (:days * interval '1 day')
                GROUP BY j.source, j.company
                ORDER BY eligible_jobs DESC, j.company ASC
                LIMIT :limit
            )
            UPDATE ats_boards b
               SET priority = :priority
              FROM ranked r
             WHERE b.ats = r.source
               AND b.slug = r.company
               {exclude_clause}
            RETURNING b.id
            """
        ),
        {**params, "priority": priority},
    )
    return len(result.fetchall())


if __name__ == "__main__":
    main()
