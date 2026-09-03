import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
sys.path.insert(0, str(API_DIR))
load_dotenv(API_DIR / ".env")

from app.database import SessionLocal  # noqa: E402


def main():
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT source,
                       count(*) FILTER (WHERE eligible) AS eligible,
                       count(*) AS total,
                       round(
                           100.0 * count(*) FILTER (WHERE eligible)
                           / nullif(count(*), 0),
                           1
                       ) AS pct
                FROM jobs
                GROUP BY 1
                ORDER BY eligible DESC
                """
            )
        ).all()
    finally:
        db.close()

    print(f"{'source':<16} {'eligible':>10} {'total':>10} {'pct':>8}")
    for source, eligible, total, pct in rows:
        print(f"{source:<16} {eligible:>10} {total:>10} {pct:>7}%")


if __name__ == "__main__":
    main()
